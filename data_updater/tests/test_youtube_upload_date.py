"""Unit tests for yt-dlp upload_date derivation from flat playlist entries."""

from datetime import UTC, datetime

from utils.youtube_upload_date import (
    UPLOAD_DATE_APPROXIMATE,
    UPLOAD_DATE_EXACT,
    best_upload_date_info,
    upload_date_from_entry,
    upload_date_info_from_entry,
)


class TestUploadDateFromEntry:
    def test_prefers_explicit_upload_date(self):
        assert (
            upload_date_from_entry(
                {
                    "upload_date": "20240115",
                    "timestamp": 1_700_000_000,
                }
            )
            == "20240115"
        )

    def test_strips_upload_date(self):
        assert upload_date_from_entry({"upload_date": " 20240115 "}) == "20240115"

    def test_from_timestamp(self):
        ts = int(datetime(2024, 1, 15, 12, 0, tzinfo=UTC).timestamp())
        assert upload_date_from_entry({"timestamp": ts}) == "20240115"

    def test_from_release_timestamp_when_timestamp_missing(self):
        ts = int(datetime(2023, 6, 1, 0, 0, tzinfo=UTC).timestamp())
        assert upload_date_from_entry({"release_timestamp": ts}) == "20230601"

    def test_prefers_timestamp_over_release_timestamp(self):
        older = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp())
        newer = int(datetime(2024, 5, 5, tzinfo=UTC).timestamp())
        assert (
            upload_date_from_entry({"timestamp": newer, "release_timestamp": older})
            == "20240505"
        )

    def test_ignores_non_positive_and_invalid(self):
        assert upload_date_from_entry({"timestamp": 0}) is None
        assert upload_date_from_entry({"timestamp": -1}) is None
        assert upload_date_from_entry({"timestamp": "nope"}) is None
        assert upload_date_from_entry({}) is None
        assert upload_date_from_entry(None) is None

    def test_empty_upload_date_falls_back_to_timestamp(self):
        ts = int(datetime(2022, 12, 25, tzinfo=UTC).timestamp())
        assert (
            upload_date_from_entry({"upload_date": "  ", "timestamp": ts}) == "20221225"
        )

    def test_invalid_explicit_date_falls_back(self):
        ts = int(datetime(2024, 2, 1, tzinfo=UTC).timestamp())
        assert (
            upload_date_from_entry({"upload_date": "20240231", "timestamp": ts})
            == "20240201"
        )

    def test_out_of_range_timestamp_is_ignored(self):
        assert upload_date_from_entry({"timestamp": 10**100}) is None

    def test_flat_timestamp_can_be_marked_approximate(self):
        ts = int(datetime(2026, 7, 25, 17, 0, tzinfo=UTC).timestamp())

        info = upload_date_info_from_entry(
            {"timestamp": ts},
            timestamp_precision=UPLOAD_DATE_APPROXIMATE,
        )

        assert info is not None
        assert info.value == "20260725"
        assert info.precision == UPLOAD_DATE_APPROXIMATE

    def test_explicit_date_stays_exact_when_timestamp_is_approximate(self):
        info = upload_date_info_from_entry(
            {
                "upload_date": "20260725",
                "timestamp": 1_784_998_800,
            },
            timestamp_precision=UPLOAD_DATE_APPROXIMATE,
        )

        assert info is not None
        assert info.value == "20260725"
        assert info.precision == UPLOAD_DATE_EXACT

    def test_scheduled_release_timestamp_is_exact(self):
        ts = int(datetime(2026, 8, 1, 12, 0, tzinfo=UTC).timestamp())

        info = upload_date_info_from_entry(
            {"release_timestamp": ts},
            timestamp_precision=UPLOAD_DATE_APPROXIMATE,
        )

        assert info is not None
        assert info.precision == UPLOAD_DATE_EXACT

    def test_unrelated_full_metadata_does_not_upgrade_flat_timestamp(self):
        info = best_upload_date_info(
            {"timestamp": 1_784_998_800},
            {"duration": 3600, "live_status": "was_live"},
        )

        assert info is not None
        assert info.value == "20260725"
        assert info.precision == UPLOAD_DATE_APPROXIMATE

    def test_full_metadata_date_wins_over_flat_approximation(self):
        info = best_upload_date_info(
            {"timestamp": 1_784_998_800},
            {"upload_date": "20260724"},
        )

        assert info is not None
        assert info.value == "20260724"
        assert info.precision == UPLOAD_DATE_EXACT
