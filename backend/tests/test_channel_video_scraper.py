"""Pure helpers around flat yt-dlp channel video entries."""

import pytest

from services.yt_scraper.channel_video_scraper import YouTubeChannelVideoScraper
from utils.youtube_upload_date import (
    UPLOAD_DATE_APPROXIMATE,
    UPLOAD_DATE_EXACT,
)
from utils.ytdlp_snapshot import snapshot_payload, snapshot_ytdlp_info


def test_flat_video_id_is_not_used_as_browser_url():
    entry = {"id": "abc123", "url": "abc123"}
    assert (
        YouTubeChannelVideoScraper._video_url(entry, "abc123")
        == "https://www.youtube.com/watch?v=abc123"
    )


def test_absolute_flat_video_url_is_preserved():
    entry = {
        "id": "abc123",
        "webpage_url": "https://www.youtube.com/watch?v=abc123",
        "url": "abc123",
    }
    assert (
        YouTubeChannelVideoScraper._video_url(entry, "abc123") == entry["webpage_url"]
    )


def test_missing_streams_tab_still_uses_empty_videos_tab(monkeypatch):
    class FakeYoutubeDL:
        def __init__(self, _options):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def extract_info(self, url, *, download):
            assert download is False
            if url.endswith("/streams"):
                raise RuntimeError("Channel has no streams tab")
            return {"entries": []}

        @staticmethod
        def sanitize_info(value):
            return value

    monkeypatch.setattr(
        "services.yt_scraper.channel_video_scraper.yt_dlp.YoutubeDL",
        FakeYoutubeDL,
    )
    scraper = YouTubeChannelVideoScraper(
        "https://www.youtube.com/@example",
        full_metadata=True,
    )

    assert scraper.get_channel_videos() == []


def test_every_failed_tab_is_an_error(monkeypatch):
    class FailingYoutubeDL:
        def __init__(self, _options):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def extract_info(self, _url, *, download):
            assert download is False
            raise RuntimeError("extract failed")

    monkeypatch.setattr(
        "services.yt_scraper.channel_video_scraper.yt_dlp.YoutubeDL",
        FailingYoutubeDL,
    )

    with pytest.raises(RuntimeError, match="Failed to extract any channel tab"):
        YouTubeChannelVideoScraper(
            "https://www.youtube.com/@example"
        ).get_channel_videos()


def test_flat_list_enables_approximate_date_without_per_video_extract(monkeypatch):
    captured_options = {}

    class FakeYoutubeDL:
        def __init__(self, options):
            captured_options.update(options)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def extract_info(self, _url, *, download):
            assert download is False
            return {"entries": []}

    monkeypatch.setattr(
        "services.yt_scraper.channel_video_scraper.yt_dlp.YoutubeDL",
        FakeYoutubeDL,
    )

    scraper = YouTubeChannelVideoScraper("https://www.youtube.com/@example")
    entries, raw_count, ok = scraper._extract_tab_entries(
        "https://www.youtube.com/@example/videos",
        playlist_start=1,
        playlist_end=3,
        use_match_filter=False,
    )

    assert (entries, raw_count, ok) == ([], 0, True)
    assert captured_options["extract_flat"] == "in_playlist"
    assert captured_options["extractor_args"] == {
        "youtubetab": {"approximate_date": [""]}
    }
    assert captured_options["socket_timeout"] == 30.0
    assert captured_options["retries"] == 2
    assert captured_options["extractor_retries"] == 2


def test_flat_timestamp_is_exposed_as_approximate_date():
    scraper = YouTubeChannelVideoScraper("https://www.youtube.com/@example")

    [video] = scraper._entries_to_models(
        [
            {
                "id": "video-1",
                "title": "Karaoke",
                "timestamp": 1_784_998_800,
            }
        ]
    )

    assert video.upload_date == "20260725"
    assert video.upload_date_precision == UPLOAD_DATE_APPROXIMATE
    assert video.raw_data["_snapshot"]["source"] == "channel_tab:unknown"
    assert snapshot_payload(video.raw_data)["timestamp"] == 1_784_998_800
    assert video.list_scraped_at is not None
    assert video.metadata_raw_data is None


def test_enriched_explicit_upload_date_is_exposed_as_exact():
    scraper = YouTubeChannelVideoScraper("https://www.youtube.com/@example")

    [video] = scraper._entries_to_models(
        [
            {
                "id": "video-1",
                "title": "Karaoke",
                "upload_date": "20260725",
                "timestamp": 1_784_998_800,
            }
        ]
    )

    assert video.upload_date == "20260725"
    assert video.upload_date_precision == UPLOAD_DATE_EXACT


def test_full_metadata_is_separate_and_overrides_flat_fields(monkeypatch):
    scraper = YouTubeChannelVideoScraper(
        "https://www.youtube.com/@example",
        full_metadata=True,
    )

    def enrich(entries):
        return [
            {
                **entries[0],
                "_vks_metadata_snapshot": snapshot_ytdlp_info(
                    {
                        "id": "video-1",
                        "title": "Exact title",
                        "upload_date": "20260724",
                        "duration": 3600,
                        "live_status": "was_live",
                    },
                    source="video_metadata",
                ),
            }
        ]

    monkeypatch.setattr(scraper, "_enrich_metadata", enrich)
    [video] = scraper._entries_to_models(
        [
            {
                "id": "video-1",
                "title": "Flat title",
                "timestamp": 1_784_998_800,
            }
        ]
    )

    assert video.title == "Exact title"
    assert video.upload_date == "20260724"
    assert video.upload_date_precision == UPLOAD_DATE_EXACT
    assert snapshot_payload(video.raw_data)["title"] == "Flat title"
    assert snapshot_payload(video.metadata_raw_data)["title"] == "Exact title"
    assert video.metadata_scraped_at is not None
