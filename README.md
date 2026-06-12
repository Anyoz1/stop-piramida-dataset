# Stop-Piramida Video Dataset Downloader

Metadata and a cross-platform downloader for 593 public videos from Stop-Piramida.kz.

The videos are not stored in this GitHub repository. Users download the videos locally with the included Playwright-based downloader.

## Dataset Stats

- Metadata records: 593
- Downloaded locally by maintainer: 590
- Missing known: 3
- Source: https://stop-piramida.kz/videos

## Requirements

- Python 3.10+
- Chromium or Google Chrome
- `ffmpeg` and `ffprobe`

Platform-specific setup:

- [Windows](docs/WINDOWS.md)
- [Linux](docs/LINUX.md)
- [macOS](docs/MACOS.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Dataset schema](docs/DATASET_SCHEMA.md)

## Quick Start

Clone and install:

```bash
git clone <REPO_URL>
cd stop-piramida-dataset
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell activation:

```powershell
.\.venv\Scripts\Activate.ps1
```

Check your environment:

```bash
python scripts/download_videoteca.py --doctor
```

Start Chrome/Chromium with CDP enabled.

Linux:

```bash
chromium --remote-debugging-port=9222 --user-data-dir="$HOME/.chromium-stop-piramida"
```

Windows PowerShell:

```powershell
chrome.exe --remote-debugging-port=9222 --user-data-dir="$env:USERPROFILE.chromium-stop-piramida"
```

macOS:

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=9222 --user-data-dir="$HOME/.chromium-stop-piramida"
```

In another terminal, list categories:

```bash
python scripts/download_videoteca.py --list-categories
```

Download two videos from one category:

```bash
python scripts/download_videoteca.py --category lzheturizm --limit 2
```

## Full Download

```bash
python scripts/download_videoteca.py --all --segment-workers 8
```

Videos are saved to:

```text
outputs/videos/<category>/<vimeo_id>.mp4
```

Existing MP4 files are skipped by default, so rerunning the command resumes the download.

## Useful Commands

Dry run:

```bash
python scripts/download_videoteca.py --dry-run --category fishing --limit 3
```

Show missing local videos:

```bash
python scripts/download_videoteca.py --missing
```

Verify downloaded MP4 files:

```bash
python scripts/download_videoteca.py --verify
```

Use a custom output directory:

```bash
python scripts/download_videoteca.py --all --output-dir outputs/videos
```

Resume after a Vimeo ID:

```bash
python scripts/download_videoteca.py --all --start-after 1184398747
```

## Refresh Metadata

By default, the downloader reads:

```text
data/metadata/all_videos.jsonl
```

It does not re-parse the website unless you ask for it.

Refresh all metadata:

```bash
python scripts/download_videoteca.py --refresh --all
```

Refresh one category:

```bash
python scripts/download_videoteca.py --refresh --category fishing
```

## How It Works

The downloader does not use `yt-dlp`. It opens each Stop-Piramida `page_url`, starts the embedded Vimeo player, captures Vimeo `playlist.json`, downloads DASH video/audio segments, handles base64 `init_segment`, and merges tracks with `ffmpeg`.

## Release Files

The `release/` directory contains:

- `videos.csv`
- `missing_videos.txt`
- `videos.sha256`
- copied metadata and downloader scripts

If you downloaded the maintainer archive, verify checksums:

```bash
sha256sum -c release/videos.sha256
```
