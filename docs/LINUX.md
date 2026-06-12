# Linux Setup

## Ubuntu/Debian

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git ffmpeg chromium-browser
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
python scripts/download_videoteca.py --all --segment-workers 8
python scripts/download_videoteca.py --missing
python scripts/download_videoteca.py --verify
```
