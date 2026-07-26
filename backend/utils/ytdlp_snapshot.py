"""Bounded, source-labelled snapshots of yt-dlp extractor responses."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import yt_dlp

SNAPSHOT_SCHEMA_VERSION = 1
MAX_SNAPSHOT_BYTES = 256 * 1024
MAX_FIELD_BYTES = 64 * 1024

# These fields are either duplicated elsewhere, extremely large, contain
# expiring/signed playback URLs, or are derived downloader state rather than
# durable source metadata.
_EXCLUDED_KEYS = frozenset(
    {
        "automatic_captions",
        "_type",
        "_version",
        "comments",
        "cookies",
        "downloader_options",
        "epoch",
        "entries",
        "formats",
        "heatmap",
        "http_headers",
        "manifest_url",
        "requested_downloads",
        "requested_formats",
        "requested_subtitles",
        "subtitles",
        "url",
    }
)

# Preserve useful identity/classification fields before optional/unknown keys
# consume the bounded payload budget.
_PRIORITY_KEYS = (
    "id",
    "title",
    "fulltitle",
    "description",
    "webpage_url",
    "original_url",
    "channel_id",
    "channel",
    "channel_url",
    "uploader_id",
    "uploader",
    "uploader_url",
    "upload_date",
    "timestamp",
    "release_date",
    "release_timestamp",
    "live_status",
    "was_live",
    "duration",
    "availability",
    "view_count",
    "like_count",
    "comment_count",
    "channel_follower_count",
    "language",
    "categories",
    "tags",
    "thumbnail",
    "thumbnails",
    "chapters",
)


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _iso_utc(value: datetime) -> str:
    aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return aware.isoformat().replace("+00:00", "Z")


def snapshot_ytdlp_info(
    info: Mapping[str, Any],
    *,
    source: str,
    captured_at: datetime | None = None,
) -> dict[str, Any]:
    """Return a JSON-safe, size-bounded snapshot with dropped-key provenance."""
    safe = yt_dlp.YoutubeDL.sanitize_info(dict(info))
    if not isinstance(safe, dict):
        raise TypeError("yt-dlp snapshot input did not sanitize to an object")

    keys = list(dict.fromkeys((*_PRIORITY_KEYS, *sorted(safe))))
    payload: dict[str, Any] = {}
    dropped: list[str] = []
    payload_bytes = 0

    for key in keys:
        if key not in safe or safe[key] is None:
            continue
        if key in _EXCLUDED_KEYS or key.startswith("__"):
            dropped.append(key)
            continue

        value = safe[key]
        try:
            encoded = json.dumps(
                value,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError):
            dropped.append(key)
            continue

        value_bytes = len(encoded)
        if value_bytes > MAX_FIELD_BYTES:
            dropped.append(key)
            continue
        candidate = {**payload, key: value}
        candidate_bytes = len(
            json.dumps(
                candidate,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        if candidate_bytes > MAX_SNAPSHOT_BYTES:
            dropped.append(key)
            continue

        payload = candidate
        payload_bytes = candidate_bytes

    return {
        "_snapshot": {
            "schema_version": SNAPSHOT_SCHEMA_VERSION,
            "source": source,
            "captured_at": _iso_utc(captured_at or _utc_now()),
            "payload_bytes": payload_bytes,
            "dropped_keys": sorted(set(dropped)),
        },
        "data": payload,
    }


def snapshot_payload(snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    """Read a versioned snapshot, while accepting legacy flat raw-data rows."""
    if not snapshot:
        return {}
    data = snapshot.get("data")
    marker = snapshot.get("_snapshot")
    if isinstance(marker, Mapping) and isinstance(data, Mapping):
        return dict(data)
    return dict(snapshot)


def snapshot_captured_at(snapshot: Mapping[str, Any] | None) -> datetime | None:
    """Return the UTC capture time from a versioned snapshot."""
    if not snapshot:
        return None
    marker = snapshot.get("_snapshot")
    if not isinstance(marker, Mapping):
        return None
    raw = marker.get("captured_at")
    if not isinstance(raw, str):
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(UTC).replace(tzinfo=None)


def merged_video_metadata(
    list_snapshot: Mapping[str, Any] | None,
    metadata_snapshot: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Full metadata overrides the channel-list observation."""
    return {
        **snapshot_payload(list_snapshot),
        **snapshot_payload(metadata_snapshot),
    }
