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
    def test_page_advances_when_any_tab_is_full(self):
        scraper = YouTubeChannelVideoScraper("https://www.youtube.com/@demo")
        full = [{"id": f"v{i}", "title": f"歌枠 {i}", "duration": 3600} for i in range(5)]
        short = [{"id": "old", "title": "歌枠 old", "duration": 3600}]

        def fake_extract(tab_url, **_kwargs):
            if tab_url.endswith("/streams"):
                return full, len(full), True
            return short, len(short), True

        with patch.object(scraper, "_extract_tab_entries", side_effect=fake_extract):
            page = scraper.get_channel_videos_page(playlist_start=1, page_size=5)

        assert page.exhausted is False
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
        assert page.raw_entry_count == 2  # both tabs

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

    def test_rejects_invalid_window(self):
        scraper = YouTubeChannelVideoScraper("https://www.youtube.com/@demo")
        with pytest.raises(ValueError):
            scraper.get_channel_videos_page(playlist_start=0, page_size=5)
        with pytest.raises(ValueError):
            scraper.get_channel_videos_page(playlist_start=1, page_size=0)
