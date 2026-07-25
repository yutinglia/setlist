"""Derive YYYYMMDD upload dates from yt-dlp video / flat-playlist entries."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

_UPLOAD_DATE_RE = re.compile(r"^\d{8}$")


def _valid_upload_date(value: str) -> str | None:
    text = value.strip()
    if not _UPLOAD_DATE_RE.fullmatch(text):
        return None
    try:
        datetime.strptime(text, "%Y%m%d")
    except ValueError:
        return None
    return text


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
        validated = _valid_upload_date(raw)
        if validated:
            return validated

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
        try:
            return datetime.fromtimestamp(ts_i, tz=UTC).strftime("%Y%m%d")
        except (OverflowError, OSError, ValueError):
            continue

    return None
