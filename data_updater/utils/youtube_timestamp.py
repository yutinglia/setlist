"""Convert setlist timestamps to YouTube deep-link seconds."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def timestamp_to_seconds(timestamp: str | None) -> int | None:
    """Parse ``mm:ss`` or ``hh:mm:ss`` into total seconds.

    Returns ``None`` if ``timestamp`` is missing or not a valid time string.
    """
    if timestamp is None:
        return None
    text = timestamp.strip().replace("：", ":")
    if not text:
        return None

    parts = text.split(":")
    if len(parts) not in {2, 3} or not all(part.isdigit() for part in parts):
        return None

    values = [int(part) for part in parts]
    seconds = values[-1]
    if seconds > 59:
        return None

    if len(values) == 2:
        # YouTube setlists commonly use cumulative minutes (e.g. 75:04).
        minutes = values[0]
        return minutes * 60 + seconds

    hours, minutes, seconds = values
    if minutes > 59:
        return None
    return hours * 3600 + minutes * 60 + seconds


def youtube_url_with_timestamp(video_url: str, timestamp: str | None) -> str:
    """Append YouTube ``&t=Ns`` (or ``?t=Ns``) when ``timestamp`` parses cleanly."""
    seconds = timestamp_to_seconds(timestamp)
    if seconds is None:
        return video_url
    parsed = urlsplit(video_url)
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key != "t"
    ]
    query.append(("t", f"{seconds}s"))
    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment)
    )
