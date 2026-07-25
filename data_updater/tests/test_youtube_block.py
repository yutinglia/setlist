"""Unit tests for YouTube block-detection helpers."""

import pytest

from services.yt_scraper.errors import (
    YouTubeAccessBlocked,
    is_youtube_block_error,
    raise_if_block_error,
)


def test_is_youtube_block_error_detects_bot_and_http():
    assert is_youtube_block_error(RuntimeError("Sign in to confirm you're not a bot"))
    assert is_youtube_block_error(RuntimeError("HTTP Error 429: Too Many Requests"))
    assert is_youtube_block_error(RuntimeError("HTTP Error 403: Forbidden"))
    assert not is_youtube_block_error(RuntimeError("Video unavailable"))


def test_raise_if_block_error_wraps():
    with pytest.raises(YouTubeAccessBlocked):
        raise_if_block_error(RuntimeError("confirm you're not a bot"))


def test_generic_extractor_error_is_not_global_block():
    assert not is_youtube_block_error(RuntimeError("Unable to extract title"))
