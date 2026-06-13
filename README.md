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
python scripts/download_videoteca.py --list-categories
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

Stable mode, recommended for first runs and unreliable servers:

```bash
python -u scripts/download_videoteca.py --all --video-workers 1 --segment-workers 8
```

Faster mode, recommended after the stable mode works:

```bash
python -u scripts/download_videoteca.py --all --video-workers 2 --segment-workers 4
```

Videos are saved to:

```text
outputs/videos/<category>/<vimeo_id>.mp4
```

Existing MP4 files are skipped by default, so rerunning the command resumes the download.

### Parallelism

- `--video-workers` controls how many videos are processed at the same time.
- `--segment-workers` controls how many DASH segments are downloaded in parallel inside one video.
- Reliability is more important than peak speed. If Vimeo playlist timeouts, SSL errors, connection resets, or failed segments increase, reduce `--video-workers` first.

Each video uses a unique temp directory:

```text
data/raw/segments/<category>/<vimeo_id>.<pid>.<worker_id>.<timestamp>/
```

Segments are downloaded into `.part` files, checked, and atomically renamed. If a segment fails, `ffmpeg` is not started for that video. After `ffmpeg`, the final MP4 is checked with `ffprobe -v error`. Failed temp directories are preserved under:

```text
data/raw/failed_segments/<category>/<vimeo_id>...
```

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

## Linux Server / Headless Chrome

On a server, run Chrome through Xvfb and expose CDP only on localhost:

```bash
xvfb-run -a google-chrome \
  --no-sandbox \
  --remote-debugging-address=127.0.0.1 \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/.chromium-stop-piramida"
```

Run the downloader in the background:

```bash
nohup python -u scripts/download_videoteca.py \
  --all \
  --video-workers 2 \
  --segment-workers 4 \
  > download_all.log 2>&1 &
```

Monitor progress:

```bash
tail -f download_all.log
```

```bash
TERM=xterm watch -n 60 '
find outputs/videos -name "*.mp4" | wc -l
du -sh outputs/videos
'
```

## After Download

Verify the local archive:

```bash
python scripts/download_videoteca.py --verify
python scripts/download_videoteca.py --missing
du -sh outputs/videos
find outputs/videos -name "*.mp4" | wc -l
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

## Troubleshooting

- `Vimeo playlist timeout`: reduce `--video-workers`, then retry. Existing MP4 files are skipped.
- `Connection reset by peer`: reduce parallelism, especially `--video-workers`.
- Failed segment: the downloader should not run `ffmpeg` for that video; failed temp data is kept under `data/raw/failed_segments/`.
- `ffprobe` error: the merged MP4 is treated as failed and removed.
- Headless server: use `xvfb-run` plus Chrome CDP as shown above.
- Do not push `outputs/videos`, `data/raw`, `.mp4`, `.env`, or token files to GitHub.

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
