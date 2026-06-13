# Stop-Piramida Video Dataset Package

Reproducible video dataset package for anti-fraud, media monitoring, and evidence-oriented analysis tasks based on 593 public videos from Stop-Piramida.kz.

The videos are not stored in this GitHub repository. GitHub stores the dataset index, schema, release descriptors, documentation, and recovery scripts. Users can reconstruct the local media layer from metadata with the included downloader.

## Dataset Stats

- Metadata records: 593
- Downloaded locally by maintainer: 590
- Missing known: 3
- Source: https://stop-piramida.kz/videos

## Dataset Architecture

The dataset is organized as a reproducible package with separate layers.

### Dataset Layers

Metadata layer:

```text
data/metadata/
```

This is the primary dataset index and is stored in GitHub. The canonical file is:

```text
data/metadata/all_videos.jsonl
```

Additional metadata files include:

```text
data/metadata/all_videos.json
data/metadata/download_status.jsonl
data/metadata/<category>.jsonl
```

Media layer:

```text
outputs/videos/<category>/<vimeo_id>.mp4
```

These are the final downloaded videos. They are not stored in GitHub because of size. Any user can reconstruct this layer locally from the metadata layer.

Sidecar metadata layer:

```text
outputs/videos/<category>/<vimeo_id>.json
```

These local JSON files describe a specific downloaded video, including its source page, Vimeo ID, category, output path, status, and available technical checks such as size or validation information.

Raw / temporary layer:

```text
data/raw/segments/
data/raw/failed_segments/
```

This layer contains intermediate DASH segments, cache files, and failed debug artifacts. It is not part of the final dataset and is not pushed to GitHub.

Release layer:

```text
release/
```

This layer is used for publishing or transferring the dataset package. It contains:

```text
release/videos.csv
release/missing_videos.txt
release/videos.sha256
release/metadata/
release/scripts/
release/drive_link.txt
```

### Canonical Dataset Index

The canonical source of truth is:

```text
data/metadata/all_videos.jsonl
```

One line equals one video. Each record describes the category, Vimeo ID, title, source page URL, and Vimeo URL. The source is Stop-Piramida.kz, and the expected local video path is derived from `category` and `vimeo_id`. Programmatic analysis should start from this JSONL file.

### Category Structure

Categories correspond to Stop-Piramida videotheque sections. Metadata and local videos use the same category-based structure:

```text
data/metadata/fishing.jsonl
outputs/videos/fishing/<vimeo_id>.mp4

data/metadata/dropperstvo.jsonl
outputs/videos/dropperstvo/<vimeo_id>.mp4
```

### Dataset Reproducibility

GitHub stores metadata, schema, scripts, documentation, and release descriptors. GitHub does not store MP4 files. This keeps the repository small while allowing any user to clone it and restore the media layer locally.

### Expected Local Structure

```text
stop-piramida-dataset/
├── data/
│   ├── metadata/
│   │   ├── all_videos.jsonl
│   │   ├── all_videos.json
│   │   ├── download_status.jsonl
│   │   └── <category>.jsonl
│   └── raw/
│       ├── segments/
│       └── failed_segments/
├── outputs/
│   └── videos/
│       └── <category>/
│           ├── <vimeo_id>.mp4
│           └── <vimeo_id>.json
├── docs/
│   └── DATASET_SCHEMA.md
├── release/
│   ├── videos.csv
│   ├── missing_videos.txt
│   ├── videos.sha256
│   ├── drive_link.txt
│   ├── metadata/
│   └── scripts/
└── scripts/
```

### Intended Downstream Use

This dataset is intended for:

- Whisper ASR / speech-to-text
- OCR on video frames
- Entity extraction: phones, URLs, Telegram usernames, domains, promo codes, amounts, crypto wallets
- Fraud scenario detection
- Media monitoring
- Anti-fraud evidence reports

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

Temporary and failed download artifacts are kept under `data/raw/`, which is excluded from GitHub and is not part of the final dataset package.

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

## Media Layer Recovery

The downloader is included only as a recovery mechanism for the media layer. It reads the canonical metadata index and writes local MP4 files under `outputs/videos/<category>/`.

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
