#!/usr/bin/env python3
import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from playwright.sync_api import Browser, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright


BASE_URL = "https://stop-piramida.kz/videos"
CDP_URL = "http://127.0.0.1:9222"
ROOT = Path(__file__).resolve().parents[1]
METADATA_DIR = ROOT / "data" / "metadata"
RAW_DIR = ROOT / "data" / "raw"
VIDEOS_DIR = ROOT / "outputs" / "videos"
ALL_VIDEOS_PATH = METADATA_DIR / "all_videos.jsonl"

CATEGORIES = [
    "lzheturizm",
    "lzhezarabotok",
    "stop-mfo",
    "dropperstvo",
    "lzhe-kredityi",
    "kriptoriski",
    "lzheyuristyi",
    "fishing",
    "lzheprodavczyi",
    "lzhexalyal",
    "telefonnoe-moshennichestvo",
    "roditelyam-na-zametku",
    "rabota-za-graniczej",
    "fejkovyie-vyiplatyi",
    "romanticheskoe-moshennichestvo",
    "riski-v-setevom-marketinge",
    "finansovyie-piramidyi",
]
_PLAYWRIGHT = None


def connect_browser(cdp_url: str = CDP_URL) -> Browser:
    global _PLAYWRIGHT
    playwright = sync_playwright().start()
    _PLAYWRIGHT = playwright
    browser = playwright.chromium.connect_over_cdp(cdp_url)
    return browser


