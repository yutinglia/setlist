# yt-scraper — Notes

Personal notes for the YouTube scrapers under `services/yt_scraper/`.

## Overview

yt-dlp wrappers collect channel metadata, video lists, and top comments for VTuber karaoke experiments. Prefer the **Dev Container** (Python 3.12) over ad-hoc conda when possible — see repo [README.md](../README.md).

## Environment

| Option | Detail |
|--------|--------|
| Dev Container | Python **3.12** (recommended) |
| Local / conda | Python **3.11–3.12** recommended; avoid bleeding-edge versions unless you need them |
| Runtime deps | `pip install -r requirements.txt` from `data_updater/` |
| Dev/test deps | `pip install -r requirements-dev.txt` |

```bash
# Local example (conda)
conda create -n vks-yt-scraper python=3.12 -y
conda activate vks-yt-scraper
cd data_updater
pip install -r requirements-dev.txt
```

Manual scratch script (not a real test suite): `services/yt_scraper/test.py`.

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

## Bumping yt-dlp

YouTube extractors break often. After a scrape failure:

```bash
cd data_updater
pip install -U yt-dlp
# then pin the new version in requirements.txt
```
