"""Application composition root.

Only this module knows concrete infrastructure implementations. Routers and
services receive their collaborators through FastAPI or constructor injection.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

import config
from config import AppSettings
from db import DatabaseResources, create_database_resources
from repositories import (
    ChannelIngestRepository,
    ChannelRepository,
    ReportRepository,
    SongRepository,
    VideoRepository,
)
from services.analyzer.llm_cleaner import LlmSongListCleaner, SongListCleaner
from services.auth import AuthService
from services.cache import ResponseCache, create_cache
from services.channel_creator import ChannelCreator
from services.data_updater import DataUpdater
from services.queries import (
    CatalogQueryService,
    ChannelIngestQueryService,
    ReportQueryService,
)
from services.scraping import DefaultScraperFactory, ScrapeExecutor, ScraperFactory
from services.stored_data_reanalyzer import StoredDataReanalyzer
from services.update_cycle_trigger import UpdateCycleTrigger
from services.updater_runtime_state import UpdaterRuntimeStateStore
from services.updater_status import UpdaterStatusTracker
from services.youtube_cooldown import YouTubeCooldown
from services.youtube_operation_lock import YouTubeOperationCoordinator


class ApplicationContainer:
    """Owns process-scoped resources and creates request-scoped use-cases."""

    def __init__(
        self,
        settings: AppSettings,
        database: DatabaseResources,
        cache: ResponseCache,
        *,
        auth_service: AuthService | None = None,
        updater_status: UpdaterStatusTracker | None = None,
        update_cycle_trigger: UpdateCycleTrigger | None = None,
        youtube_cooldown: YouTubeCooldown | None = None,
        youtube_operations: YouTubeOperationCoordinator | None = None,
        scraper_factory: ScraperFactory | None = None,
        scrape_executor: ScrapeExecutor | None = None,
        song_list_cleaner: SongListCleaner | None = None,
    ) -> None:
        self.settings = settings
        self.database = database
        self.cache = cache
        self.auth_service = auth_service or AuthService(settings.auth)
        self.updater_status = updater_status or UpdaterStatusTracker()
        self.update_cycle_trigger = update_cycle_trigger or UpdateCycleTrigger()
        self.youtube_cooldown = youtube_cooldown or YouTubeCooldown(
            settings.scrape_policy.youtube_cooldown_seconds
        )
        self.youtube_operations = youtube_operations or YouTubeOperationCoordinator()
        self.scraper_factory = scraper_factory or DefaultScraperFactory(
            settings.scrape_policy
        )
        self.scrape_executor = scrape_executor or ScrapeExecutor(settings.scrape_policy)
        self.song_list_cleaner = song_list_cleaner or LlmSongListCleaner(settings.llm)
        self.runtime_state_store = UpdaterRuntimeStateStore(database.engine)

    @classmethod
    def build(
        cls,
        settings: AppSettings | None = None,
        *,
        database: DatabaseResources | None = None,
        cache: ResponseCache | None = None,
        **overrides,
    ) -> ApplicationContainer:
        selected = settings or config.get_settings()
        resources = database or create_database_resources(
            selected.database_url,
            echo=selected.is_dev,
        )
        return cls(
            selected,
            resources,
            cache or create_cache(selected.cache),
            **overrides,
        )

    @property
    def engine(self):
        return self.database.engine

    @property
    def session_factory(self):
        return self.database.session_factory

    def catalog_queries(self, session: AsyncSession) -> CatalogQueryService:
        return CatalogQueryService(
            ChannelRepository(session),
            VideoRepository(session),
            SongRepository(session),
            self.cache,
        )

    def channel_ingest_queries(
        self,
        session: AsyncSession,
    ) -> ChannelIngestQueryService:
        return ChannelIngestQueryService(ChannelIngestRepository(session))

    def report_queries(self, session: AsyncSession) -> ReportQueryService:
        return ReportQueryService(ReportRepository(session), self.cache)

    def channel_creator(self, session: AsyncSession) -> ChannelCreator:
        return ChannelCreator(
            session,
            ChannelRepository(session),
            ingest_repo=ChannelIngestRepository(session),
            add_cooldown_seconds=self.settings.channel_add_cooldown_seconds,
            policy=self.settings.scrape_policy,
            cooldown=self.youtube_cooldown,
            operations=self.youtube_operations,
            scraper_factory=self.scraper_factory,
            scrape_executor=self.scrape_executor,
            cache=self.cache,
        )

    def data_updater(self, session: AsyncSession) -> DataUpdater:
        channel_ingest_repo = ChannelIngestRepository(session)
        return DataUpdater(
            session,
            ChannelRepository(session),
            VideoRepository(session),
            SongRepository(session),
            policy=self.settings.scrape_policy,
            runtime_state_store=self.runtime_state_store,
            status_tracker=self.updater_status,
            cooldown=self.youtube_cooldown,
            operations=self.youtube_operations,
            channel_ingest_repo=channel_ingest_repo,
            channel_creator=self.channel_creator(session),
            scraper_factory=self.scraper_factory,
            scrape_executor=self.scrape_executor,
            song_list_cleaner=self.song_list_cleaner,
            cache=self.cache,
            heartbeat_interval_seconds=(
                self.settings.updater_heartbeat_interval_seconds
            ),
            background_updater_enabled=(self.settings.background_updater_enabled),
            llm_settings=self.settings.llm,
        )

    def stored_data_reanalyzer(
        self,
        session: AsyncSession,
    ) -> StoredDataReanalyzer:
        return StoredDataReanalyzer(
            session,
            ChannelRepository(session),
            VideoRepository(session),
            SongRepository(session),
            max_analysis_attempts=(self.settings.scrape_policy.max_analysis_attempts),
            operations=self.youtube_operations,
            cache=self.cache,
        )

    async def close(self) -> None:
        await self.cache.aclose()
        await self.engine.dispose()
