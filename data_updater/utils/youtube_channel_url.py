"""YouTube channel URL helpers for scrapers."""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse

_TAB_SUFFIXES = frozenset(
    {"videos", "streams", "live", "shorts", "playlists", "community", "featured"}
)
_NON_CHANNEL_ROOTS = frozenset(
    {
        "account",
        "embed",
        "feed",
        "gaming",
        "hashtag",
        "oembed",
        "playlist",
        "redirect",
        "results",
        "shorts",
        "watch",
    }
)
_ALLOWED_HOSTS = frozenset({"youtube.com", "www.youtube.com", "m.youtube.com"})


def normalize_youtube_channel_url(channel_url: str) -> str:
    """Validate and canonicalize a public YouTube channel URL.

    This function is also the SSRF boundary for user-supplied channel URLs:
    only normal HTTP(S) YouTube hosts and channel-shaped paths are accepted.
    Query strings, fragments, credentials, ports, and tab suffixes are removed.
    """
    raw = (channel_url or "").strip()
    if not raw:
        raise ValueError("YouTube channel URL must not be empty")

    parsed = urlparse(raw)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError("YouTube channel URL must use http or https")
    if parsed.username or parsed.password:
        raise ValueError("YouTube channel URL must not include credentials")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("YouTube channel URL has an invalid port") from exc
    if port is not None:
        raise ValueError("YouTube channel URL must not include a custom port")

    host = (parsed.hostname or "").lower().rstrip(".")
    if host not in _ALLOWED_HOSTS:
        raise ValueError("URL must point to youtube.com")

    parts = [part for part in (parsed.path or "").split("/") if part]
    if not parts or parts[0].lower() in _NON_CHANNEL_ROOTS:
        raise ValueError("URL must point to a YouTube channel")
    if parts[-1].lower() in _TAB_SUFFIXES:
        parts.pop()
    if not parts:
        raise ValueError("URL must point to a YouTube channel")
    root = parts[0].lower()
    if root in {"channel", "c", "user"}:
        if len(parts) != 2:
            raise ValueError("YouTube channel URL has an invalid path")
    elif parts[0].startswith("@"):
        if len(parts) != 1 or len(parts[0]) == 1:
            raise ValueError("YouTube channel handle is invalid")
    elif len(parts) != 1:
        # Retain one-segment legacy custom channel URLs, but reject arbitrary
        # nested YouTube paths such as /embed/... or /foo/bar.
        raise ValueError("URL must point to a YouTube channel")

    path = "/" + "/".join(parts)
    return urlunparse(("https", "www.youtube.com", path, "", "", ""))


def channel_list_urls(channel_url: str) -> list[str]:
    """Return Streams + Videos tab URLs so karaoke archives are not missed.

    Seeded channels often point at ``…/videos``. Past livestream karaoke
    archives primarily appear under ``…/streams``; scraping only Videos
    yields mostly MVs/covers.
    """
    raw = (channel_url or "").strip()
    if not raw:
        return []

    try:
        base = normalize_youtube_channel_url(raw)
    except ValueError:
        return []

    # Streams first (karaoke archives), then Videos (MVs / covers).
    return [f"{base}/streams", f"{base}/videos"]
