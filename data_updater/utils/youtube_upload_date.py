"""Derive YYYYMMDD upload dates from yt-dlp video / flat-playlist entries."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


def upload_date_from_entry(entry: Mapping[str, Any] | None) -> str | None:
    """Best-effort ``YYYYMMDD`` from a yt-dlp entry.

    Flat channel playlist extracts usually omit ``upload_date`` but often
    include unix ``timestamp`` / ``release_timestamp``. Prefer an explicit
    ``upload_date`` when present.
    """
    if not entry:
        return None

    raw = entry.get("upload_date")
    if isinstance(raw, str):
        text = raw.strip()
        if text:
            return text

    for key in ("timestamp", "release_timestamp"):
        ts = entry.get(key)
        if ts is None:
            continue
        try:
            ts_i = int(ts)
        except (TypeError, ValueError):
            continue
        if ts_i <= 0:
            continue
        return datetime.fromtimestamp(ts_i, tz=timezone.utc).strftime("%Y%m%d")

    return None
