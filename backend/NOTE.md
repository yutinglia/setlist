# YouTube scraper notes

[Project README](../README.md) ·
[繁體中文 README](../README.zh-Hant.md)

Implementation notes for the YouTube wrappers under `services/yt_scraper/`.

## Overview

yt-dlp wrappers collect channel metadata, bounded video-list pages, full video
metadata, and top comments for the Setlist pipeline. Prefer the **Dev
Container** (Python 3.14) over an ad-hoc conda environment.

All yt-dlp wrappers are synchronous. Production application paths run each
operation in a killable child process with bounded yt-dlp network retries and a
whole-operation deadline while holding the shared PostgreSQL advisory lock.
Unit-test doubles may use `asyncio.to_thread`. Do not bypass updater caps,
jitter, block detection, deadlines, or the persisted cooldown.

Global cooldown detection intentionally requires a high-confidence signal such
as HTTP 429, an explicit bot/CAPTCHA challenge, or IP/network blocking text.
Age confirmation, members-only/private/region restrictions, and a bare HTTP
403 can apply to only one video and must remain ordinary bounded failures. When
investigating a suspected false alert, compare one failing record with one
known-public control from the same container and egress; do not clear persisted
state merely because the control succeeds.

## Environment

| Option | Detail |
|--------|--------|
| Dev Container | Python **3.14** (recommended and CI-tested) |
| Local / conda | Python **3.14** recommended to match CI and production |
| Runtime deps | `pip install -r requirements.txt` from `backend/` |
| Dev/test deps | `pip install -r requirements-dev.txt` |

```bash
# Local example (conda)
conda create -n vks-yt-scraper python=3.14 -y
conda activate vks-yt-scraper
cd backend
pip install -r requirements-dev.txt
```

`services/yt_scraper/test.py` performs live, ad-hoc smoke checks. It is
intentionally not part of pytest or CI and may call YouTube when run.

The runtime requirements install `yt-dlp[default]` so the version-matched
`yt-dlp-ejs` challenge scripts are present, plus a pinned Deno executable as
the JavaScript runtime recommended by yt-dlp. Verify the exact production
image rather than assuming that a host-level yt-dlp installation represents
the container:

```bash
python -c "import importlib.metadata, yt_dlp; print(yt_dlp.version.__version__, importlib.metadata.version('yt-dlp-ejs'))"
deno --version
```

See yt-dlp's [EJS setup guide](https://github.com/yt-dlp/yt-dlp/wiki/EJS).
Missing EJS support is a runtime-packaging risk, but it is not by itself proof
that a particular comment failure was caused by a JavaScript challenge; use a
same-video, same-options A/B reproduction before assigning that root cause.

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
- Comments use their own analysis snapshot. Schema 2 records the bounded
  request cap, returned/reported counts, sort/depth/reply policy, yt-dlp
  version, and a likely-truncation flag without adding more comment content.
- A sparse list refresh must never overwrite richer full metadata.
- Exact upload dates may replace approximate list dates; approximate data must
  never downgrade an exact date.

Use `utils.ytdlp_snapshot` for this policy. Do not shallow-merge sparse and rich
payloads.

## Bumping yt-dlp

YouTube extractors break often. The runtime pins are currently maintained in
`requirements.txt` (`yt-dlp[default]==2026.8.19` and `deno==2.9.5`). After
confirming that a failure is extractor-related:

```bash
cd backend
pip install -U "yt-dlp[default]" deno
# reproduce the scrape, then pin the verified version in requirements.txt
python -m pytest
```

Also run the one-shot updater against a non-production development database and
confirm that block-like failures still trigger the normal cooldown. Do not
commit cookies, browser profiles, proxy credentials, signed playback URLs, or
raw secrets captured during debugging.
