"""YouTube channel URL helpers for scrapers."""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse


def channel_list_urls(channel_url: str) -> list[str]:
    """Return Streams + Videos tab URLs so karaoke archives are not missed.

    Seeded channels often point at ``…/videos``. Past livestream karaoke
    archives primarily appear under ``…/streams``; scraping only Videos
    yields mostly MVs/covers.
    """
    raw = (channel_url or "").strip()
    if not raw:
        return []

    parsed = urlparse(raw)
    path = (parsed.path or "").rstrip("/")
    lower = path.lower()

    # Strip known tab suffixes so we can rebuild both tabs.
    for suffix in (
        "/videos",
        "/streams",
        "/live",
        "/shorts",
        "/playlists",
        "/community",
    ):
        if lower.endswith(suffix):
            path = path[: -len(suffix)]
            break

    base = urlunparse(
        (
            parsed.scheme or "https",
            parsed.netloc,
            path.rstrip("/") or "/",
            "",
            "",
            "",
        )
    ).rstrip("/")

    # Streams first (karaoke archives), then Videos (MVs / covers).
    return [f"{base}/streams", f"{base}/videos"]
