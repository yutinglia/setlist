"""Administrator channel creation with durable pacing and bounded bulk support."""

from __future__ import annotations

import asyncio
import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from config import CHANNEL_ADD_COOLDOWN_SECONDS, SCRAPE_POLICY
from models.channel import VIDEO_BACKFILL_PENDING, YouTubeChannel
from repositories.channel_ingest_repository import ChannelIngestRepository
from repositories.channel_repository import ChannelRepository
from services.cache import PUBLIC_CACHE_NAMESPACES, ResponseCache
from services.scrape_policy import ScrapePolicy
from services.scraping import (
    DefaultScraperFactory,
    ScrapeExecutor,
    ScraperFactory,
)
from services.youtube_cooldown import YouTubeCooldown
from services.youtube_operation_lock import (
    YouTubeOperationCoordinator,
    YouTubeUpdaterBusyError,
    default_youtube_operation_coordinator,
)
from services.yt_scraper.errors import (
    YouTubeAccessBlocked,
    is_youtube_block_error,
)

ChannelCreationStatus = Literal[
    "created",
    "already_exists",
    "queued",
    "failed",
    "skipped",
]


@dataclass(frozen=True)
class ChannelCreationOutcome:
    requested_url: str
    status: ChannelCreationStatus
    channel: YouTubeChannel | None
    message: str
    queue_id: int | None = None
    commit_required: bool = False
    public_data_changed: bool = False
    defer_until_cooldown_ends: bool = False


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
        ingest_repo: ChannelIngestRepository | None = None,
        add_cooldown_seconds: int = CHANNEL_ADD_COOLDOWN_SECONDS,
        policy: ScrapePolicy = SCRAPE_POLICY,
        cooldown: YouTubeCooldown | None = None,
        operations: YouTubeOperationCoordinator | None = None,
        scraper_factory: ScraperFactory | None = None,
        scrape_executor: ScrapeExecutor | None = None,
        cache: ResponseCache | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.session = session
        self.repo = repo
        self.ingest_repo = ingest_repo
        self.add_cooldown_seconds = max(0, add_cooldown_seconds)
        self.policy = policy
        self.cooldown = cooldown or YouTubeCooldown(policy.youtube_cooldown_seconds)
        self.operations = operations or default_youtube_operation_coordinator
        self.scraper_factory = scraper_factory or DefaultScraperFactory(policy)
        self.scrape_executor = scrape_executor or ScrapeExecutor(policy)
        self.cache = cache
        self.sleep = sleep

    async def create(self, channel_url: str) -> ChannelCreationOutcome:
        """Create one channel, returning 429-compatible cooldown information."""
        async with self.operations.guard(self.session) as acquired:
            if not acquired:
                raise YouTubeUpdaterBusyError(
                    "Another updater process is currently using YouTube"
                )
            await self._sync_youtube_cooldown()
            self._raise_if_youtube_cooldown()
            try:
                outcome = await self.resolve_locked(
                    channel_url,
                    wait_for_add_cooldown=False,
                )
                if outcome.commit_required:
                    await self._commit(
                        invalidate_cache=outcome.public_data_changed,
                    )
                return outcome
            except ChannelResolutionFailed:
                await self._commit_staged_failure()
                raise
            except YouTubeAccessBlocked:
                await self._persist_youtube_block()
                raise
            except BaseException:
                await self.session.rollback()
                raise

    async def create_bulk(
        self,
        channel_urls: list[str],
    ) -> list[ChannelCreationOutcome]:
        """Create a validated batch under one global lock and paced deadline."""
        async with self.operations.guard(self.session) as acquired:
            if not acquired:
                raise YouTubeUpdaterBusyError(
                    "Another updater process is currently using YouTube"
                )
            await self._sync_youtube_cooldown()
            self._raise_if_youtube_cooldown()

            outcomes: list[ChannelCreationOutcome] = []
            for index, channel_url in enumerate(channel_urls):
                try:
                    outcome = await self.resolve_locked(
                        channel_url,
                        wait_for_add_cooldown=True,
                    )
                except ChannelResolutionFailed:
                    await self._commit_staged_failure()
                    outcome = ChannelCreationOutcome(
                        requested_url=channel_url,
                        status="failed",
                        channel=None,
                        message="Could not resolve this YouTube channel",
                    )
                except YouTubeAccessBlocked:
                    await self._persist_youtube_block()
                    outcomes.append(
                        ChannelCreationOutcome(
                            requested_url=channel_url,
                            status="failed",
                            channel=None,
                            message="YouTube temporarily blocked this request",
                            defer_until_cooldown_ends=True,
                        )
                    )
                    outcomes.extend(
                        ChannelCreationOutcome(
                            requested_url=remaining_url,
                            status="skipped",
                            channel=None,
                            message="Skipped because the YouTube cooldown is active",
                            defer_until_cooldown_ends=True,
                        )
                        for remaining_url in channel_urls[index + 1 :]
                    )
                    break
                except BaseException:
                    await self.session.rollback()
                    raise
                else:
                    if outcome.commit_required:
                        await self._commit(
                            invalidate_cache=outcome.public_data_changed,
                        )
                outcomes.append(outcome)
            return outcomes

    async def create_or_queue(self, channel_url: str) -> ChannelCreationOutcome:
        """Resolve immediately unless the global YouTube cooldown is active."""
        await self._sync_youtube_cooldown()
        if self._youtube_cooldown_remaining() > 0:
            return (await self._queue_many([channel_url]))[0]
        try:
            return await self.create(channel_url)
        except YouTubeCooldownActive:
            return (await self._queue_many([channel_url]))[0]

    async def create_bulk_or_queue(
        self,
        channel_urls: list[str],
    ) -> list[ChannelCreationOutcome]:
        """Resolve a healthy batch, or durably defer it during cooldown."""
        await self._sync_youtube_cooldown()
        if self._youtube_cooldown_remaining() > 0:
            return await self._queue_many(channel_urls)
        try:
            outcomes = await self.create_bulk(channel_urls)
        except YouTubeCooldownActive:
            return await self._queue_many(channel_urls)

        if self._youtube_cooldown_remaining() <= 0 or self.ingest_repo is None:
            return outcomes

        deferred_positions = [
            index
            for index, outcome in enumerate(outcomes)
            if outcome.defer_until_cooldown_ends
        ]
        deferred = await self._queue_many(
            [outcomes[index].requested_url for index in deferred_positions]
        )
        for index, queued_outcome in zip(
            deferred_positions,
            deferred,
            strict=True,
        ):
            outcomes[index] = queued_outcome
        return outcomes

    async def resolve_locked(
        self,
        channel_url: str,
        *,
        wait_for_add_cooldown: bool,
    ) -> ChannelCreationOutcome:
        """Stage one resolution while the caller owns the YouTube lock.

        The caller also owns commit/rollback based on the outcome flags. A
        block is deliberately not persisted here so each use case can include
        its own durable state in the cooldown transaction.
        """
        self._raise_if_youtube_cooldown()
        return await self._create_locked(
            channel_url,
            wait_for_add_cooldown=wait_for_add_cooldown,
        )

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
            await self.sleep(remaining)

        self._raise_if_youtube_cooldown()
        scraper = self.scraper_factory.channel()
        scrape = partial(scraper.get_channel_info, channel_url)

        try:
            scraped = await self.scrape_executor.run(
                scrape,
                production=isinstance(self.session, AsyncSession),
            )
        except Exception as exc:
            if isinstance(exc, YouTubeAccessBlocked) or is_youtube_block_error(exc):
                raise YouTubeAccessBlocked(str(exc)) from exc
            await self.repo.set_channel_add_cooldown_until(
                self._new_add_cooldown_deadline()
            )
            raise ChannelResolutionFailed(str(exc)) from exc

        if not scraped.id:
            await self.repo.set_channel_add_cooldown_until(
                self._new_add_cooldown_deadline()
            )
            raise ChannelResolutionFailed("Channel id missing from extractor response")

        existing = await self.repo.get_by_id(scraped.id)
        if existing is not None:
            await self.repo.set_channel_add_cooldown_until(
                self._new_add_cooldown_deadline()
            )
            return ChannelCreationOutcome(
                requested_url=channel_url,
                status="already_exists",
                channel=existing,
                message="Channel is already tracked",
                commit_required=True,
            )

        to_create = scraped.model_copy(
            update={
                "video_backfill_status": VIDEO_BACKFILL_PENDING,
                "video_backfill_offset": 1,
                "video_backfill_updated_at": None,
            }
        )
        created = await self.repo.create(to_create)
        if created is None:
            existing = await self.repo.get_by_id(scraped.id)
            await self.repo.set_channel_add_cooldown_until(
                self._new_add_cooldown_deadline()
            )
            return ChannelCreationOutcome(
                requested_url=channel_url,
                status="already_exists",
                channel=existing,
                message="Channel is already tracked",
                commit_required=True,
            )
        await self.repo.set_channel_add_cooldown_until(
            self._new_add_cooldown_deadline()
        )

        return ChannelCreationOutcome(
            requested_url=channel_url,
            status="created",
            channel=created,
            message="Channel added; video backfill is pending",
            commit_required=True,
            public_data_changed=True,
        )

    async def _queue_many(
        self,
        channel_urls: list[str],
    ) -> list[ChannelCreationOutcome]:
        if self.ingest_repo is None:
            self._raise_if_youtube_cooldown()
            raise RuntimeError("Deferred channel ingest is not configured")

        outcomes: list[ChannelCreationOutcome] = []
        queue_touched = False
        try:
            for channel_url in channel_urls:
                existing = await self.repo.get_by_url(channel_url)
                if existing is not None:
                    outcomes.append(
                        ChannelCreationOutcome(
                            requested_url=channel_url,
                            status="already_exists",
                            channel=existing,
                            message="Channel is already tracked",
                        )
                    )
                    continue

                item, created = await self.ingest_repo.enqueue(channel_url)
                queue_touched = True
                outcomes.append(
                    ChannelCreationOutcome(
                        requested_url=channel_url,
                        status="queued",
                        channel=None,
                        message=(
                            "Channel queued; YouTube resolution will resume "
                            "after cooldown"
                            if created
                            else "Channel is already queued for resolution"
                        ),
                        queue_id=item.id,
                    )
                )
            if queue_touched:
                await self._commit(invalidate_cache=False)
        except BaseException:
            await self.session.rollback()
            raise
        return outcomes

    async def _sync_youtube_cooldown(self) -> None:
        persisted = await self.repo.get_youtube_cooldown_until()
        if persisted is None:
            return
        remaining = (persisted - self._utc_now()).total_seconds()
        if remaining > self._youtube_cooldown_remaining():
            self._set_youtube_cooldown(remaining)

    def _raise_if_youtube_cooldown(self) -> None:
        remaining = self._youtube_cooldown_remaining()
        if remaining > 0:
            raise YouTubeCooldownActive(remaining)

    async def _channel_add_cooldown_remaining(self) -> float:
        deadline = await self.repo.get_channel_add_cooldown_until()
        if deadline is None:
            return 0.0
        return max(0.0, (deadline - self._utc_now()).total_seconds())

    async def _commit_staged_failure(self) -> None:
        try:
            await self._commit(invalidate_cache=False)
        except BaseException:
            await self.session.rollback()
            raise

    async def _persist_youtube_block(self) -> None:
        now = self._utc_now()
        block_seconds = self.policy.youtube_cooldown_seconds
        try:
            await self.repo.set_channel_add_cooldown_until(
                self._new_add_cooldown_deadline(now)
            )
            await self.repo.set_youtube_cooldown_until(
                now + timedelta(seconds=block_seconds)
            )
            await self._commit(invalidate_cache=False)
        except BaseException:
            await self.session.rollback()
            raise
        self._set_youtube_cooldown(block_seconds)

    def _youtube_cooldown_remaining(self) -> float:
        return self.cooldown.remaining()

    def _set_youtube_cooldown(self, seconds: float) -> None:
        self.cooldown.activate(seconds)

    async def _commit(self, *, invalidate_cache: bool) -> None:
        await self.session.commit()
        if invalidate_cache and self.cache is not None:
            await self.cache.invalidate(*PUBLIC_CACHE_NAMESPACES)

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
