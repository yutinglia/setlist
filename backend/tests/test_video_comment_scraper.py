"""Defensive yt-dlp comment response handling."""

from unittest.mock import patch

import pytest

from services.yt_scraper.errors import YouTubeAccessBlocked
from services.yt_scraper.video_comment_scraper import YouTubeVideoCommentScraper


class _FakeYdl:
    response = None

    def __init__(self, _options):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def extract_info(self, _url, *, download):
        assert download is False
        return self.response

    @staticmethod
    def sanitize_info(value):
        return value


def test_empty_response_is_retryable_without_global_cooldown():
    _FakeYdl.response = None
    scraper = YouTubeVideoCommentScraper("https://www.youtube.com/watch?v=test")

    with patch(
        "services.yt_scraper.video_comment_scraper.yt_dlp.YoutubeDL",
        _FakeYdl,
    ):
        with pytest.raises(RuntimeError) as exc_info:
            scraper.get_video_top_comments(10)

    assert not isinstance(exc_info.value, YouTubeAccessBlocked)


def test_unexpected_comments_shape_is_retryable_error():
    _FakeYdl.response = {"comments": {"not": "a list"}}
    scraper = YouTubeVideoCommentScraper("https://www.youtube.com/watch?v=test")

    with patch(
        "services.yt_scraper.video_comment_scraper.yt_dlp.YoutubeDL",
        _FakeYdl,
    ):
        with pytest.raises(RuntimeError, match="Unexpected comments response"):
            scraper.get_video_top_comments(10)


def test_malformed_comment_items_are_dropped():
    _FakeYdl.response = {
        "comments": [{"text": "valid"}, None, "invalid", {"text": "also valid"}]
    }
    scraper = YouTubeVideoCommentScraper("https://www.youtube.com/watch?v=test")

    with patch(
        "services.yt_scraper.video_comment_scraper.yt_dlp.YoutubeDL",
        _FakeYdl,
    ):
        comments = scraper.get_video_top_comments(10)

    assert comments == [{"text": "valid"}, {"text": "also valid"}]


def test_comment_scrape_exposes_existing_full_video_metadata():
    _FakeYdl.response = {
        "id": "video-1",
        "title": "Karaoke",
        "upload_date": "20260725",
        "timestamp": 1_784_997_784,
        "duration": 3600,
        "live_status": "was_live",
        "comments": [],
        # Large/unrelated extractor fields must not be retained here.
        "formats": [{"format_id": "large"}],
    }
    scraper = YouTubeVideoCommentScraper("https://www.youtube.com/watch?v=test")

    with patch(
        "services.yt_scraper.video_comment_scraper.yt_dlp.YoutubeDL",
        _FakeYdl,
    ):
        assert scraper.get_video_top_comments(10) == []

    assert scraper.video_metadata == {
        "id": "video-1",
        "title": "Karaoke",
        "upload_date": "20260725",
        "timestamp": 1_784_997_784,
        "live_status": "was_live",
        "duration": 3600,
    }
    assert scraper.last_result is not None
    assert scraper.last_result.metadata_raw_data["_snapshot"]["source"] == (
        "video_comments"
    )
    assert scraper.last_result.metadata_raw_data["_snapshot"]["dropped_keys"] == [
        "comments",
        "formats",
    ]
