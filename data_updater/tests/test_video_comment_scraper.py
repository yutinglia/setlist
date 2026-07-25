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
