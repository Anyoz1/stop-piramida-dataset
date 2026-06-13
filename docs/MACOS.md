# macOS Setup

## Install Homebrew

Install Homebrew from:

https://brew.sh/

## Install Dependencies

```bash
brew install python git ffmpeg
brew install --cask google-chrome
```

Check:

```bash
python3 --version
ffmpeg -version
ffprobe -version
```

## Create Virtual Environment

```bash
git clone <REPO_URL>
cd stop-piramida-dataset
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Start Chrome With CDP

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=9222 --user-data-dir="$HOME/.chromium-stop-piramida"
```

Keep this browser open while downloading.

## Downloader Commands

```bash
python scripts/download_videoteca.py --doctor
python scripts/download_videoteca.py --list-categories
python scripts/download_videoteca.py --category lzheturizm --limit 2
python -u scripts/download_videoteca.py --all --video-workers 1 --segment-workers 8
python -u scripts/download_videoteca.py --all --video-workers 2 --segment-workers 4
```

`--video-workers` controls parallel videos. `--segment-workers` controls parallel DASH segments inside one video. If Vimeo timeout, SSL, or connection reset errors increase, reduce `--video-workers`.
