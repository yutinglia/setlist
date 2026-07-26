"""Bounded yt-dlp snapshot persistence."""

from datetime import datetime

from utils.ytdlp_snapshot import (
    MAX_FIELD_BYTES,
    merged_video_metadata,
    snapshot_captured_at,
    snapshot_payload,
    snapshot_ytdlp_info,
)


def test_snapshot_keeps_stable_and_unknown_fields_but_drops_ephemeral_payloads():
    captured_at = datetime(2026, 7, 26, 12, 30)

    snapshot = snapshot_ytdlp_info(
        {
            "id": "video-1",
            "title": "Karaoke",
            "description": "Reusable source text",
            "future_extractor_field": {"useful": True},
            "formats": [{"url": "signed-playback-url"}],
            "automatic_captions": {"en": [{"url": "large"}]},
            "comments": [{"text": "stored separately"}],
            "http_headers": {"Authorization": "not-for-storage"},
            "url": "signed-selected-format-url",
            "__x_forwarded_for_ip": "sensitive",
        },
        source="video_metadata",
        captured_at=captured_at,
    )

    assert snapshot_payload(snapshot) == {
        "id": "video-1",
        "title": "Karaoke",
        "description": "Reusable source text",
        "future_extractor_field": {"useful": True},
    }
    assert {
        "__x_forwarded_for_ip",
        "automatic_captions",
        "comments",
        "formats",
        "http_headers",
        "url",
    }.issubset(snapshot["_snapshot"]["dropped_keys"])
    assert snapshot_captured_at(snapshot) == captured_at


def test_oversized_unknown_field_is_dropped_without_losing_identity():
    snapshot = snapshot_ytdlp_info(
        {
            "id": "video-1",
            "title": "Karaoke",
            "future_large_field": "x" * (MAX_FIELD_BYTES + 1),
        },
        source="video_metadata",
    )

    assert snapshot_payload(snapshot) == {
        "id": "video-1",
        "title": "Karaoke",
    }
    assert "future_large_field" in snapshot["_snapshot"]["dropped_keys"]


def test_payload_reader_accepts_legacy_rows_and_full_metadata_wins():
    legacy = {"duration": 100, "live_status": "not_live", "list_only": True}
    full = snapshot_ytdlp_info(
        {
            "duration": 3600,
            "live_status": "was_live",
            "metadata_only": True,
        },
        source="video_metadata",
    )

    assert merged_video_metadata(legacy, full) == {
        "duration": 3600,
        "live_status": "was_live",
        "list_only": True,
        "metadata_only": True,
    }
