# yt-scraper — Notes

Personal notes for the YouTube scraper used in this project.

## Overview

This small scraper collects metadata / videos for VTuber karaoke search experiments. Keep this file for quick setup and usage tips.

## Environment

-   Conda environment name: `vks-yt-scraper`
-   Python: `3.14` (if `3.14` isn't available on your platform, use `3.11` or the latest supported Python 3.x in your conda channel)

## Quick setup

Open PowerShell and run:

```pwsh
conda create -n vks-yt-scraper python=3.14 -y
conda activate vks-yt-scraper
# If you have a requirements file, install it; otherwise install the packages you need
pip install -r requirements.txt
```

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
        "is_pinned": False
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
