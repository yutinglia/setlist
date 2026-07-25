"""Unit tests for channel video list filtering and paced backfill pages."""

from unittest.mock import patch

import pytest

from services.yt_scraper.channel_video_scraper import (
    YouTubeChannelVideoScraper,
    should_exclude_channel_list_entry,
)


class TestShouldExcludeChannelListEntry:
    def test_keeps_normal_vod(self):
        assert (
            should_exclude_channel_list_entry(
                {"id": "a", "url": "https://www.youtube.com/watch?v=a", "duration": 600}
            )
            is None
        )

    def test_excludes_shorts(self):
        assert (
            should_exclude_channel_list_entry(
                {"id": "a", "url": "https://www.youtube.com/shorts/a"}
            )
            is not None
        )

    def test_excludes_short_duration(self):
        assert (
            should_exclude_channel_list_entry({"id": "a", "duration": 30}) is not None
        )


class TestChannelVideoPage:
    def test_page_advances_when_all_tabs_succeed_and_any_tab_is_full(self):
        scraper = YouTubeChannelVideoScraper("https://www.youtube.com/@demo")
        full = [
            {"id": f"v{i}", "title": f"歌枠 {i}", "duration": 3600} for i in range(5)
        ]
        short = [{"id": "old", "title": "歌枠 old", "duration": 3600}]

        def fake_extract(tab_url, **_kwargs):
            if tab_url.endswith("/streams"):
                return full, len(full), True
            return short, len(short), True

        with patch.object(scraper, "_extract_tab_entries", side_effect=fake_extract):
            page = scraper.get_channel_videos_page(playlist_start=1, page_size=5)

        assert page.exhausted is False
        assert page.all_tabs_succeeded is True
        assert page.failed_tabs == ()
        assert page.raw_entry_count == 6
        assert len(page.videos) == 6

    def test_page_exhausted_when_all_tabs_short(self):
        scraper = YouTubeChannelVideoScraper("https://www.youtube.com/@demo")
        short = [{"id": "a", "title": "歌枠", "duration": 3600}]

        with patch.object(
            scraper,
            "_extract_tab_entries",
            return_value=(short, 1, True),
        ):
            page = scraper.get_channel_videos_page(playlist_start=21, page_size=5)

        assert page.exhausted is True
        assert page.all_tabs_succeeded is True
        assert page.raw_entry_count == 2  # both tabs

    def test_partial_tab_failure_never_advances_or_signals_exhaustion(self):
        scraper = YouTubeChannelVideoScraper("https://www.youtube.com/@demo")
        short = [{"id": "old", "title": "歌枠 old", "duration": 3600}]

        def fake_extract(tab_url, **_kwargs):
            if tab_url.endswith("/streams"):
                return [], 0, False
            return short, len(short), True

        with patch.object(scraper, "_extract_tab_entries", side_effect=fake_extract):
            page = scraper.get_channel_videos_page(playlist_start=21, page_size=5)

        assert page.exhausted is False
        assert page.all_tabs_succeeded is False
        assert len(page.failed_tabs) == 1
        assert page.raw_entry_count == 1
        assert [video.id for video in page.videos] == ["old"]

    def test_page_raises_when_all_tabs_fail(self):
        scraper = YouTubeChannelVideoScraper("https://www.youtube.com/@demo")
        with patch.object(
            scraper,
            "_extract_tab_entries",
            return_value=([], 0, False),
        ):
            with pytest.raises(RuntimeError, match="Failed to extract backfill page"):
                scraper.get_channel_videos_page(playlist_start=1, page_size=5)

    def test_filters_shorts_without_counting_as_exhaustion(self):
        scraper = YouTubeChannelVideoScraper("https://www.youtube.com/@demo")
        raw = [
            {"id": f"s{i}", "url": f"https://www.youtube.com/shorts/s{i}"}
            for i in range(5)
        ]

        with patch.object(
            scraper,
            "_extract_tab_entries",
            return_value=(raw, 5, True),
        ):
            page = scraper.get_channel_videos_page(playlist_start=1, page_size=5)

        assert page.exhausted is False
        assert page.raw_entry_count == 10
        assert page.videos == []

    def test_missing_channel_tab_is_treated_as_empty_success(self):
        scraper = YouTubeChannelVideoScraper("https://www.youtube.com/@demo")
        error = RuntimeError("This channel does not have a streams tab")

        class BrokenYdl:
            def __init__(self, _opts):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def extract_info(self, _url, *, download):
                del download
                raise error

        with patch(
            "services.yt_scraper.channel_video_scraper.yt_dlp.YoutubeDL",
            BrokenYdl,
        ):
            entries, raw_count, ok = scraper._extract_tab_entries(
                "https://www.youtube.com/@demo/streams",
                playlist_start=1,
                playlist_end=5,
                use_match_filter=False,
            )

        assert entries == []
        assert raw_count == 0
        assert ok is True

    def test_unavailable_slots_count_toward_page_window(self):
        scraper = YouTubeChannelVideoScraper("https://www.youtube.com/@demo")

        class FakeYdl:
            def __init__(self, _opts):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def extract_info(self, _url, *, download):
                del download
                return {
                    "entries": [
                        {"id": "kept", "title": "歌枠"},
                        None,
                        None,
                    ]
                }

        with patch(
            "services.yt_scraper.channel_video_scraper.yt_dlp.YoutubeDL",
            FakeYdl,
        ):
            entries, raw_count, ok = scraper._extract_tab_entries(
                "https://www.youtube.com/@demo/videos",
                playlist_start=1,
                playlist_end=3,
                use_match_filter=False,
            )

        assert [entry["id"] for entry in entries] == ["kept"]
        assert entries[0]["_vks_playlist_position"] == 1
        assert raw_count == 3
        assert ok is True

    def test_playlist_position_accounts_for_page_offset(self):
        scraper = YouTubeChannelVideoScraper("https://www.youtube.com/@demo")

        class FakeYdl:
            def __init__(self, _opts):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def extract_info(self, _url, *, download):
                del download
                return {"entries": [{"id": "old", "title": "歌枠"}]}

        with patch(
            "services.yt_scraper.channel_video_scraper.yt_dlp.YoutubeDL",
            FakeYdl,
        ):
            entries, _, _ = scraper._extract_tab_entries(
                "https://www.youtube.com/@demo/streams",
                playlist_start=101,
                playlist_end=200,
                use_match_filter=False,
            )

        assert entries[0]["_vks_source_tab"] == "streams"
        assert entries[0]["_vks_playlist_position"] == 101

    def test_rejects_invalid_window(self):
        scraper = YouTubeChannelVideoScraper("https://www.youtube.com/@demo")
        with pytest.raises(ValueError):
            scraper.get_channel_videos_page(playlist_start=0, page_size=5)
        with pytest.raises(ValueError):
            scraper.get_channel_videos_page(playlist_start=1, page_size=0)
