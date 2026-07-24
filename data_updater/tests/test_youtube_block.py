"""Unit tests for YouTube block-detection helpers."""

from services.yt_scraper.errors import (
    YouTubeAccessBlocked,
    comments_look_blocked,
    is_youtube_block_error,
    raise_if_block_error,
)


def test_is_youtube_block_error_detects_bot_and_http():
    assert is_youtube_block_error(
        RuntimeError("Sign in to confirm you're not a bot")
    )
    assert is_youtube_block_error(RuntimeError("HTTP Error 429: Too Many Requests"))
    assert is_youtube_block_error(RuntimeError("HTTP Error 403: Forbidden"))
    assert not is_youtube_block_error(RuntimeError("Video unavailable"))


def test_raise_if_block_error_wraps():
    try:
        raise_if_block_error(RuntimeError("confirm you're not a bot"))
        assert False, "expected YouTubeAccessBlocked"
    except YouTubeAccessBlocked:
        pass


def test_comments_look_blocked():
    assert comments_look_blocked(None) is True
    assert comments_look_blocked([]) is False
    assert comments_look_blocked([{"text": "hi"}]) is False
