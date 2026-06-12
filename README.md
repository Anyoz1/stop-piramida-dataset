# Stop-Piramida Video Dataset

Dataset of public anti-fraud videos from Stop-Piramida.

- Source: https://stop-piramida.kz/videos
- Videos found: 593
- Videos downloaded: 590
- Missing videos: 3
- Video archive size: 15GB
- Google Drive video archive: DRIVE_LINK_HERE

## Categories

- `dropperstvo`
- `fejkovyie-vyiplatyi`
- `finansovyie-piramidyi`
- `fishing`
- `kriptoriski`
- `lzhe-kredityi`
- `lzheprodavczyi`
- `lzheturizm`
- `lzhexalyal`
- `lzheyuristyi`
- `lzhezarabotok`
- `rabota-za-graniczej`
- `riski-v-setevom-marketinge`
- `roditelyam-na-zametku`
- `romanticheskoe-moshennichestvo`
- `stop-mfo`
- `telefonnoe-moshennichestvo`

## Repository Structure

```text
data/
  metadata/
    all_videos.jsonl
    download_status.jsonl
release/
  README.md
  videos.csv
  missing_videos.txt
  videos.sha256
  metadata/
    all_videos.jsonl
    download_status.jsonl
  scripts/
    download_videoteca.py
    download_videoteca_stable.py
scripts/
  download_videoteca.py
  download_videoteca_stable.py
```

Video files are not stored in GitHub. Download them from Google Drive:

```text
DRIVE_LINK_HERE
```

Expected local video layout after download:

```text
outputs/videos/<category>/<vimeo_id>.mp4
```

## Verify SHA256

After downloading videos into `outputs/videos/`, verify checksums:

```bash
sha256sum -c release/videos.sha256
```

## Download Videos Again

Use an already opened Chromium with CDP enabled:

```bash
chromium --remote-debugging-port=9222
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Download one category:

```bash
python scripts/download_videoteca.py --category lzheturizm --segment-workers 8
```

Download all categories:

```bash
python scripts/download_videoteca.py --all --segment-workers 8
```

Resume options:

```bash
python scripts/download_videoteca.py --all --limit 50 --start-after 1184398747 --segment-workers 8
```

## Google Drive Upload

1. Open Google Cloud Console.
2. Create or select a project.
3. Enable Google Drive API.
4. Go to APIs & Services -> Credentials.
5. Create OAuth client ID credentials for a Desktop app.
6. Download the JSON credentials file.
7. Save it in the project root as `client_secrets.json`.

Upload videos:

```bash
python scripts/upload_drive.py
```

The uploader creates a Drive folder named `Stop-Piramida Video Dataset`, skips already uploaded files by name and size, and writes the folder link to:

```text
release/drive_link.txt
```

After upload, replace `DRIVE_LINK_HERE` in `README.md` and `release/README.md` with the generated link.

## Prepare Release

Generate release metadata:

```bash
python scripts/prepare_release.py
```

## GitHub Publish Commands

```bash
git init
git add README.md requirements.txt scripts data/metadata release .gitignore
git commit -m "Add Stop-Piramida video dataset metadata and downloader"
git branch -M main
git remote add origin <REPO_URL>
git push -u origin main
```
