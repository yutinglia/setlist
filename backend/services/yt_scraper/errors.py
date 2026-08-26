"""YouTube access / bot-limit detection helpers for Tier B pacing."""

from __future__ import annotations

# High-confidence substrings seen when YouTube rate-limits or challenges an
# entire yt-dlp client/egress. Do not include generic sign-in or HTTP 403 text:
# age-restricted, members-only, private, and region-restricted videos can emit
# those per-video failures while unrelated public videos remain accessible.
_BLOCK_MARKERS = (
    "confirm you're not a bot",
    "confirm you’re not a bot",
    "confirm you are not a bot",
    "http error 429",
    "too many requests",
    "has blocked your ip",
    "blocked your ip",
    "your ip is likely being blocked by youtube",
    "rate-limited by youtube",
    "bot check",
    "captcha",
    "request from your network",
)


class YouTubeAccessBlocked(Exception):
    """Raised when YouTube appears to be blocking or limiting access."""


def is_youtube_block_error(exc: BaseException) -> bool:
    """Return True if an exception chain looks like an access block.

    yt-dlp and wrappers sometimes replace the outer message while retaining
    the useful HTTP/bot-check text in ``__cause__`` or ``__context__``.
    """
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, YouTubeAccessBlocked):
            return True
        msg = str(current).lower()
        if any(marker in msg for marker in _BLOCK_MARKERS):
            return True
        current = current.__cause__ or current.__context__
    return False


def raise_if_block_error(exc: BaseException) -> None:
    """Re-raise ``exc`` as ``YouTubeAccessBlocked`` when it matches block markers."""
    if is_youtube_block_error(exc):
        raise YouTubeAccessBlocked(str(exc)) from exc
