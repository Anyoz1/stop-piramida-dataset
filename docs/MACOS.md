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
python scripts/download_videoteca.py --all --segment-workers 8
```
