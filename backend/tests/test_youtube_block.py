"""Unit tests for YouTube block-detection helpers."""

import pytest

from services.yt_scraper.errors import (
    YouTubeAccessBlocked,
    is_youtube_block_error,
    raise_if_block_error,
)


def test_is_youtube_block_error_detects_high_confidence_block_signals():
    assert is_youtube_block_error(RuntimeError("Sign in to confirm you're not a bot"))
    assert is_youtube_block_error(RuntimeError("Sign in to confirm you’re not a bot"))
    assert is_youtube_block_error(RuntimeError("HTTP Error 429: Too Many Requests"))
    assert is_youtube_block_error(RuntimeError("YouTube has blocked your IP"))
    assert is_youtube_block_error(
        RuntimeError("Your IP is likely being blocked by Youtube")
    )
    assert is_youtube_block_error(
        RuntimeError("The current session has been rate-limited by YouTube")
    )


@pytest.mark.parametrize(
    "message",
    (
        "Sign in to confirm your age",
        "HTTP Error 403: Forbidden",
        "Join this channel to get access to members-only content",
        "Private video. Sign in if you've been granted access",
        "Video unavailable",
        "This video is not available in your country",
    ),
)
def test_per_video_access_failures_do_not_trigger_global_cooldown(message):
    assert not is_youtube_block_error(RuntimeError(message))


def test_raise_if_block_error_wraps():
    with pytest.raises(YouTubeAccessBlocked):
        raise_if_block_error(RuntimeError("confirm you're not a bot"))


def test_typed_block_remains_blocked_with_an_opaque_message():
    typed = YouTubeAccessBlocked("upstream access guard")
    assert is_youtube_block_error(typed)
    with pytest.raises(YouTubeAccessBlocked):
        raise_if_block_error(typed)


def test_generic_extractor_error_is_not_global_block():
    assert not is_youtube_block_error(RuntimeError("Unable to extract title"))


def test_block_marker_in_wrapped_cause_is_detected():
    try:
        try:
            raise RuntimeError("HTTP Error 429: Too Many Requests")
        except RuntimeError as exc:
            raise RuntimeError("yt-dlp extraction failed") from exc
    except RuntimeError as wrapped:
        assert is_youtube_block_error(wrapped)
