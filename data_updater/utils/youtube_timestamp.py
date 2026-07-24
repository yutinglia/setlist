"""Convert setlist timestamps to YouTube deep-link seconds."""

from __future__ import annotations

import re

_TIMESTAMP_RE = re.compile(
    r"^(?:(?P<hours>\d{1,2}):)?(?P<minutes>\d{1,2}):(?P<seconds>\d{1,2})$"
)


def timestamp_to_seconds(timestamp: str | None) -> int | None:
    """Parse ``mm:ss`` or ``hh:mm:ss`` into total seconds.

    Returns ``None`` if ``timestamp`` is missing or not a valid time string.
    """
    if timestamp is None:
        return None
    text = timestamp.strip()
    if not text:
        return None

    match = _TIMESTAMP_RE.match(text)
    if not match:
        return None

    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes"))
    seconds = int(match.group("seconds"))
    if minutes > 59 or seconds > 59:
        return None
    return hours * 3600 + minutes * 60 + seconds


def youtube_url_with_timestamp(video_url: str, timestamp: str | None) -> str:
    """Append YouTube ``&t=Ns`` (or ``?t=Ns``) when ``timestamp`` parses cleanly."""
    seconds = timestamp_to_seconds(timestamp)
    if seconds is None:
        return video_url
    sep = "&" if "?" in video_url else "?"
    return f"{video_url}{sep}t={seconds}s"