def load_category(page: Page, category: str) -> None:
    url = f"{BASE_URL}/{category}"
    print(f"OPEN PAGE: {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    page.wait_for_load_state("networkidle", timeout=30_000)

    previous_count = -1
    stagnant_clicks = 0

    while True:
        cards_count = page.locator(".videoBoxHover").count()
        if cards_count == previous_count:
            stagnant_clicks += 1
        else:
            stagnant_clicks = 0
        previous_count = cards_count

        button = _find_show_more_button(page)
        if button is None or stagnant_clicks >= 2:
            return

        try:
            button.scroll_into_view_if_needed(timeout=5_000)
            button.click(timeout=10_000)
            page.wait_for_load_state("networkidle", timeout=20_000)
            page.wait_for_timeout(700)
        except PlaywrightTimeoutError:
            return


def extract_videos(page: Page, category: str) -> list[dict[str, str]]:
    items = page.evaluate(
        """
        (category) => Array.from(document.querySelectorAll('.videoBoxHover')).map((card) => {
          const parent = card.parentElement || card.closest('a, article, div') || card;
          const desc = parent.querySelector('.descVideo__text');
          const pageUrl = card.getAttribute('data-v-fullurl') || card.href || parent.href || '';
          const vimeoUrl = card.getAttribute('data-v-url') || '';
          return {
            category,
            title: (card.getAttribute('data-v-title') || card.textContent || '').trim(),
            description: desc ? desc.textContent.trim().replace(/\\s+/g, ' ') : '',
            page_url: pageUrl ? new URL(pageUrl, window.location.href).href : '',
            vimeo_url: vimeoUrl,
            vimeo_id: (vimeoUrl.match(/vimeo\\.com\\/(?:video\\/)?(\\d+)/) || [])[1] || ''
          };
        })
        """
        ,
        category,
    )

    seen: set[str] = set()
    deduped: list[dict[str, str]] = []
    for item in items:
        key = item.get("vimeo_id") or item.get("page_url")
        if key and key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped


def get_playlist(page: Page, video: dict[str, str], timeout_ms: int = 45_000) -> tuple[dict[str, Any], str]:
    playlist_responses: list[tuple[str, dict[str, Any]]] = []
    page_url = video["page_url"]
    logged_playlists: set[str] = set()

    def on_response(response: Any) -> None:
        url = response.url
        if "playlist.json" not in url:
            return
        if url not in logged_playlists:
            logged_playlists.add(url)
            print(f"FOUND PLAYLIST: {url}")
        try:
            playlist_responses.append((url, response.json()))
        except Exception:
            pass

    page.on("response", on_response)
    try:
        with page.expect_response(lambda r: "playlist.json" in r.url, timeout=timeout_ms) as response_info:
            print(f"OPEN PAGE: {page_url}")
            page.goto(page_url, wait_until="domcontentloaded", timeout=60_000)
            _start_vimeo_playback(page, video)
        response = response_info.value
        return response.json(), response.url
    except PlaywrightTimeoutError:
        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            if playlist_responses:
                return playlist_responses[-1]
            page.wait_for_timeout(500)
        raise RuntimeError("playlist.json was not captured")
    finally:
        page.remove_listener("response", on_response)


def select_best_stream(playlist: dict[str, Any], playlist_url: str = "") -> dict[str, Any]:
    streams = playlist.get("video") or []
    if not streams:
        streams = _extract_streams_recursively(playlist)
    if not streams:
        raise RuntimeError("playlist contains no video streams")

    video_stream = max(
        streams,
        key=lambda item: (
            int(item.get("width") or 0) * int(item.get("height") or 0),
            int(item.get("bitrate") or 0),
        ),
    )
    audio_stream = _select_best_audio_stream(playlist)

    playlist_base = urljoin(playlist_url, playlist.get("base_url") or "")
    return {
        "playlist_url": playlist_url,
        "playlist_base": playlist_base,
        "video": _normalize_stream_urls(video_stream, playlist_base),
        "audio": _normalize_stream_urls(audio_stream, playlist_base) if audio_stream else None,
    }


def download_segments(stream_bundle: dict[str, Any], work_dir: Path) -> dict[str, Path | None]:
    work_dir.mkdir(parents=True, exist_ok=True)
    video_path = _download_stream_fragments(stream_bundle["video"], work_dir / "video")
    audio = stream_bundle.get("audio")
    audio_path = _download_stream_fragments(audio, work_dir / "audio") if audio else None
    return {"video": video_path, "audio": audio_path}


def merge_segments(downloaded: dict[str, Path | None], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    video_path = downloaded["video"]
    audio_path = downloaded.get("audio")
    if not video_path:
        raise RuntimeError("video fragments were not downloaded")

    tmp_output = output_path.with_name(f"{output_path.stem}.part{output_path.suffix}")
    if audio_path and shutil.which("ffmpeg"):
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-c",
            "copy",
            str(tmp_output),
        ]
        subprocess.run(command, check=True)
    else:
        shutil.copyfile(video_path, tmp_output)

    tmp_output.replace(output_path)


def save_metadata(video: dict[str, Any], playlist_info: dict[str, Any], output_path: Path) -> None:
    metadata_path = output_path.with_suffix(".json")
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        **video,
        "mp4_path": str(output_path.relative_to(ROOT)),
        "playlist_url": playlist_info.get("playlist_url", ""),
        "selected_video": _stream_metadata(playlist_info["video"]),
        "selected_audio": _stream_metadata(playlist_info["audio"]) if playlist_info.get("audio") else None,
    }
    metadata_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    args = _parse_args()
    _ensure_dirs()
    categories = CATEGORIES if args.all else [args.category]

    browser = connect_browser(args.cdp_url)
    try:
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.new_page()
        all_videos: list[dict[str, str]] = []

        for category in categories:
            print(f"[+] Loading category {category}")
            load_category(page, category)
            videos = extract_videos(page, category)
            _save_category_index(category, videos)
            all_videos.extend(videos)
            print(f"[✓] Indexed {len(videos)} videos in {category}")

        _save_all_index(all_videos)
        print(f"[✓] Saved combined index -> {ALL_VIDEOS_PATH.relative_to(ROOT)}")

        total = len(all_videos)
        for index, video in enumerate(all_videos, start=1):
            category = video["category"]
            vimeo_id = video.get("vimeo_id") or _extract_vimeo_id(video.get("vimeo_url", ""))
            if not vimeo_id:
                print(f"[!] Failed [{index}/{total}] {video.get('title', '')}: no Vimeo id")
                continue

            output_path = VIDEOS_DIR / category / f"{vimeo_id}.mp4"
            if output_path.exists() and output_path.stat().st_size > 0:
                print(f"[{index}/{total}] Skipping existing {output_path.relative_to(ROOT)}")
                continue

            print(f"[{index}/{total}] Downloading {category}/{vimeo_id} ...")
            try:
                playlist, playlist_url = get_playlist(page, video)
                playlist_info = select_best_stream(playlist, playlist_url)
                _save_raw_playlist(category, vimeo_id, playlist)
                work_dir = RAW_DIR / "segments" / category / vimeo_id
                downloaded = download_segments(playlist_info, work_dir)
                merge_segments(downloaded, output_path)
                save_metadata(video, playlist_info, output_path)
                print(f"[✓] Saved {output_path.relative_to(ROOT)}")
            except Exception as exc:
                print(f"[!] Failed {category}/{vimeo_id}: {exc}")
    finally:
        try:
            browser.close()
        finally:
            if _PLAYWRIGHT:
                _PLAYWRIGHT.stop()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download stop-piramida.kz video library via Playwright and Vimeo playlist.json.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--category", choices=CATEGORIES, help="download one category")
    group.add_argument("--all", action="store_true", help="download all known categories")
    parser.add_argument("--cdp-url", default=CDP_URL, help=f"Chromium CDP URL, default: {CDP_URL}")
    return parser.parse_args()


