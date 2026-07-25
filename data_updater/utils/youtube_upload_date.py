"""Derive YYYYMMDD upload dates from yt-dlp video / flat-playlist entries."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

_UPLOAD_DATE_RE = re.compile(r"^\d{8}$")

UploadDatePrecision = Literal["exact", "approximate"]
UPLOAD_DATE_EXACT: UploadDatePrecision = "exact"
UPLOAD_DATE_APPROXIMATE: UploadDatePrecision = "approximate"


@dataclass(frozen=True)
class UploadDateInfo:
    """A normalized YouTube date and whether it came from relative list text."""

    value: str
    precision: UploadDatePrecision


def _valid_upload_date(value: str) -> str | None:
    text = value.strip()
    if not _UPLOAD_DATE_RE.fullmatch(text):
        return None
    try:
        datetime.strptime(text, "%Y%m%d")
    except ValueError:
        return None
    return text


def _date_from_timestamp(value: Any) -> str | None:
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return None
    if timestamp <= 0:
        return None
    try:
        return datetime.fromtimestamp(timestamp, tz=UTC).strftime("%Y%m%d")
    except (OverflowError, OSError, ValueError):
        return None


def upload_date_info_from_entry(
    entry: Mapping[str, Any] | None,
    *,
    timestamp_precision: UploadDatePrecision = UPLOAD_DATE_EXACT,
) -> UploadDateInfo | None:
    """Best-effort date plus precision from a yt-dlp entry.

    Flat channel playlist extracts usually omit ``upload_date`` but often
    expose relative time text. yt-dlp's ``youtubetab:approximate_date``
    converts that text to ``timestamp`` without another video request, so
    callers processing flat entries must pass ``timestamp_precision`` as
    ``"approximate"``. An explicit ``upload_date`` and a scheduled
    ``release_timestamp`` remain exact.
    """
    if not entry:
        return None

    raw = entry.get("upload_date")
    if isinstance(raw, str):
        validated = _valid_upload_date(raw)
        if validated:
            return UploadDateInfo(validated, UPLOAD_DATE_EXACT)

    timestamp_date = _date_from_timestamp(entry.get("timestamp"))
    if timestamp_date:
        return UploadDateInfo(timestamp_date, timestamp_precision)

    release_date = _date_from_timestamp(entry.get("release_timestamp"))
    if release_date:
        return UploadDateInfo(release_date, UPLOAD_DATE_EXACT)

    return None


def upload_date_from_entry(entry: Mapping[str, Any] | None) -> str | None:
    """Backward-compatible value-only form for exact/full metadata entries."""
    info = upload_date_info_from_entry(entry)
    return info.value if info else None


def best_upload_date_info(
    list_entry: Mapping[str, Any] | None,
    metadata_entry: Mapping[str, Any] | None,
) -> UploadDateInfo | None:
    """Prefer an exact full-video date, then a list-source approximate date.

    Source provenance matters: the presence of unrelated full metadata must
    not make a timestamp inherited from a flat channel list exact.
    """
    exact = upload_date_info_from_entry(metadata_entry)
    if exact is not None:
        return exact
    return upload_date_info_from_entry(
        list_entry,
        timestamp_precision=UPLOAD_DATE_APPROXIMATE,
    )
