"""Injectable factories/adapters for blocking yt-dlp work."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, Protocol

from services.scrape_policy import ScrapePolicy
from services.yt_scraper.channel_scraper import YouTubeChannelScraper
from services.yt_scraper.channel_video_scraper import YouTubeChannelVideoScraper
from services.yt_scraper.subprocess_runner import run_scrape_in_subprocess
from services.yt_scraper.video_comment_scraper import YouTubeVideoCommentScraper


class ScraperFactory(Protocol):
    def channel(self) -> YouTubeChannelScraper: ...

    def channel_videos(
        self,
        channel_url: str,
        **overrides: Any,
    ) -> YouTubeChannelVideoScraper: ...

    def video_comments(self, video_url: str) -> YouTubeVideoCommentScraper: ...


class DefaultScraperFactory:
    """Centralizes yt-dlp constructor policy for easy replacement in tests."""

    def __init__(self, policy: ScrapePolicy) -> None:
        self.policy = policy

    def channel(self) -> YouTubeChannelScraper:
        return YouTubeChannelScraper(
            sleep_interval=self.policy.ytdlp_list_sleep_interval,
            max_sleep_interval=self.policy.ytdlp_list_max_sleep_interval,
            socket_timeout=self.policy.ytdlp_socket_timeout_seconds,
            retries=self.policy.ytdlp_retries,
            extractor_retries=self.policy.ytdlp_extractor_retries,
        )

    def channel_videos(
        self,
        channel_url: str,
        **overrides: Any,
    ) -> YouTubeChannelVideoScraper:
        options = {
            "sleep_interval": self.policy.ytdlp_list_sleep_interval,
            "max_sleep_interval": self.policy.ytdlp_list_max_sleep_interval,
            "socket_timeout": self.policy.ytdlp_socket_timeout_seconds,
            "retries": self.policy.ytdlp_retries,
            "extractor_retries": self.policy.ytdlp_extractor_retries,
        }
        options.update(overrides)
        return YouTubeChannelVideoScraper(channel_url, **options)

    def video_comments(self, video_url: str) -> YouTubeVideoCommentScraper:
        return YouTubeVideoCommentScraper(
            video_url,
            sleep_interval=self.policy.ytdlp_comment_sleep_interval,
            max_sleep_interval=self.policy.ytdlp_comment_max_sleep_interval,
            socket_timeout=self.policy.ytdlp_socket_timeout_seconds,
            retries=self.policy.ytdlp_retries,
            extractor_retries=self.policy.ytdlp_extractor_retries,
        )


class ScrapeExecutor:
    """Strategy for running blocking scrapers without blocking the event loop."""

    def __init__(self, policy: ScrapePolicy) -> None:
        self.policy = policy

    async def run(
        self,
        operation: Callable[[], Any],
        *,
        production: bool,
    ) -> Any:
        if production:
            return await run_scrape_in_subprocess(
                operation,
                timeout_seconds=self.policy.ytdlp_operation_timeout_seconds,
                terminate_grace_seconds=self.policy.ytdlp_terminate_grace_seconds,
            )
        return await asyncio.to_thread(operation)
