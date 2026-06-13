# Windows Setup

## Install Python

Install Python 3.10 or newer from:

https://www.python.org/downloads/windows/

During installation, enable `Add python.exe to PATH`.

Check:

```powershell
python --version
```

## Install Git

Install Git for Windows:

https://git-scm.com/download/win

Check:

```powershell
git --version
```

## Install Chrome

Install Google Chrome:

https://www.google.com/chrome/

## Install ffmpeg

Install ffmpeg with winget:

```powershell
winget install Gyan.FFmpeg
```

Restart PowerShell and check:

```powershell
ffmpeg -version
ffprobe -version
```

## Create Virtual Environment

```powershell
git clone <REPO_URL>
cd stop-piramida-dataset
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Start Chrome With Remote Debugging

Close existing Chrome windows first, then run:

```powershell
chrome.exe --remote-debugging-port=9222 --user-data-dir="$env:USERPROFILE.chromium-stop-piramida"
```

Log in if Chrome asks. Keep this browser open while downloading.

## Download One Category

In a second PowerShell window:

```powershell
.\.venv\Scripts\Activate.ps1
python scripts/download_videoteca.py --doctor
python scripts/download_videoteca.py --list-categories
python scripts/download_videoteca.py --category lzheturizm --limit 2
python -u scripts/download_videoteca.py --all --video-workers 1 --segment-workers 8
python -u scripts/download_videoteca.py --all --video-workers 2 --segment-workers 4
```

`--video-workers` controls parallel videos. `--segment-workers` controls parallel DASH segments inside one video. If Vimeo timeout, SSL, or connection reset errors increase, reduce `--video-workers`.
