# Linux Setup

## Ubuntu/Debian

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git ffmpeg chromium-browser xvfb
```

Some Ubuntu versions provide Chromium through Snap. If `chromium-browser` is not available, install Google Chrome or your distribution's Chromium package.

## Arch Linux

```bash
sudo pacman -Syu
sudo pacman -S python python-pip git ffmpeg chromium
```

## Create Virtual Environment

```bash
git clone <REPO_URL>
cd stop-piramida-dataset
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Start Chromium With CDP

```bash
chromium --remote-debugging-port=9222 --user-data-dir="$HOME/.chromium-stop-piramida"
```

Keep this browser open while downloading.

## Downloader Commands

```bash
python scripts/download_videoteca.py --doctor
python scripts/download_videoteca.py --list-categories
python scripts/download_videoteca.py --category fishing --limit 3
python -u scripts/download_videoteca.py --all --video-workers 1 --segment-workers 8
python -u scripts/download_videoteca.py --all --video-workers 2 --segment-workers 4
python scripts/download_videoteca.py --missing
python scripts/download_videoteca.py --verify
```

## Headless Server

Run Chrome through Xvfb:

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

Monitor:

```bash
tail -f download_all.log
```

```bash
TERM=xterm watch -n 60 '
find outputs/videos -name "*.mp4" | wc -l
du -sh outputs/videos
'
```

If Vimeo timeouts, SSL errors, or connection resets increase, reduce `--video-workers` first.