def _ensure_dirs() -> None:
    for path in (METADATA_DIR, RAW_DIR, ROOT / "data" / "transcripts", VIDEOS_DIR):
        path.mkdir(parents=True, exist_ok=True)


def _find_show_more_button(page: Page) -> Any | None:
    selectors = [
        "text=Показать ещё",
        "text=Показать еще",
        "button:has-text('Показать')",
        "a:has-text('Показать')",
    ]
    for selector in selectors:
        try:
            matches = page.locator(selector)
            count = matches.count()
            if not count:
                continue
            locator = matches.nth(count - 1)
            if locator.is_visible(timeout=1_000):
                return locator
        except Exception:
            continue
    return None


def _start_vimeo_playback(page: Page, video: dict[str, str]) -> None:
    found_iframe = _log_vimeo_iframe(page, timeout_ms=3_000)

    for locator in [
        page.locator(".videoBoxHover").first,
        page.locator(".videoBox").first,
        page.locator("[data-v-url*='vimeo.com']").first,
        page.get_by_role("button", name=re.compile("play|воспроизвести", re.I)).first,
        page.locator("iframe[src*='vimeo.com']").first,
    ]:
        try:
            if locator.count() and locator.is_visible(timeout=2_000):
                locator.scroll_into_view_if_needed(timeout=2_000)
                locator.click(timeout=5_000)
                break
        except Exception:
            continue

    if not found_iframe:
        page.wait_for_timeout(1_000)
        _log_vimeo_iframe(page, timeout_ms=500)


def _log_vimeo_iframe(page: Page, timeout_ms: int) -> bool:
    try:
        iframe = page.wait_for_selector("iframe[src*='vimeo.com']", timeout=timeout_ms)
        src = iframe.get_attribute("src") or ""
        print(f"FOUND IFRAME: {src}")
        return True
    except PlaywrightTimeoutError:
        pass

    for frame in page.frames:
        if "vimeo.com" in frame.url:
            print(f"FOUND IFRAME: {frame.url}")
            return True

    print("FOUND IFRAME: <none>")
    return False


