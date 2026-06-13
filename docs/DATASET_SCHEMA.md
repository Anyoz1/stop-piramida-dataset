# Dataset Schema

This repository is a reproducible video dataset package. GitHub stores the dataset index, schema, scripts, documentation, and release descriptors. MP4 files are reconstructed locally and are not committed.

## Dataset Layers

Metadata layer:

```text
data/metadata/
```

This layer is committed to GitHub and is the main index for analysis and recovery.

Media layer:

```text
outputs/videos/<category>/<vimeo_id>.mp4
```

This layer contains local downloaded videos. It is not committed to GitHub.

Sidecar metadata layer:

```text
outputs/videos/<category>/<vimeo_id>.json
```

These files are local technical metadata for downloaded videos.

Raw / temporary layer:

```text
data/raw/segments/
data/raw/failed_segments/
```

This layer contains temporary segments, cache files, and failed debug artifacts. It is not part of the final dataset.

Release layer:

```text
release/
```

This layer contains CSV exports, missing-video lists, checksums, copied metadata, copied scripts, and external storage links.

## `data/metadata/all_videos.jsonl`

Canonical source of truth for the dataset.

One JSON object per line equals one video. Programmatic analysis should start from this file.

Canonical fields:

- `category`: Stop-Piramida category slug. This also defines the local media directory.
- `title`: video title from the site.
- `description`: video description from the site.
- `page_url`: Stop-Piramida video page URL.
- `vimeo_url`: Vimeo URL as exposed by the site metadata.
- `vimeo_id`: Vimeo numeric ID.

Derived semantics:

- Source collection: Stop-Piramida.kz videotheque.
- Expected local MP4 path: `outputs/videos/<category>/<vimeo_id>.mp4`.
- Expected sidecar path: `outputs/videos/<category>/<vimeo_id>.json`.

Expected local media path:

```text
outputs/videos/<category>/<vimeo_id>.mp4
```

Example category mapping:

```text
data/metadata/fishing.jsonl
outputs/videos/fishing/<vimeo_id>.mp4

data/metadata/dropperstvo.jsonl
outputs/videos/dropperstvo/<vimeo_id>.mp4
```

## `data/metadata/all_videos.json`

JSON array form of the canonical metadata index. Use `all_videos.jsonl` for streaming and line-oriented processing.

## `data/metadata/<category>.jsonl`

Category-specific metadata subset. Each line follows the same record structure as `all_videos.jsonl`.

The `category` value corresponds to both the Stop-Piramida videotheque section and the local output directory.

## `data/metadata/download_status.jsonl`

Append-only local downloader status log.

Fields:

- `vimeo_id`
- `category`
- `status`: `ok` or `failed`
- `file`: local output path.
- `error`: error text or empty string.
- `timestamp`: UTC ISO timestamp.

## `release/videos.csv`

CSV table derived from the canonical metadata index and local media status.

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

Downloaded videos are stored locally and are not committed to GitHub:

```text
outputs/videos/<category>/<vimeo_id>.mp4
outputs/videos/<category>/<vimeo_id>.json
```

The JSON file beside each MP4 stores local technical metadata for that video, such as source page, Vimeo ID, category, output path, status, and available size or validation information.

## `release/missing_videos.txt`

Tab-separated list of known metadata records that were not present in the maintainer's local MP4 archive at release time. These records still exist in `all_videos.jsonl`; they are missing only from the local media layer used to build the release.

Fields:

```text
category    vimeo_id    title    page_url
```

## `release/videos.sha256`

SHA256 checksums for released local MP4 files. Use this file to validate a downloaded media archive:

```bash
sha256sum -c release/videos.sha256
```

On platforms without `sha256sum`, use an equivalent SHA256 verification tool.

## `release/metadata/`

Copied metadata snapshot used for release packaging.

## `release/scripts/`

Copied scripts snapshot used for release packaging.

## `release/drive_link.txt`

Optional external storage link for a released media archive.
