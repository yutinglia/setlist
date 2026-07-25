"""Pure helpers around flat yt-dlp channel video entries."""

import pytest

from services.yt_scraper.channel_video_scraper import YouTubeChannelVideoScraper


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
