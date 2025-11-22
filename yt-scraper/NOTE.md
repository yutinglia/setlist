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
