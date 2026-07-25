"""YouTube access / bot-limit detection helpers for Tier B pacing."""

from __future__ import annotations

# Substrings commonly seen when YouTube rate-limits or challenges yt-dlp clients.
_BLOCK_MARKERS = (
    "sign in to confirm",
    "confirm you're not a bot",
    "confirm you are not a bot",
    "http error 429",
    "http error 403",
    "too many requests",
    "has blocked your ip",
    "blocked your ip",
    "bot check",
    "captcha",
    "request from your network",
)


class YouTubeAccessBlocked(Exception):
    """Raised when YouTube appears to be blocking or limiting access."""


def is_youtube_block_error(exc: BaseException) -> bool:
    """Return True if ``exc`` looks like a YouTube bot / HTTP access block."""
    msg = str(exc).lower()
    return any(marker in msg for marker in _BLOCK_MARKERS)


def raise_if_block_error(exc: BaseException) -> None:
    """Re-raise ``exc`` as ``YouTubeAccessBlocked`` when it matches block markers."""
    if is_youtube_block_error(exc):
        raise YouTubeAccessBlocked(str(exc)) from exc
