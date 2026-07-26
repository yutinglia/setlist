"""Administrator channel creation with durable pacing and bounded bulk support."""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from config import CHANNEL_ADD_COOLDOWN_SECONDS, SCRAPE_POLICY
from models.channel import VIDEO_BACKFILL_PENDING, YouTubeChannel
from repositories.channel_repository import ChannelRepository
from services.data_updater import DataUpdater
from services.youtube_operation_lock import (
    YouTubeUpdaterBusyError,
    youtube_operation_guard,
)
from services.yt_scraper.channel_scraper import YouTubeChannelScraper
from services.yt_scraper.errors import (
    YouTubeAccessBlocked,
    is_youtube_block_error,
)
from services.yt_scraper.subprocess_runner import run_scrape_in_subprocess

ChannelCreationStatus = Literal[
    "created",
    "already_exists",
    "failed",
    "skipped",
]


@dataclass(frozen=True)
class ChannelCreationOutcome:
    requested_url: str
    status: ChannelCreationStatus
    channel: YouTubeChannel | None
    message: str


class ChannelAddCooldownActive(RuntimeError):
    def __init__(self, remaining_seconds: float):
        self.remaining_seconds = max(0.0, remaining_seconds)
        super().__init__(
            f"Channel add cooldown active for {self.remaining_seconds:.0f} seconds"
        )


class YouTubeCooldownActive(RuntimeError):
    def __init__(self, remaining_seconds: float):
        self.remaining_seconds = max(0.0, remaining_seconds)
        super().__init__(
            f"YouTube cooldown active for {self.remaining_seconds:.0f} seconds"
        )


class ChannelResolutionFailed(RuntimeError):
    """A non-block upstream failure with its admin cooldown already committed."""


