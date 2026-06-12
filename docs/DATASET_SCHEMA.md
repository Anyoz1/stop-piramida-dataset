# Dataset Schema

## `data/metadata/all_videos.jsonl`

One JSON object per video card.

Fields:

- `category`: Stop-Piramida category slug.
- `title`: video title from the site.
- `description`: video description from the site.
- `page_url`: Stop-Piramida video page URL.
- `vimeo_url`: Vimeo URL as exposed by the site metadata.
- `vimeo_id`: Vimeo numeric ID.

## `release/videos.csv`

CSV table derived from metadata.

Fields:

- `category`
- `vimeo_id`
- `title`
- `description`
- `page_url`
- `vimeo_url`
- `file`: expected local MP4 path when present.
- `downloaded`: `yes` or `no`.

## `outputs/videos/`

Downloaded videos are stored locally and are not committed to GitHub.

```text
outputs/videos/<category>/<vimeo_id>.mp4
outputs/videos/<category>/<vimeo_id>.json
```

The JSON file beside each MP4 stores selected stream metadata and the captured Vimeo playlist URL.

## `release/missing_videos.txt`

Tab-separated list of known metadata records that were not present in the maintainer's local MP4 archive at release time.

Fields:

```text
category    vimeo_id    title    page_url
```

## `data/metadata/download_status.jsonl`

Append-only downloader status log.

Fields:

- `vimeo_id`
- `category`
- `status`: `ok` or `failed`
- `file`: local output path.
- `error`: error text or empty string.
- `timestamp`: UTC ISO timestamp.
