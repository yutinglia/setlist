"""Unit tests for yt-dlp upload_date derivation from flat playlist entries."""

from datetime import datetime, timezone

from utils.youtube_upload_date import upload_date_from_entry


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
        ts = int(datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc).timestamp())
        assert upload_date_from_entry({"timestamp": ts}) == "20240115"

    def test_from_release_timestamp_when_timestamp_missing(self):
        ts = int(datetime(2023, 6, 1, 0, 0, tzinfo=timezone.utc).timestamp())
        assert upload_date_from_entry({"release_timestamp": ts}) == "20230601"

    def test_prefers_timestamp_over_release_timestamp(self):
        older = int(datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp())
        newer = int(datetime(2024, 5, 5, tzinfo=timezone.utc).timestamp())
        assert (
            upload_date_from_entry(
                {"timestamp": newer, "release_timestamp": older}
            )
            == "20240505"
        )

    def test_ignores_non_positive_and_invalid(self):
        assert upload_date_from_entry({"timestamp": 0}) is None
        assert upload_date_from_entry({"timestamp": -1}) is None
        assert upload_date_from_entry({"timestamp": "nope"}) is None
        assert upload_date_from_entry({}) is None
        assert upload_date_from_entry(None) is None

    def test_empty_upload_date_falls_back_to_timestamp(self):
        ts = int(datetime(2022, 12, 25, tzinfo=timezone.utc).timestamp())
        assert (
            upload_date_from_entry({"upload_date": "  ", "timestamp": ts})
            == "20221225"
        )
