#!/usr/bin/env python3
import argparse
import base64
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import re
import requests
import shutil
import subprocess
import sys
import threading
import time
import os
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Browser, Error as PlaywrightError, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright


BASE_URL = "https://stop-piramida.kz/videos"
DEFAULT_CDP_URL = "http://127.0.0.1:9222"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_METADATA = ROOT / "data" / "metadata" / "all_videos.jsonl"
DEFAULT_OUTPUT_DIR = ROOT / "outputs" / "videos"
DEFAULT_RAW_DIR = ROOT / "data" / "raw"
PAGE_TIMEOUT_MS = 30_000
PLAYLIST_TIMEOUT_MS = 30_000
DOWNLOAD_TIMEOUT_SEC = 30
FFMPEG_TIMEOUT_SEC = 120

REFRESH_CATEGORIES = [
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
_THREAD_LOCAL = threading.local()
_STATUS_LOCK = threading.Lock()


def connect_browser(cdp_url: str = DEFAULT_CDP_URL) -> Browser:
    global _PLAYWRIGHT
    playwright = sync_playwright().start()
    _PLAYWRIGHT = playwright
    try:
        return playwright.chromium.connect_over_cdp(cdp_url)
    except PlaywrightError as exc:
        playwright.stop()
        _PLAYWRIGHT = None
        raise RuntimeError(
            "Chromium CDP is not available.\n"
            f"{browser_start_help()}\n"
            f"Then rerun this script. CDP URL: {cdp_url}"
        ) from exc


def connect_browser_for_thread(cdp_url: str = DEFAULT_CDP_URL) -> tuple[Any, Browser]:
    playwright = sync_playwright().start()
    try:
        return playwright, playwright.chromium.connect_over_cdp(cdp_url)
    except PlaywrightError as exc:
        playwright.stop()
        raise RuntimeError(
            "Chromium CDP is not available for a video worker.\n"
            f"{browser_start_help()}\n"
            f"CDP URL: {cdp_url}"
        ) from exc


def load_category(page: Page, category: str) -> None:
    url = f"{BASE_URL}/{category}"
    print(f"OPEN PAGE: {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
    try:
        page.wait_for_load_state("networkidle", timeout=PAGE_TIMEOUT_MS)
    except PlaywrightTimeoutError:
        pass

    previous_count = -1
    stagnant_clicks = 0
    while True:
        cards_count = page.locator(".videoBoxHover").count()
        stagnant_clicks = stagnant_clicks + 1 if cards_count == previous_count else 0
        previous_count = cards_count

        button = _find_show_more_button(page)
        if button is None or stagnant_clicks >= 2:
            return
        try:
            button.scroll_into_view_if_needed(timeout=5_000)
            button.click(timeout=10_000)
            page.wait_for_load_state("networkidle", timeout=PAGE_TIMEOUT_MS)
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
        """,
        category,
    )

    seen: set[str] = set()
    deduped: list[dict[str, str]] = []
    for item in items:
        normalized = normalize_video(item)
        key = normalized.get("vimeo_id") or normalized.get("page_url")
        if key and key not in seen:
            seen.add(key)
            deduped.append(normalized)
    return deduped


def get_playlist(page: Page, video: dict[str, str], timeout_ms: int = PLAYLIST_TIMEOUT_MS, worker_id: int = 1) -> tuple[dict[str, Any], str]:
    playlist_responses: list[tuple[dict[str, Any], str]] = []
    page_url = video["page_url"]
    logged_playlists: set[str] = set()

    def on_response(response: Any) -> None:
        url = response.url
        if "playlist.json" not in url:
            return
        if url not in logged_playlists:
            logged_playlists.add(url)
            print(f"[W{worker_id}] FOUND PLAYLIST: {url}")
        try:
            playlist = response.json()
            if isinstance(playlist, dict):
                playlist_responses.append((playlist, url))
        except Exception:
            pass

    page.on("response", on_response)
    try:
        with page.expect_response(lambda r: "playlist.json" in r.url, timeout=timeout_ms) as response_info:
            print(f"[W{worker_id}] PLAYLIST WAITING")
            print(f"[W{worker_id}] OPEN PAGE: {page_url}")
            page.goto(page_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
            _start_vimeo_playback(page, video, worker_id=worker_id)
        response = response_info.value
        try:
            playlist = response.json()
        except Exception:
            playlist = None
        if isinstance(playlist, dict):
            return playlist, response.url
        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            if playlist_responses:
                return playlist_responses[-1]
            page.wait_for_timeout(500)
        raise RuntimeError(f"Vimeo playlist response was not a JSON object for {page_url}")
    except PlaywrightTimeoutError as exc:
        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            if playlist_responses:
                return playlist_responses[-1]
            page.wait_for_timeout(500)
        raise RuntimeError(f"Vimeo playlist timeout for {page_url}") from exc
    finally:
        page.remove_listener("response", on_response)


def select_best_stream(playlist: dict[str, Any], playlist_url: str = "") -> dict[str, Any]:
    streams = _coerce_stream_list(playlist.get("video"))
    if not streams:
        streams = _extract_streams_recursively(playlist)
    if not streams:
        raise RuntimeError("Vimeo playlist contains no video streams")

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


def download_segments(stream_bundle: dict[str, Any], work_dir: Path, segment_workers: int = 8) -> dict[str, Any]:
    start = time.perf_counter()
    work_dir.mkdir(parents=True, exist_ok=True)
    video_path = _download_stream_fragments(stream_bundle["video"], work_dir / "video", segment_workers)
    audio = stream_bundle.get("audio")
    audio_path = _download_stream_fragments(audio, work_dir / "audio", segment_workers) if audio else None
    bytes_total = video_path.stat().st_size + (audio_path.stat().st_size if audio_path else 0)
    return {
        "video": video_path,
        "audio": audio_path,
        "seconds": time.perf_counter() - start,
        "bytes": bytes_total,
    }


def merge_segments(downloaded: dict[str, Any], output_path: Path) -> float:
    start = time.perf_counter()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    video_path = downloaded["video"]
    audio_path = downloaded.get("audio")
    if not video_path:
        raise RuntimeError("video fragments were not downloaded")

    tmp_output = output_path.with_name(f"{output_path.stem}.part{output_path.suffix}")
    if audio_path:
        require_ffmpeg()
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
        subprocess.run(command, check=True, timeout=FFMPEG_TIMEOUT_SEC)
    else:
        shutil.copyfile(video_path, tmp_output)

    tmp_output.replace(output_path)
    verify_mp4(output_path)
    return time.perf_counter() - start


def save_metadata(video: dict[str, Any], playlist_info: dict[str, Any], output_path: Path) -> None:
    metadata_path = output_path.with_suffix(".json")
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        **video,
        "mp4_path": str(output_path),
        "playlist_url": playlist_info.get("playlist_url", ""),
        "selected_video": _stream_metadata(playlist_info["video"]),
        "selected_audio": _stream_metadata(playlist_info["audio"]) if playlist_info.get("audio") else None,
    }
    metadata_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    args = _parse_args()
    if args.video_workers < 1:
        raise SystemExit("--video-workers must be >= 1")
    if args.segment_workers < 1:
        raise SystemExit("--segment-workers must be >= 1")
    metadata_path = Path(args.metadata)
    output_dir = Path(args.output_dir)
    status_path = metadata_path.parent / "download_status.jsonl"
    raw_dir = DEFAULT_RAW_DIR

    try:
        if args.doctor:
            run_doctor(args.cdp_url, metadata_path, output_dir)
            return

        if args.refresh:
            videos = refresh_metadata(args, metadata_path)
        else:
            videos = read_metadata(metadata_path)

        if args.list_categories:
            print_categories(videos)
            return
        if args.missing:
            print_missing(videos, output_dir, args.category)
            return
        if args.verify:
            verify_videos(videos, output_dir, args.category)
            return

        if not args.all and not args.category:
            raise SystemExit("Choose --category CATEGORY, --all, --list-categories, --missing, or --verify.")

        selected = select_videos(videos, category=args.category, all_videos=args.all, start_after=args.start_after)
        if args.limit is not None:
            selected = selected[: args.limit]

        if args.dry_run:
            dry_run(selected, output_dir)
            return

        require_writable(output_dir)
        require_ffmpeg()
        download_videos(selected, args, output_dir, raw_dir, status_path)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        raise SystemExit(130)
    except RuntimeError as exc:
        print(f"[!] {exc}", file=sys.stderr)
        raise SystemExit(1)


def refresh_metadata(args: argparse.Namespace, metadata_path: Path) -> list[dict[str, str]]:
    categories = [args.category] if args.category else REFRESH_CATEGORIES
    browser = connect_browser(args.cdp_url)
    try:
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.new_page()
        videos: list[dict[str, str]] = []
        for category in categories:
            print(f"[+] Refreshing category {category}")
            load_category(page, category)
            category_videos = extract_videos(page, category)
            _save_category_index(metadata_path.parent, category, category_videos)
            videos.extend(category_videos)
            print(f"[✓] Indexed {len(category_videos)} videos in {category}")
        _save_all_index(metadata_path, videos)
        print(f"[✓] Saved metadata -> {metadata_path}")
        return videos
    finally:
        close_browser(browser)


def download_videos(
    videos: list[dict[str, str]],
    args: argparse.Namespace,
    output_dir: Path,
    raw_dir: Path,
    status_path: Path,
) -> None:
    total = len(videos)
    if total == 0:
        print("Nothing to download.")
        return

    if args.video_workers <= 1:
        browser = connect_browser(args.cdp_url)
        try:
            context = browser.new_context()
            page = context.new_page()
            try:
                for index, video in enumerate(videos, start=1):
                    process_one_video(
                        worker_id=1,
                        index=index,
                        total=total,
                        page=page,
                        video=video,
                        args=args,
                        output_dir=output_dir,
                        raw_dir=raw_dir,
                        status_path=status_path,
                    )
            finally:
                context.close()
            return
        finally:
            close_browser(browser)

    print(f"[INFO] video-workers={args.video_workers}, segment-workers={args.segment_workers}")
    print("[INFO] If Vimeo, SSL, or timeout errors increase, reduce --video-workers.")
    with ThreadPoolExecutor(max_workers=args.video_workers) as executor:
        futures = []
        for index, video in enumerate(videos, start=1):
            worker_id = ((index - 1) % args.video_workers) + 1
            futures.append(
                executor.submit(
                    process_one_video_in_worker,
                    args.cdp_url,
                    worker_id,
                    index,
                    total,
                    video,
                    args,
                    output_dir,
                    raw_dir,
                    status_path,
                )
            )
        for future in as_completed(futures):
            future.result()


def process_one_video_in_worker(
    cdp_url: str,
    worker_id: int,
    index: int,
    total: int,
    video: dict[str, str],
    args: argparse.Namespace,
    output_dir: Path,
    raw_dir: Path,
    status_path: Path,
) -> None:
    playwright, browser = connect_browser_for_thread(cdp_url)
    context = None
    try:
        context = browser.new_context()
        page = context.new_page()
        process_one_video(worker_id, index, total, page, video, args, output_dir, raw_dir, status_path)
    finally:
        try:
            if context is not None:
                context.close()
            browser.close()
        finally:
            playwright.stop()


def process_one_video(
    worker_id: int,
    index: int,
    total: int,
    page: Page,
    video: dict[str, str],
    args: argparse.Namespace,
    output_dir: Path,
    raw_dir: Path,
    status_path: Path,
) -> None:
    category = video["category"]
    vimeo_id = video["vimeo_id"]
    output_path = output_dir / category / f"{vimeo_id}.mp4"
    prefix = f"[W{worker_id} {index}/{total}]"
    if args.skip_existing and output_path.exists() and output_path.stat().st_size > 0:
        print(f"{prefix} Skipping existing {output_path}")
        _write_status(status_path, video, "ok", output_path, "skipped existing")
        return

    print(f"{prefix} Downloading {category}/{vimeo_id} ...")
    try:
        total_start = time.perf_counter()
        playlist_start = time.perf_counter()
        playlist, playlist_url = get_playlist(page, video, worker_id=worker_id)
        playlist_seconds = time.perf_counter() - playlist_start
        print(f"{prefix} playlist: {playlist_seconds:.1f}s")
        playlist_info = select_best_stream(playlist, playlist_url)
        _save_raw_playlist(raw_dir, category, vimeo_id, playlist)
        work_dir = make_video_work_dir(raw_dir, category, vimeo_id, worker_id)
        downloaded = download_segments(playlist_info, work_dir, args.segment_workers)
        segment_mb = downloaded["bytes"] / 1024 / 1024
        segment_speed = segment_mb / downloaded["seconds"] if downloaded["seconds"] else 0
        print(f"{prefix} segments: {downloaded['seconds']:.1f}s, {segment_mb:.1f} MB, {segment_speed:.2f} MB/s")
        ffmpeg_seconds = merge_segments(downloaded, output_path)
        print(f"{prefix} ffmpeg: {ffmpeg_seconds:.1f}s")
        save_metadata(video, playlist_info, output_path)
        if args.clean_temp_on_success:
            shutil.rmtree(work_dir, ignore_errors=True)
        output_mb = output_path.stat().st_size / 1024 / 1024
        total_seconds = time.perf_counter() - total_start
        total_speed = output_mb / total_seconds if total_seconds else 0
        _write_status(status_path, video, "ok", output_path, "")
        print(f"[W{worker_id} ✓] Saved {output_path} ({output_mb:.1f} MB, avg {total_speed:.2f} MB/s)")
    except Exception as exc:
        if output_path.exists():
            output_path.unlink()
        if "work_dir" in locals():
            preserve_failed_segments(work_dir, raw_dir, category, vimeo_id, args.keep_temp_on_fail)
        _write_status(status_path, video, "failed", output_path, str(exc))
        print(f"[W{worker_id} !] Failed {category}/{vimeo_id}: {exc}")


def read_metadata(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise RuntimeError(
            f"Metadata file not found: {path}\n"
            "Run with --refresh to rebuild metadata, or pass --metadata PATH."
        )
    videos: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                videos.append(normalize_video(json.loads(line)))
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Invalid JSONL metadata at {path}:{line_number}: {exc}") from exc
    if not videos:
        raise RuntimeError(f"Metadata file is empty: {path}")
    return videos


def normalize_video(item: dict[str, Any]) -> dict[str, str]:
    vimeo_url = item.get("vimeo_url") or item.get("vimeo") or ""
    page_url = item.get("page_url") or item.get("url") or ""
    vimeo_id = item.get("vimeo_id") or _extract_vimeo_id(vimeo_url)
    return {
        "category": item.get("category") or "",
        "title": item.get("title") or "",
        "description": item.get("description") or "",
        "page_url": page_url,
        "vimeo_url": vimeo_url,
        "vimeo_id": vimeo_id,
    }


def select_videos(videos: list[dict[str, str]], category: str | None, all_videos: bool, start_after: str | None) -> list[dict[str, str]]:
    selected = videos if all_videos else [video for video in videos if video["category"] == category]
    if category and not selected:
        available = ", ".join(sorted({video["category"] for video in videos}))
        raise RuntimeError(f"Category not found in metadata: {category}\nAvailable categories: {available}")
    return _apply_start_after(selected, start_after)


def print_categories(videos: list[dict[str, str]]) -> None:
    counts = Counter(video["category"] for video in videos)
    for category in sorted(counts):
        print(f"{category}\t{counts[category]}")
    print(f"TOTAL\t{sum(counts.values())}")


def print_missing(videos: list[dict[str, str]], output_dir: Path, category: str | None) -> None:
    selected = [video for video in videos if category is None or video["category"] == category]
    missing = [video for video in selected if not video_path(output_dir, video).exists()]
    for video in missing:
        print(f"{video['category']}\t{video['vimeo_id']}\t{video['title']}")
    print(f"Missing: {len(missing)} / {len(selected)}")


def dry_run(videos: list[dict[str, str]], output_dir: Path) -> None:
    for video in videos:
        exists = video_path(output_dir, video).exists()
        marker = "exists" if exists else "new"
        print(f"{marker}\t{video['category']}\t{video['vimeo_id']}\t{video['title']}")
    print(f"Would process: {len(videos)} videos")


def verify_videos(videos: list[dict[str, str]], output_dir: Path, category: str | None) -> None:
    if not shutil.which("ffprobe"):
        raise RuntimeError("ffprobe not found. Install ffmpeg to use --verify.")
    selected = [video for video in videos if category is None or video["category"] == category]
    checked = 0
    failed = 0
    missing = 0
    for video in selected:
        path = video_path(output_dir, video)
        if not path.exists():
            missing += 1
            print(f"[missing] {path}")
            continue
        result = subprocess.run(
            ["ffprobe", "-v", "error", str(path)],
            text=True,
            capture_output=True,
            timeout=30,
        )
        checked += 1
        if result.returncode:
            failed += 1
            print(f"[failed] {path}: {result.stderr.strip()}")
        else:
            print(f"[ok] {path}")
    print(f"Verify complete: ok={checked - failed}, failed={failed}, missing={missing}")


def require_ffmpeg() -> None:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found. Install ffmpeg and ensure it is available in PATH.")


def require_writable(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
        test_path = path / ".write_test"
        test_path.write_text("ok", encoding="utf-8")
        test_path.unlink()
    except OSError as exc:
        raise RuntimeError(f"No write permission for output directory: {path}") from exc


def make_video_work_dir(raw_dir: Path, category: str, vimeo_id: str, worker_id: int) -> Path:
    timestamp = int(time.time() * 1000)
    path = raw_dir / "segments" / category / f"{vimeo_id}.{os.getpid()}.{worker_id}.{timestamp}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def preserve_failed_segments(work_dir: Path, raw_dir: Path, category: str, vimeo_id: str, keep_temp_on_fail: bool) -> None:
    if not keep_temp_on_fail or not work_dir.exists():
        return
    failed_root = raw_dir / "failed_segments" / category
    failed_root.mkdir(parents=True, exist_ok=True)
    destination = failed_root / f"{vimeo_id}.{work_dir.name}"
    counter = 1
    while destination.exists():
        destination = failed_root / f"{vimeo_id}.{work_dir.name}.{counter}"
        counter += 1
    work_dir.replace(destination)
    print(f"[INFO] Failed segments preserved: {destination}")


def verify_mp4(path: Path) -> None:
    if not shutil.which("ffprobe"):
        raise RuntimeError("ffprobe not found. Install ffmpeg to verify merged mp4 files.")
    result = subprocess.run(
        ["ffprobe", "-v", "error", str(path)],
        text=True,
        capture_output=True,
        timeout=30,
    )
    if result.returncode != 0 or result.stderr.strip():
        message = result.stderr.strip() or f"ffprobe exited with {result.returncode}"
        if path.exists():
            path.unlink()
        raise RuntimeError(f"ffprobe validation failed for {path}: {message}")


def run_doctor(cdp_url: str = DEFAULT_CDP_URL, metadata_path: Path = DEFAULT_METADATA, output_dir: Path = DEFAULT_OUTPUT_DIR) -> bool:
    ok = True
    print("Stop-Piramida downloader environment check")
    print()

    if sys.version_info >= (3, 10):
        print(f"[OK] Python version: {sys.version.split()[0]}")
    else:
        print(f"[FAIL] Python version: {sys.version.split()[0]} (Python 3.10+ recommended)")
        ok = False

    ok &= _doctor_which("ffmpeg", required=True)
    ok &= _doctor_which("ffprobe", required=True)

    browser = find_browser_binary()
    if browser:
        print(f"[OK] Chromium/Chrome found: {browser}")
    else:
        print("[WARN] Chromium/Chrome was not found in PATH or common install locations.")

    try:
        import playwright  # noqa: F401

        print("[OK] Playwright installed")
    except Exception as exc:
        print(f"[FAIL] Playwright import failed: {exc}")
        ok = False

    if check_cdp(cdp_url):
        print(f"[OK] CDP available: {cdp_url}")
    else:
        print(f"[FAIL] CDP not available: {cdp_url}")
        print(f"[INFO] Start browser with:\n{browser_start_help()}")
        ok = False

    if metadata_path.exists():
        print(f"[OK] metadata exists: {metadata_path}")
    else:
        print(f"[FAIL] metadata not found: {metadata_path}")
        print("[INFO] Use --refresh to rebuild metadata if you have browser CDP running.")
        ok = False

    if check_writable(output_dir):
        print(f"[OK] output directory writable: {output_dir}")
    else:
        print(f"[FAIL] output directory is not writable: {output_dir}")
        ok = False

    print()
    print("[OK] Doctor passed" if ok else "[FAIL] Doctor found issues")
    return ok


def _doctor_which(name: str, required: bool) -> bool:
    path = shutil.which(name)
    if path:
        print(f"[OK] {name} found: {path}")
        return True
    status = "FAIL" if required else "WARN"
    print(f"[{status}] {name} not found in PATH")
    return not required


def find_browser_binary() -> str | None:
    candidates = [
        "chromium",
        "chromium-browser",
        "google-chrome",
        "google-chrome-stable",
        "chrome",
        "chrome.exe",
        "msedge",
        "msedge.exe",
    ]
    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return found

    common_paths = [
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
        Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
        Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe",
    ]
    for path in common_paths:
        if path.exists():
            return str(path)
    return None


def check_cdp(cdp_url: str) -> bool:
    global _PLAYWRIGHT
    playwright = sync_playwright().start()
    try:
        browser = playwright.chromium.connect_over_cdp(cdp_url, timeout=3_000)
        browser.close()
        return True
    except Exception:
        return False
    finally:
        playwright.stop()
        _PLAYWRIGHT = None


def check_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        test_path = path / ".write_test"
        test_path.write_text("ok", encoding="utf-8")
        test_path.unlink()
        return True
    except OSError:
        return False


def browser_start_help() -> str:
    return "\n".join(
        [
            "Linux:",
            '  chromium --remote-debugging-port=9222 --user-data-dir="$HOME/.chromium-stop-piramida"',
            "Windows PowerShell:",
            '  chrome.exe --remote-debugging-port=9222 --user-data-dir="$env:USERPROFILE.chromium-stop-piramida"',
            "macOS:",
            '  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=9222 --user-data-dir="$HOME/.chromium-stop-piramida"',
        ]
    )


def close_browser(browser: Browser) -> None:
    try:
        browser.close()
    finally:
        global _PLAYWRIGHT
        if _PLAYWRIGHT:
            _PLAYWRIGHT.stop()
            _PLAYWRIGHT = None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download the stop-piramida.kz video dataset using Playwright and Vimeo playlist.json.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--list-categories", action="store_true", help="show categories and video counts")
    parser.add_argument("--category", help="download or inspect one category")
    parser.add_argument("--all", action="store_true", help="download or inspect all categories")
    parser.add_argument("--refresh", action="store_true", help="re-parse stop-piramida.kz and update metadata")
    parser.add_argument("--limit", type=int, help="download or show only N videos")
    parser.add_argument("--start-after", help="start after this Vimeo id")
    parser.add_argument("--video-workers", type=int, default=1, help="parallel video workers, each with its own Playwright context/page")
    parser.add_argument("--segment-workers", type=int, default=8, help="parallel segment workers per audio/video track")
    parser.add_argument("--keep-temp-on-fail", action=argparse.BooleanOptionalAction, default=True, help="keep failed segment temp directories for debugging")
    parser.add_argument("--clean-temp-on-success", action=argparse.BooleanOptionalAction, default=True, help="delete per-video temp segment directory after successful merge")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="directory for downloaded mp4 files")
    parser.add_argument("--metadata", default=str(DEFAULT_METADATA), help="metadata JSONL path")
    parser.add_argument("--dry-run", action="store_true", help="show what would be downloaded without downloading")
    parser.add_argument("--verify", action="store_true", help="verify local mp4 files with ffprobe")
    parser.add_argument("--missing", action="store_true", help="show videos present in metadata but missing locally")
    parser.add_argument("--doctor", action="store_true", help="check local environment and print setup hints")
    parser.add_argument("--cdp-url", default=DEFAULT_CDP_URL, help="Chromium CDP URL")
    parser.add_argument("--skip-existing", action=argparse.BooleanOptionalAction, default=True, help="skip existing mp4 files")
    return parser.parse_args()


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


def _start_vimeo_playback(page: Page, video: dict[str, str], worker_id: int = 1) -> None:
    vimeo_id = video.get("vimeo_id") or _extract_vimeo_id(video.get("vimeo_url", ""))
    if _log_vimeo_iframe(page, timeout_ms=1_000, vimeo_id=vimeo_id, worker_id=worker_id):
        return

    block = _find_video_block(page, vimeo_id)
    if block is not None:
        print(f"[W{worker_id}] VIDEO BLOCK FOUND")
        try:
            block.scroll_into_view_if_needed(timeout=5_000)
        except Exception:
            pass

        try:
            print(f"[W{worker_id}] CLICK FORCE")
            block.click(timeout=7_000, force=True)
        except Exception:
            try:
                print(f"[W{worker_id}] CLICK JS")
                page.evaluate("(el) => el.click()", block)
            except Exception:
                pass

        if _wait_for_vimeo_iframe(page, vimeo_id, timeout_ms=7_000, worker_id=worker_id):
            return

    _inject_vimeo_iframe(page, vimeo_id, worker_id=worker_id)
    _wait_for_vimeo_iframe(page, vimeo_id, timeout_ms=7_000, worker_id=worker_id)


def _find_video_block(page: Page, vimeo_id: str) -> Any | None:
    selectors = []
    if vimeo_id:
        selectors.extend(
            [
                f".videoBoxHover[data-v-url*='{vimeo_id}']",
                f"[data-v-url*='vimeo.com/{vimeo_id}']",
                f"[data-v-url*='{vimeo_id}']",
            ]
        )
    selectors.extend(
        [
            ".videoBoxHover",
            ".videoBox",
            "[data-v-url*='vimeo.com']",
        ]
    )

    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if locator.count():
                return locator
        except Exception:
            continue
    return None


def _wait_for_vimeo_iframe(page: Page, vimeo_id: str, timeout_ms: int, worker_id: int = 1) -> bool:
    if vimeo_id:
        selector = f"iframe[src*='player.vimeo.com/video/{vimeo_id}']"
    else:
        selector = "iframe[src*='player.vimeo.com']"

    try:
        iframe = page.wait_for_selector(selector, timeout=timeout_ms)
        src = iframe.get_attribute("src") or ""
        print(f"[W{worker_id}] FOUND IFRAME: {src}")
        return True
    except PlaywrightTimeoutError:
        return _log_vimeo_iframe(page, timeout_ms=500, vimeo_id=vimeo_id, worker_id=worker_id)


def _inject_vimeo_iframe(page: Page, vimeo_id: str, worker_id: int = 1) -> None:
    if not vimeo_id:
        return
    iframe_url = f"https://player.vimeo.com/video/{vimeo_id}?color=fdbb03&autoplay=1&app_id=122963"
    page.evaluate(
        """
        (src) => {
          let container = document.querySelector('#unified-player-container');
          if (!container) {
            container = document.createElement('div');
            container.id = 'unified-player-container';
            document.body.prepend(container);
          }
          container.innerHTML = '';
          const iframe = document.createElement('iframe');
          iframe.src = src;
          iframe.allow = 'autoplay; fullscreen; picture-in-picture';
          iframe.setAttribute('allowfullscreen', '');
          iframe.style.width = '960px';
          iframe.style.height = '540px';
          iframe.style.border = '0';
          container.appendChild(iframe);
        }
        """,
        iframe_url,
    )
    print(f"[W{worker_id}] IFRAME INJECTED")


def _log_vimeo_iframe(page: Page, timeout_ms: int, vimeo_id: str = "", worker_id: int = 1) -> bool:
    selector = f"iframe[src*='player.vimeo.com/video/{vimeo_id}']" if vimeo_id else "iframe[src*='vimeo.com']"
    try:
        iframe = page.wait_for_selector(selector, timeout=timeout_ms)
        src = iframe.get_attribute("src") or ""
        print(f"[W{worker_id}] FOUND IFRAME: {src}")
        return True
    except PlaywrightTimeoutError:
        pass

    for frame in page.frames:
        if "vimeo.com" in frame.url and (not vimeo_id or vimeo_id in frame.url):
            print(f"[W{worker_id}] FOUND IFRAME: {frame.url}")
            return True

    print(f"[W{worker_id}] FOUND IFRAME: <none>")
    return False


def _extract_streams_recursively(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if value.get("segments") and (value.get("init_segment") or value.get("init_segment_url")):
            found.append(value)
        for child in value.values():
            found.extend(_extract_streams_recursively(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_extract_streams_recursively(child))
    return found


def _coerce_stream_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        if value.get("segments") and (value.get("init_segment") or value.get("init_segment_url")):
            return [value]
        streams: list[dict[str, Any]] = []
        for child in value.values():
            streams.extend(_coerce_stream_list(child))
        return streams
    return []


def _select_best_audio_stream(playlist: dict[str, Any]) -> dict[str, Any] | None:
    streams = _coerce_stream_list(playlist.get("audio"))
    streams = [item for item in streams if item.get("segments") and (item.get("init_segment") or item.get("init_segment_url"))]
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

    absolute_segments = []
    for segment in segments:
        if isinstance(segment, dict):
            segment_url = segment["url"]
            expected_size = segment.get("size")
        else:
            segment_url = str(segment)
            expected_size = None
        absolute_segments.append(
            {
                "url": urljoin(base_url, segment_url),
                "size": int(expected_size) if expected_size else None,
            }
        )
    segment_urls = [segment["url"] for segment in absolute_segments]
    absolute_downloads = []
    if init_segment_url:
        absolute_downloads.append({"url": init_segment_url, "size": None})
    absolute_downloads.extend(absolute_segments)

    return {
        **stream,
        "init_bytes": init_bytes,
        "init_segment_url": init_segment_url,
        "segment_urls": segment_urls,
        "absolute_segments": absolute_segments,
        "absolute_urls": [segment["url"] for segment in absolute_downloads],
        "absolute_downloads": absolute_downloads,
        "absolute_base_url": base_url,
    }


def _download_stream_fragments(stream: dict[str, Any], target_dir: Path, segment_workers: int) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    output_path = target_dir.with_suffix(".mp4")
    part_path = output_path.with_suffix(".mp4.part")
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://player.vimeo.com/"}
    segment_paths = _download_stream_segments_parallel(stream["absolute_downloads"], target_dir, headers, segment_workers)

    with part_path.open("wb") as out:
        if stream.get("init_bytes"):
            out.write(stream["init_bytes"])
        for fragment_path in segment_paths:
            with fragment_path.open("rb") as fragment:
                shutil.copyfileobj(fragment, out)

    part_path.replace(output_path)
    return output_path


def _download_stream_segments_parallel(
    segments: list[dict[str, Any]],
    target_dir: Path,
    headers: dict[str, str],
    segment_workers: int,
) -> list[Path]:
    if not segments:
        return []
    workers = max(1, segment_workers)
    results: list[Path | None] = [None] * len(segments)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_download_segment, index, segment, target_dir, headers): index
            for index, segment in enumerate(segments)
        }
        for future in as_completed(futures):
            index, path = future.result()
            results[index] = path
    return [path for path in results if path is not None]


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


def _download_segment(index: int, segment: dict[str, Any], target_dir: Path, headers: dict[str, str]) -> tuple[int, Path]:
    url = segment["url"]
    expected_size = segment.get("size")
    path = target_dir / f"{index:06d}.m4s"
    if path.exists() and _segment_size_ok(path, expected_size):
        return index, path
    _download_url(url, path, headers, expected_size=expected_size)
    return index, path


def _download_url(url: str, path: Path, headers: dict[str, str], expected_size: int | None = None, retries: int = 3) -> None:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        part_path = path.with_suffix(f"{path.suffix}.part.{os.getpid()}.{threading.get_ident()}.{attempt}")
        try:
            session = _get_session()
            response = session.get(url, headers=headers, timeout=DOWNLOAD_TIMEOUT_SEC, stream=True)
            response.raise_for_status()
            with part_path.open("wb") as out:
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        out.write(chunk)
            if not part_path.exists() or part_path.stat().st_size == 0:
                raise RuntimeError(f"empty segment temp file: {part_path}")
            if expected_size and part_path.stat().st_size < expected_size:
                raise RuntimeError(
                    f"short segment download: got {part_path.stat().st_size}, expected {expected_size}"
                )
            part_path.replace(path)
            return
        except (requests.RequestException, TimeoutError, RuntimeError, OSError) as exc:
            last_error = exc
            if part_path.exists():
                part_path.unlink()
            if attempt < retries:
                time.sleep(1.5 * attempt)
    raise RuntimeError(f"segment download failed after {retries} retries: {url}: {last_error}")


def _segment_size_ok(path: Path, expected_size: int | None) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    return not expected_size or path.stat().st_size >= expected_size


def _get_session() -> requests.Session:
    session = getattr(_THREAD_LOCAL, "session", None)
    if session is None:
        session = requests.Session()
        _THREAD_LOCAL.session = session
    return session


def _apply_start_after(videos: list[dict[str, str]], start_after: str | None) -> list[dict[str, str]]:
    if not start_after:
        return videos
    for index, video in enumerate(videos):
        if video.get("vimeo_id") == start_after:
            return videos[index + 1 :]
    return videos


def _write_status(status_path: Path, video: dict[str, Any], status: str, file_path: Path | str, error: str) -> None:
    status_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "vimeo_id": video.get("vimeo_id") or _extract_vimeo_id(video.get("vimeo_url", "")),
        "category": video.get("category", ""),
        "status": status,
        "file": str(file_path) if file_path else "",
        "error": error,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with _STATUS_LOCK:
        with status_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _save_category_index(metadata_dir: Path, category: str, videos: list[dict[str, str]]) -> None:
    metadata_dir.mkdir(parents=True, exist_ok=True)
    path = metadata_dir / f"{category}.jsonl"
    with path.open("w", encoding="utf-8") as file:
        for video in videos:
            file.write(json.dumps(video, ensure_ascii=False) + "\n")


def _save_all_index(path: Path, videos: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for video in videos:
            file.write(json.dumps(video, ensure_ascii=False) + "\n")


def _save_raw_playlist(raw_dir: Path, category: str, vimeo_id: str, playlist: dict[str, Any]) -> None:
    path = raw_dir / "playlists" / category / f"{vimeo_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(playlist, ensure_ascii=False, indent=2), encoding="utf-8")


def _stream_metadata(stream: dict[str, Any]) -> dict[str, Any]:
    keys = ("id", "profile", "width", "height", "bitrate", "mime_type", "absolute_base_url")
    return {key: stream.get(key) for key in keys if key in stream}


def _extract_vimeo_id(url: str) -> str:
    parsed = urlparse(url)
    match = re.search(r"/(?:video/)?(\d+)", parsed.path)
    return match.group(1) if match else ""


def video_path(output_dir: Path, video: dict[str, str]) -> Path:
    return output_dir / video["category"] / f"{video['vimeo_id']}.mp4"


if __name__ == "__main__":
    main()
