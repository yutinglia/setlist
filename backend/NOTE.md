# YouTube scraper notes

[Project README](../README.md) ·
[繁體中文 README](../README.zh-Hant.md)

Implementation notes for the YouTube wrappers under `services/yt_scraper/`.

## Overview

yt-dlp wrappers collect channel metadata, bounded video-list pages, full video
metadata, and top comments for the Setlist pipeline. Prefer the **Dev
Container** (Python 3.12) over an ad-hoc conda environment.

All yt-dlp wrappers are synchronous. Call them from async application code with
`asyncio.to_thread` while holding the shared YouTube operation lock. Do not
bypass updater caps, jitter, block detection, or the persisted cooldown.

## Environment

| Option | Detail |
|--------|--------|
| Dev Container | Python **3.12** (recommended) |
| Local / conda | Python **3.11–3.12** recommended; avoid bleeding-edge versions unless you need them |
| Runtime deps | `pip install -r requirements.txt` from `backend/` |
| Dev/test deps | `pip install -r requirements-dev.txt` |

```bash
# Local example (conda)
conda create -n vks-yt-scraper python=3.12 -y
conda activate vks-yt-scraper
cd backend
pip install -r requirements-dev.txt
```

`services/yt_scraper/test.py` is a manual scratch script with known stale
assumptions; it is not part of pytest or CI.

## YouTube comment dict structure

```python
[
    {
        "id": "",
        "parent": "root",
        "text": "",
        "like_count": 0,
        "author_id": "",
        "author": "",
        "author_thumbnail": "",
        "author_is_uploader": False,
        "author_is_verified": False,
        "author_url": "",
        "is_favorited": False,
        "_time_text": "",
        "timestamp": 0,
        "is_pinned": False,
    },
]
```

## YouTube video list dict structure

```python
# channel info
dict_keys(['id', 'channel', 'channel_id', 'title', 'availability', 'channel_follower_count', 'description', 'tags', 'thumbnails', 'uploader_id', 'uploader_url', 'modified_date', 'view_count',
'playlist_count', 'uploader', 'channel_url', '_type', 'entries', 'webpage_url', 'original_url',
'webpage_url_basename', 'webpage_url_domain', 'extractor', 'extractor_key', 'release_year', 'requested_entries', 'epoch'])

# playlist video entry
dict_keys(['id', 'channel', 'channel_id', 'title', 'availability', 'channel_follower_count', 'description', 'tags', 'thumbnails', 'uploader_id', 'uploader_url', 'modified_date', 'view_count',
'playlist_count', 'uploader', 'channel_url', '_type', 'entries', 'extractor_key', 'extractor', 'webpage_url', '__x_forwarded_for_ip', 'release_year', 'epoch'])

# video info entry
dict_keys(['_type', 'ie_key', 'id', 'url', 'title', 'description', 'duration', 'channel_id', 'channel', 'channel_url', 'uploader', 'uploader_id', 'uploader_url', 'thumbnails', 'timestamp', 'release_timestamp', 'availability', 'view_count', 'live_status', 'channel_is_verified', '__x_forwarded_for_ip'])
```

These keys are observational examples, not a stable yt-dlp contract. Extractors
can add, remove, or change fields without notice.

## Snapshot storage policy

- Flat channel-list observations are stored in `videos.raw_data`.
- Rich full-video observations are stored separately in
  `videos.metadata_raw_data`.
- Each snapshot records source, capture time, schema version, and why fields
  were dropped.
- Stable unknown extractor fields may be retained within the 256 KiB
  record / 64 KiB field bounds.
- Volatile playback formats, signed URLs, request headers, captions,
  subtitles, and comments are excluded.
- Comments use their own analysis snapshot.
- A sparse list refresh must never overwrite richer full metadata.
- Exact upload dates may replace approximate list dates; approximate data must
  never downgrade an exact date.

Use `utils.ytdlp_snapshot` for this policy. Do not shallow-merge sparse and rich
payloads.

## Bumping yt-dlp

YouTube extractors break often. The runtime pin is currently maintained in
`requirements.txt` (currently `yt-dlp==2026.7.4`). After confirming that a
failure is extractor-related:

```bash
cd backend
pip install -U yt-dlp
# reproduce the scrape, then pin the verified version in requirements.txt
python -m pytest
```

Also run the one-shot updater against a non-production development database and
confirm that block-like failures still trigger the normal cooldown. Do not
commit cookies, browser profiles, proxy credentials, signed playback URLs, or
raw secrets captured during debugging.
