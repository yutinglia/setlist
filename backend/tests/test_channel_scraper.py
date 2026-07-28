"""Channel metadata scraper unit coverage without live YouTube calls."""

import pytest

from services.yt_scraper import channel_scraper
from services.yt_scraper.channel_scraper import YouTubeChannelScraper
from services.yt_scraper.errors import YouTubeAccessBlocked


def _install_youtube_dl(monkeypatch, *, result=None, error=None):
    instances = []

    class FakeYoutubeDL:
        @staticmethod
        def sanitize_info(info):
            return info

        def __init__(self, options):
            self.options = options
            instances.append(self)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def extract_info(self, url, *, download):
            self.url = url
            self.download = download
            if error is not None:
                raise error
            return result

    monkeypatch.setattr(channel_scraper.yt_dlp, "YoutubeDL", FakeYoutubeDL)
    return instances


def test_channel_scraper_prefers_uncropped_avatar_and_bounded_options(monkeypatch):
    instances = _install_youtube_dl(
        monkeypatch,
        result={
            "channel_id": "UC-test",
            "channel": "Test Channel",
            "thumbnails": [
                {"id": "small", "url": "https://images.test/small.jpg"},
                {
                    "id": "avatar_uncropped",
                    "url": "https://images.test/avatar.jpg",
                },
            ],
        },
    )
    scraper = YouTubeChannelScraper(
        sleep_interval=1.5,
        max_sleep_interval=3.0,
        socket_timeout=12.0,
        retries=4,
        extractor_retries=5,
    )

    result = scraper.get_channel_info("http://m.youtube.com/@test/videos?view=0#top")

    assert result.id == "UC-test"
    assert result.name == "Test Channel"
    assert result.url == "https://www.youtube.com/@test"
    assert result.thumbnail_url == "https://images.test/avatar.jpg"
    assert result.raw_data["_snapshot"]["source"] == "channel"
    assert scraper.channel is result
    assert instances[0].download is False
    assert instances[0].options["playlist_items"] == "0"
    assert instances[0].options["socket_timeout"] == 12.0
    assert instances[0].options["retries"] == 4
    assert instances[0].options["extractor_retries"] == 5


def test_channel_scraper_falls_back_to_id_uploader_and_last_thumbnail(monkeypatch):
    _install_youtube_dl(
        monkeypatch,
        result={
            "id": "UC-fallback",
            "uploader": "Fallback Name",
            "thumbnails": [
                None,
                {"url": ""},
                {"id": "last", "url": "https://images.test/last.jpg"},
            ],
        },
    )

    result = YouTubeChannelScraper().get_channel_info(
        "https://www.youtube.com/channel/UC-fallback"
    )

    assert result.id == "UC-fallback"
    assert result.name == "Fallback Name"
    assert result.thumbnail_url == "https://images.test/last.jpg"


@pytest.mark.parametrize("result", [None, {}, [], "invalid"])
def test_channel_scraper_rejects_empty_or_non_mapping_metadata(monkeypatch, result):
    _install_youtube_dl(monkeypatch, result=result)

    with pytest.raises(RuntimeError, match="Failed to extract"):
        YouTubeChannelScraper().get_channel_info("https://www.youtube.com/@test")


def test_channel_scraper_rejects_missing_channel_id(monkeypatch):
    _install_youtube_dl(monkeypatch, result={"channel": "Missing ID"})

    with pytest.raises(RuntimeError, match="Channel id missing"):
        YouTubeChannelScraper().get_channel_info("https://www.youtube.com/@test")


def test_channel_scraper_translates_block_errors_and_reraises_other_errors(
    monkeypatch,
):
    _install_youtube_dl(monkeypatch, error=RuntimeError("HTTP Error 429"))
    with pytest.raises(YouTubeAccessBlocked):
        YouTubeChannelScraper().get_channel_info("https://www.youtube.com/@test")

    sentinel = ValueError("ordinary extraction failure")
    _install_youtube_dl(monkeypatch, error=sentinel)
    with pytest.raises(ValueError) as exc_info:
        YouTubeChannelScraper().get_channel_info("https://www.youtube.com/@test")
    assert exc_info.value is sentinel
