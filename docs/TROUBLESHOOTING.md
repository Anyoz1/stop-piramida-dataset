# Troubleshooting

## CDP Connection Refused

The downloader controls an already opened browser through Chrome DevTools Protocol.

Start the browser first:

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

Then run:

```bash
python scripts/download_videoteca.py --doctor
```

## ffmpeg Not Found

Install ffmpeg and ensure `ffmpeg` and `ffprobe` are available in `PATH`.

Check:

```bash
ffmpeg -version
ffprobe -version
```

## Metadata Not Found

The default metadata path is:

```text
data/metadata/all_videos.jsonl
```

If it is missing, rebuild it:

```bash
python scripts/download_videoteca.py --refresh --all
```

## Vimeo Playlist Timeout

The script opens the Stop-Piramida page and waits for Vimeo `playlist.json`.

Try:

```bash
python scripts/download_videoteca.py --category <category> --limit 1
```

If it still fails, check that the browser can open the video page manually and that network access to Vimeo is not blocked.

## Download Is Slow

Increase segment workers carefully:

```bash
python scripts/download_videoteca.py --all --segment-workers 12
```

If the network becomes unstable, reduce it:

```bash
python scripts/download_videoteca.py --all --segment-workers 4
```

## Broken MP4

Verify files:

```bash
python scripts/download_videoteca.py --verify
```

Delete the broken file and rerun the same command. Existing valid files are skipped by default.

## How To Resume

Rerun the downloader. Existing MP4 files are skipped:

```bash
python scripts/download_videoteca.py --all
```

Resume after a specific Vimeo ID:

```bash
python scripts/download_videoteca.py --all --start-after 1184398747
```

## How To Show Missing Files

```bash
python scripts/download_videoteca.py --missing
```
