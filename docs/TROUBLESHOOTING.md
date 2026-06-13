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

For parallel downloads, reduce video-level parallelism first:

```bash
python -u scripts/download_videoteca.py --all --video-workers 1 --segment-workers 8
```

## Connection Reset By Peer

This usually means the network or Vimeo CDN is unhappy with the current concurrency. Reduce parallelism:

```bash
python -u scripts/download_videoteca.py --all --video-workers 1 --segment-workers 4
```

## Failed Segment

Segments are downloaded into `.part` files and checked before atomic rename. If a segment fails, the downloader does not run `ffmpeg` for that video.

Failed temp directories are preserved under:

```text
data/raw/failed_segments/<category>/<vimeo_id>...
```

## Download Is Slow

Increase segment workers carefully:

```bash
python -u scripts/download_videoteca.py --all --video-workers 2 --segment-workers 4
```

If the network becomes unstable, reduce video workers first:

```bash
python -u scripts/download_videoteca.py --all --video-workers 1 --segment-workers 4
```

## Broken MP4

Verify files:

```bash
python scripts/download_videoteca.py --verify
```

Delete the broken file and rerun the same command. Existing valid files are skipped by default.

The downloader also runs `ffprobe -v error` after `ffmpeg`; if the merged MP4 is invalid, it is treated as failed and removed.

## Headless Server

Use Xvfb plus Chrome CDP:

```bash
xvfb-run -a google-chrome \
  --no-sandbox \
  --remote-debugging-address=127.0.0.1 \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/.chromium-stop-piramida"
```

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

## Do Not Commit Large Or Secret Files

Do not push:

- `outputs/videos`
- `data/raw`
- `.mp4`
- `.env`
- token or credential files
