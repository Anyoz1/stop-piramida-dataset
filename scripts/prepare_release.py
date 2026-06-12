#!/usr/bin/env python3
import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
METADATA_DIR = ROOT / "data" / "metadata"
VIDEOS_DIR = ROOT / "outputs" / "videos"
RELEASE_DIR = ROOT / "release"

DATASET_TITLE = "Stop-Piramida Video Dataset"
SOURCE_URL = "https://stop-piramida.kz/videos"
FOUND_VIDEOS = 593
DOWNLOADED_VIDEOS = 590
MISSING_VIDEOS = 3
VIDEO_SIZE = "15GB"
DRIVE_PLACEHOLDER = "DRIVE_LINK_HERE"

CATEGORY_FILES_SKIP = {"all_videos.jsonl", "download_status.jsonl"}


def main() -> None:
    parse_args()
    videos = collect_videos()
    release_metadata_dir = RELEASE_DIR / "metadata"
    release_scripts_dir = RELEASE_DIR / "scripts"

    release_metadata_dir.mkdir(parents=True, exist_ok=True)
    release_scripts_dir.mkdir(parents=True, exist_ok=True)

    write_all_videos(videos, METADATA_DIR / "all_videos.jsonl")
    write_all_videos(videos, release_metadata_dir / "all_videos.jsonl")
    copy_if_exists(METADATA_DIR / "download_status.jsonl", release_metadata_dir / "download_status.jsonl")
    copy_if_exists(ROOT / "scripts" / "download_videoteca.py", release_scripts_dir / "download_videoteca.py")
    copy_if_exists(ROOT / "scripts" / "download_videoteca_stable.py", release_scripts_dir / "download_videoteca_stable.py")

    missing = find_missing_videos(videos)
    write_videos_csv(videos, RELEASE_DIR / "videos.csv")
    write_missing_videos(missing, RELEASE_DIR / "missing_videos.txt")
    write_sha256(VIDEOS_DIR, RELEASE_DIR / "videos.sha256")
    readme = build_readme(videos)
    (RELEASE_DIR / "README.md").write_text(readme, encoding="utf-8")

    print(f"Release prepared: {RELEASE_DIR.relative_to(ROOT)}")
    print(f"videos.csv rows: {len(videos)}")
    print(f"missing_videos.txt rows: {len(missing)}")
    print(f"sha256 files: {len(list(VIDEOS_DIR.glob('*/*.mp4')))}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare GitHub release metadata for the Stop-Piramida video dataset.")
    return parser.parse_args()


def collect_videos() -> list[dict[str, Any]]:
    videos: list[dict[str, Any]] = []

    for path in sorted(METADATA_DIR.glob("*.jsonl")):
        if path.name in CATEGORY_FILES_SKIP:
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = normalize_video(json.loads(line), path.stem)
            if not (item["vimeo_id"] or item["page_url"]):
                continue
            videos.append(item)

    return videos


def normalize_video(item: dict[str, Any], fallback_category: str) -> dict[str, str]:
    vimeo_url = item.get("vimeo_url") or item.get("vimeo") or ""
    page_url = item.get("page_url") or item.get("url") or ""
    vimeo_id = item.get("vimeo_id") or extract_vimeo_id(vimeo_url)
    category = item.get("category") or fallback_category
    return {
        "category": category,
        "title": item.get("title") or "",
        "description": item.get("description") or "",
        "page_url": page_url,
        "vimeo_url": vimeo_url,
        "vimeo_id": vimeo_id,
    }


def write_all_videos(videos: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for video in videos:
            file.write(json.dumps(video, ensure_ascii=False) + "\n")


def write_videos_csv(videos: list[dict[str, Any]], path: Path) -> None:
    fieldnames = [
        "category",
        "vimeo_id",
        "title",
        "description",
        "page_url",
        "vimeo_url",
        "file",
        "downloaded",
    ]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for video in videos:
            file_path = video_file_path(video)
            writer.writerow(
                {
                    **video,
                    "file": str(file_path.relative_to(ROOT)) if file_path.exists() else "",
                    "downloaded": "yes" if file_path.exists() else "no",
                }
            )


def find_missing_videos(videos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [video for video in videos if not video_file_path(video).exists()]


def write_missing_videos(missing: list[dict[str, Any]], path: Path) -> None:
    with path.open("w", encoding="utf-8") as file:
        for video in missing:
            file.write(
                "\t".join(
                    [
                        video["category"],
                        video["vimeo_id"],
                        video["title"],
                        video["page_url"],
                    ]
                )
                + "\n"
            )


def write_sha256(videos_dir: Path, path: Path) -> None:
    with path.open("w", encoding="utf-8") as file:
        for video_path in sorted(videos_dir.glob("*/*.mp4")):
            digest = sha256_file(video_path)
            file.write(f"{digest}  {video_path.relative_to(ROOT)}\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_readme(videos: list[dict[str, Any]]) -> str:
    categories = sorted({video["category"] for video in videos})
    category_lines = "\n".join(f"- `{category}`" for category in categories)
    return f"""# {DATASET_TITLE}

Dataset of public anti-fraud videos from Stop-Piramida.

- Source: {SOURCE_URL}
- Videos found: {FOUND_VIDEOS}
- Videos downloaded: {DOWNLOADED_VIDEOS}
- Missing videos: {MISSING_VIDEOS}
- Video archive size: {VIDEO_SIZE}
- Google Drive video archive: {DRIVE_PLACEHOLDER}

## Categories

{category_lines}

## Release Structure

```text
release/
├── README.md
├── videos.csv
├── missing_videos.txt
├── videos.sha256
├── metadata/
│   ├── all_videos.jsonl
│   └── download_status.jsonl
└── scripts/
    ├── download_videoteca.py
    └── download_videoteca_stable.py
```

## Download Videos

Video files are not stored in GitHub. Download them from Google Drive:

```text
{DRIVE_PLACEHOLDER}
```

Expected local layout:

```text
outputs/videos/<category>/<vimeo_id>.mp4
```

## Verify SHA256

After downloading videos into `outputs/videos/`, run:

```bash
sha256sum -c release/videos.sha256
```

## Re-download From Source

Open Chromium with CDP enabled:

```bash
chromium --remote-debugging-port=9222
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Download all videos:

```bash
python scripts/download_videoteca.py --all --segment-workers 8
```

Download one category:

```bash
python scripts/download_videoteca.py --category lzheturizm --segment-workers 8
```

## Google Drive Link

After upload, replace `{DRIVE_PLACEHOLDER}` in `README.md` and `release/README.md` with the link saved in:

```text
release/drive_link.txt
```
"""


def copy_if_exists(source: Path, destination: Path) -> None:
    if source.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def video_file_path(video: dict[str, Any]) -> Path:
    return VIDEOS_DIR / video["category"] / f"{video['vimeo_id']}.mp4"


def extract_vimeo_id(url: str) -> str:
    return url.rstrip("/").split("/")[-1] if url else ""


if __name__ == "__main__":
    main()
