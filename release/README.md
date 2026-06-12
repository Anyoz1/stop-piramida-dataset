# Stop-Piramida Video Dataset

Dataset of public anti-fraud videos from Stop-Piramida.

- Source: https://stop-piramida.kz/videos
- Videos found: 593
- Videos downloaded: 590
- Missing videos: 3
- Video archive size: 15GB
- Google Drive video archive: https://drive.google.com/drive/folders/1g-rahFj4oRNPTQQgXZv-EQ_I-lexgB20

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

## Release Structure

```text
release/
├── README.md
├── videos.csv
├── missing_videos.txt
├── videos.sha256
├── metadata/
│   ├── all_videos.jsonl
│   └── download_status.jsonl
└── scripts/
    ├── download_videoteca.py
    └── download_videoteca_stable.py
```

## Download Videos

Video files are not stored in GitHub. Download them from Google Drive:

```text
https://drive.google.com/drive/folders/1g-rahFj4oRNPTQQgXZv-EQ_I-lexgB20
```

Expected local layout:

```text
outputs/videos/<category>/<vimeo_id>.mp4
```

## Verify SHA256

After downloading videos into `outputs/videos/`, run:

```bash
sha256sum -c release/videos.sha256
```

## Re-download From Source

Open Chromium with CDP enabled:

```bash
chromium --remote-debugging-port=9222
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Download all videos:

```bash
python scripts/download_videoteca.py --all --segment-workers 8
```

Download one category:

```bash
python scripts/download_videoteca.py --category lzheturizm --segment-workers 8
```

## Google Drive Link

After upload, replace `https://drive.google.com/drive/folders/1g-rahFj4oRNPTQQgXZv-EQ_I-lexgB20` in `README.md` and `release/README.md` with the link saved in:

```text
release/drive_link.txt
```