def _extract_streams_recursively(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if value.get("segments") and value.get("init_segment"):
            found.append(value)
        for child in value.values():
            found.extend(_extract_streams_recursively(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_extract_streams_recursively(child))
    return found


def _select_best_audio_stream(playlist: dict[str, Any]) -> dict[str, Any] | None:
    streams = playlist.get("audio") or []
    streams = [item for item in streams if item.get("segments") and item.get("init_segment")]
    if not streams:
        return None
    return max(streams, key=lambda item: int(item.get("bitrate") or 0))


def _normalize_stream_urls(stream: dict[str, Any], playlist_base: str) -> dict[str, Any]:
    base_url = urljoin(playlist_base, stream.get("base_url") or "")
    init_segment = stream.get("init_segment")
    init_segment_url = stream.get("init_segment_url")
    segments = stream.get("segments") or []
    if isinstance(init_segment, dict):
        init_segment_url = init_segment.get("url")
        init_segment = None

    init_bytes = None
    if init_segment:
        init_bytes = _decode_init_segment(init_segment)
        print("INIT SEGMENT: base64")
    elif init_segment_url:
        init_segment_url = urljoin(base_url, init_segment_url)
        print("INIT SEGMENT: url")

    segment_urls = [
        urljoin(base_url, segment["url"] if isinstance(segment, dict) else str(segment))
        for segment in segments
    ]
    urls = []
    if init_segment_url:
        urls.append(init_segment_url)
    urls.extend(segment_urls)

    return {
        **stream,
        "init_bytes": init_bytes,
        "init_segment_url": init_segment_url,
        "segment_urls": segment_urls,
        "absolute_urls": urls,
        "absolute_base_url": base_url,
    }


def _download_stream_fragments(stream: dict[str, Any], target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    output_path = target_dir.with_suffix(".mp4")
    part_path = output_path.with_suffix(".mp4.part")
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://player.vimeo.com/"}

    with part_path.open("wb") as out:
        if stream.get("init_bytes"):
            out.write(stream["init_bytes"])
        for number, url in enumerate(stream["absolute_urls"]):
            fragment_path = target_dir / f"{number:06d}.m4s"
            if not fragment_path.exists() or fragment_path.stat().st_size == 0:
                _download_url(url, fragment_path, headers)
            with fragment_path.open("rb") as fragment:
                shutil.copyfileobj(fragment, out)

    part_path.replace(output_path)
    return output_path


def _decode_init_segment(init_segment: Any) -> bytes:
    if isinstance(init_segment, bytes):
        return init_segment
    if not isinstance(init_segment, str):
        raise RuntimeError(f"unsupported init_segment type: {type(init_segment).__name__}")

    payload = init_segment.strip()
    if payload.startswith("range/prot/"):
        payload = payload[len("range/prot/") :]
    missing_padding = len(payload) % 4
    if missing_padding:
        payload += "=" * (4 - missing_padding)
    return base64.b64decode(payload)


def _download_url(url: str, path: Path, headers: dict[str, str], retries: int = 3) -> None:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            request = Request(url, headers=headers)
            with urlopen(request, timeout=60) as response, path.with_suffix(path.suffix + ".part").open("wb") as out:
                shutil.copyfileobj(response, out)
            path.with_suffix(path.suffix + ".part").replace(path)
            return
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(1.5 * attempt)
    raise RuntimeError(f"download failed: {url}: {last_error}")


def _save_category_index(category: str, videos: list[dict[str, str]]) -> None:
    path = METADATA_DIR / f"{category}.jsonl"
    with path.open("w", encoding="utf-8") as file:
        for video in videos:
            file.write(json.dumps(video, ensure_ascii=False) + "\n")


def _save_all_index(videos: list[dict[str, str]]) -> None:
    seen: set[str] = set()
    with ALL_VIDEOS_PATH.open("w", encoding="utf-8") as file:
        for video in videos:
            key = video.get("vimeo_id") or video.get("page_url") or json.dumps(video, sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            file.write(json.dumps(video, ensure_ascii=False) + "\n")


def _save_raw_playlist(category: str, vimeo_id: str, playlist: dict[str, Any]) -> None:
    path = RAW_DIR / "playlists" / category / f"{vimeo_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(playlist, ensure_ascii=False, indent=2), encoding="utf-8")


def _stream_metadata(stream: dict[str, Any]) -> dict[str, Any]:
    keys = ("id", "profile", "width", "height", "bitrate", "mime_type", "absolute_base_url")
    return {key: stream.get(key) for key in keys if key in stream}


def _extract_vimeo_id(url: str) -> str:
    parsed = urlparse(url)
    match = re.search(r"/(?:video/)?(\d+)", parsed.path)
    return match.group(1) if match else ""


if __name__ == "__main__":
    main()