class ChannelCreator:
    """Resolve and persist channels without allowing request bursts."""

    def __init__(
        self,
        session: AsyncSession,
        repo: ChannelRepository,
        *,
        add_cooldown_seconds: int = CHANNEL_ADD_COOLDOWN_SECONDS,
    ) -> None:
        self.session = session
        self.repo = repo
        self.add_cooldown_seconds = max(0, add_cooldown_seconds)

    async def create(self, channel_url: str) -> ChannelCreationOutcome:
        """Create one channel, returning 429-compatible cooldown information."""
        async with youtube_operation_guard(self.session) as acquired:
            if not acquired:
                raise YouTubeUpdaterBusyError(
                    "Another updater process is currently using YouTube"
                )
            await self._sync_youtube_cooldown()
            self._raise_if_youtube_cooldown()
            return await self._create_locked(
                channel_url,
                wait_for_add_cooldown=False,
            )

    async def create_bulk(
        self,
        channel_urls: list[str],
    ) -> list[ChannelCreationOutcome]:
        """Create a validated batch under one global lock and paced deadline."""
        async with youtube_operation_guard(self.session) as acquired:
            if not acquired:
                raise YouTubeUpdaterBusyError(
                    "Another updater process is currently using YouTube"
                )
            await self._sync_youtube_cooldown()
            self._raise_if_youtube_cooldown()

            outcomes: list[ChannelCreationOutcome] = []
            for index, channel_url in enumerate(channel_urls):
                try:
                    outcome = await self._create_locked(
                        channel_url,
                        wait_for_add_cooldown=True,
                    )
                except ChannelResolutionFailed:
                    outcome = ChannelCreationOutcome(
                        requested_url=channel_url,
                        status="failed",
                        channel=None,
                        message="Could not resolve this YouTube channel",
                    )
                except YouTubeAccessBlocked:
                    outcomes.append(
                        ChannelCreationOutcome(
                            requested_url=channel_url,
                            status="failed",
                            channel=None,
                            message="YouTube temporarily blocked this request",
                        )
                    )
                    outcomes.extend(
                        ChannelCreationOutcome(
                            requested_url=remaining_url,
                            status="skipped",
                            channel=None,
                            message="Skipped because the YouTube cooldown is active",
                        )
                        for remaining_url in channel_urls[index + 1 :]
                    )
                    break
                outcomes.append(outcome)
            return outcomes

    async def _create_locked(
        self,
        channel_url: str,
        *,
        wait_for_add_cooldown: bool,
    ) -> ChannelCreationOutcome:
        # Exact normalized duplicates need no YouTube request and therefore do
        # not consume or wait for the administrator add cooldown.
        existing_by_url = await self.repo.get_by_url(channel_url)
        if existing_by_url is not None:
            return ChannelCreationOutcome(
                requested_url=channel_url,
                status="already_exists",
                channel=existing_by_url,
                message="Channel is already tracked",
            )

        remaining = await self._channel_add_cooldown_remaining()
        if remaining > 0:
            if not wait_for_add_cooldown:
                raise ChannelAddCooldownActive(remaining)
            await asyncio.sleep(remaining)

        self._raise_if_youtube_cooldown()
        scraper = YouTubeChannelScraper(
            sleep_interval=SCRAPE_POLICY.ytdlp_list_sleep_interval,
            max_sleep_interval=SCRAPE_POLICY.ytdlp_list_max_sleep_interval,
            socket_timeout=SCRAPE_POLICY.ytdlp_socket_timeout_seconds,
            retries=SCRAPE_POLICY.ytdlp_retries,
            extractor_retries=SCRAPE_POLICY.ytdlp_extractor_retries,
        )
        scrape = partial(scraper.get_channel_info, channel_url)

        try:
            if isinstance(self.session, AsyncSession):
                scraped = await run_scrape_in_subprocess(
                    scrape,
                    timeout_seconds=SCRAPE_POLICY.ytdlp_operation_timeout_seconds,
                    terminate_grace_seconds=(
                        SCRAPE_POLICY.ytdlp_terminate_grace_seconds
                    ),
                )
            else:
                scraped = await asyncio.to_thread(scrape)
        except Exception as exc:
            if isinstance(exc, YouTubeAccessBlocked) or is_youtube_block_error(exc):
                await self._persist_youtube_block()
                raise YouTubeAccessBlocked(str(exc)) from exc
            await self._commit_add_cooldown()
            raise ChannelResolutionFailed(str(exc)) from exc

        if not scraped.id:
            await self._commit_add_cooldown()
            raise ChannelResolutionFailed("Channel id missing from extractor response")

        existing = await self.repo.get_by_id(scraped.id)
        if existing is not None:
            await self._commit_add_cooldown()
            return ChannelCreationOutcome(
                requested_url=channel_url,
                status="already_exists",
                channel=existing,
                message="Channel is already tracked",
            )

        to_create = scraped.model_copy(
            update={
                "video_backfill_status": VIDEO_BACKFILL_PENDING,
                "video_backfill_offset": 1,
                "video_backfill_updated_at": None,
            }
        )
        try:
            created = await self.repo.create(to_create)
            if created is None:
                existing = await self.repo.get_by_id(scraped.id)
                await self.repo.set_channel_add_cooldown_until(
                    self._new_add_cooldown_deadline()
                )
                await self.session.commit()
                return ChannelCreationOutcome(
                    requested_url=channel_url,
                    status="already_exists",
                    channel=existing,
                    message="Channel is already tracked",
                )
            await self.repo.set_channel_add_cooldown_until(
                self._new_add_cooldown_deadline()
            )
            await self.session.commit()
        except BaseException:
            await self.session.rollback()
            raise

        return ChannelCreationOutcome(
            requested_url=channel_url,
            status="created",
            channel=created,
            message="Channel added; video backfill is pending",
        )

    async def _sync_youtube_cooldown(self) -> None:
        persisted = await self.repo.get_youtube_cooldown_until()
        if persisted is None:
            return
        remaining = (persisted - self._utc_now()).total_seconds()
        if remaining > DataUpdater.youtube_cooldown_remaining():
            DataUpdater.set_youtube_cooldown(remaining)

    def _raise_if_youtube_cooldown(self) -> None:
        remaining = DataUpdater.youtube_cooldown_remaining()
        if remaining > 0:
            raise YouTubeCooldownActive(remaining)

    async def _channel_add_cooldown_remaining(self) -> float:
        deadline = await self.repo.get_channel_add_cooldown_until()
        if deadline is None:
            return 0.0
        return max(0.0, (deadline - self._utc_now()).total_seconds())

    async def _commit_add_cooldown(self) -> None:
        try:
            await self.repo.set_channel_add_cooldown_until(
                self._new_add_cooldown_deadline()
            )
            await self.session.commit()
        except BaseException:
            await self.session.rollback()
            raise

    async def _persist_youtube_block(self) -> None:
        now = self._utc_now()
        block_seconds = SCRAPE_POLICY.youtube_cooldown_seconds
        try:
            await self.repo.set_channel_add_cooldown_until(
                self._new_add_cooldown_deadline(now)
            )
            await self.repo.set_youtube_cooldown_until(
                now + timedelta(seconds=block_seconds)
            )
            await self.session.commit()
        except BaseException:
            await self.session.rollback()
            raise
        DataUpdater.set_youtube_cooldown(block_seconds)

    def _new_add_cooldown_deadline(
        self,
        now: datetime | None = None,
    ) -> datetime:
        return (now or self._utc_now()) + timedelta(seconds=self.add_cooldown_seconds)

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(UTC).replace(tzinfo=None)

    @staticmethod
    def retry_after_header(remaining_seconds: float) -> str:
        return str(max(1, math.ceil(remaining_seconds)))
