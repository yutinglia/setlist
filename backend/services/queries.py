"""Read use-cases with dependency-injected repositories and cache-aside policy."""

from __future__ import annotations

from models.report import SummaryReport
from models.search import (
    ChannelRead,
    Paginated,
    SongSearchResult,
    SongSuggestion,
    VideoRead,
)
from models.song import Song
from repositories import (
    ChannelRepository,
    ReportRepository,
    SongRepository,
    VideoRepository,
)
from services.cache import ResponseCache

CATALOG_CACHE_NAMESPACE = "catalog"
REPORT_CACHE_NAMESPACE = "report"


class CatalogQueryService:
    """Application-level public catalog reads.

    Routers depend on this service rather than constructing repositories or
    knowing how Redis/Valkey values are serialized.
    """

    def __init__(
        self,
        channel_repo: ChannelRepository,
        video_repo: VideoRepository,
        song_repo: SongRepository,
        cache: ResponseCache,
    ) -> None:
        self.channel_repo = channel_repo
        self.video_repo = video_repo
        self.song_repo = song_repo
        self.cache = cache

    async def search_songs(
        self,
        query: str,
        *,
        limit: int,
        offset: int,
        channel_ids: list[str] | None,
        video_type: str | None,
        upload_date_from: str | None,
        upload_date_to: str | None,
    ) -> Paginated[SongSearchResult]:
        parameters = {
            "operation": "search_songs",
            "query": query,
            "limit": limit,
            "offset": offset,
            "channel_ids": sorted(set(channel_ids or [])),
            "video_type": video_type,
            "upload_date_from": upload_date_from,
            "upload_date_to": upload_date_to,
        }

        async def load() -> Paginated[SongSearchResult]:
            items, total = await self.song_repo.search_by_title(
                query,
                limit=limit,
                offset=offset,
                channel_ids=channel_ids,
                video_type=video_type,
                upload_date_from=upload_date_from,
                upload_date_to=upload_date_to,
            )
            return Paginated(
                items=items,
                total=total,
                limit=limit,
                offset=offset,
            )

        return await self.cache.remember(
            CATALOG_CACHE_NAMESPACE,
            parameters,
            Paginated[SongSearchResult],
            load,
        )

    async def suggest_songs(
        self,
        query: str,
        *,
        limit: int,
        channel_ids: list[str] | None,
        video_type: str | None,
        upload_date_from: str | None,
        upload_date_to: str | None,
    ) -> list[SongSuggestion]:
        parameters = {
            "operation": "suggest_songs",
            "query": query,
            "limit": limit,
            "channel_ids": sorted(set(channel_ids or [])),
            "video_type": video_type,
            "upload_date_from": upload_date_from,
            "upload_date_to": upload_date_to,
        }

        async def load() -> list[SongSuggestion]:
            return await self.song_repo.suggest_titles(
                query,
                limit=limit,
                channel_ids=channel_ids,
                video_type=video_type,
                upload_date_from=upload_date_from,
                upload_date_to=upload_date_to,
            )

        return await self.cache.remember(
            CATALOG_CACHE_NAMESPACE,
            parameters,
            list[SongSuggestion],
            load,
        )

    async def get_song(self, song_id: int) -> SongSearchResult | None:
        async def load() -> SongSearchResult | None:
            return await self.song_repo.get_detail(song_id)

        return await self.cache.remember(
            CATALOG_CACHE_NAMESPACE,
            {"operation": "get_song", "song_id": song_id},
            SongSearchResult | None,
            load,
        )

    async def list_channels(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Paginated[ChannelRead]:
        async def load() -> Paginated[ChannelRead]:
            channels = await self.channel_repo.get_all(limit=limit, offset=offset)
            total = await self.channel_repo.count_all()
            return Paginated(
                items=[ChannelRead.model_validate(item) for item in channels],
                total=total,
                limit=limit,
                offset=offset,
            )

        return await self.cache.remember(
            CATALOG_CACHE_NAMESPACE,
            {"operation": "list_channels", "limit": limit, "offset": offset},
            Paginated[ChannelRead],
            load,
        )

    async def get_channel(self, channel_id: str) -> ChannelRead | None:
        async def load() -> ChannelRead | None:
            channel = await self.channel_repo.get_by_id(channel_id)
            return ChannelRead.model_validate(channel) if channel is not None else None

        return await self.cache.remember(
            CATALOG_CACHE_NAMESPACE,
            {"operation": "get_channel", "channel_id": channel_id},
            ChannelRead | None,
            load,
        )

    async def list_channel_videos(
        self,
        channel_id: str,
        *,
        limit: int,
        offset: int,
        video_type: str | None,
        has_song_list: bool | None,
    ) -> Paginated[VideoRead] | None:
        async def load() -> Paginated[VideoRead] | None:
            if await self.channel_repo.get_by_id(channel_id) is None:
                return None
            videos = await self.video_repo.get_by_channel_id(
                channel_id,
                limit=limit,
                offset=offset,
                video_type=video_type,
                has_song_list=has_song_list,
            )
            total = await self.video_repo.count_by_channel_id(
                channel_id,
                video_type=video_type,
                has_song_list=has_song_list,
            )
            return Paginated(
                items=[VideoRead.model_validate(item) for item in videos],
                total=total,
                limit=limit,
                offset=offset,
            )

        return await self.cache.remember(
            CATALOG_CACHE_NAMESPACE,
            {
                "operation": "list_channel_videos",
                "channel_id": channel_id,
                "limit": limit,
                "offset": offset,
                "video_type": video_type,
                "has_song_list": has_song_list,
            },
            Paginated[VideoRead] | None,
            load,
        )

    async def get_video(self, video_id: str) -> VideoRead | None:
        async def load() -> VideoRead | None:
            video = await self.video_repo.get_by_id(video_id)
            return VideoRead.model_validate(video) if video is not None else None

        return await self.cache.remember(
            CATALOG_CACHE_NAMESPACE,
            {"operation": "get_video", "video_id": video_id},
            VideoRead | None,
            load,
        )

    async def list_video_songs(
        self,
        video_id: str,
        *,
        limit: int,
        offset: int,
    ) -> Paginated[Song] | None:
        async def load() -> Paginated[Song] | None:
            if await self.video_repo.get_by_id(video_id) is None:
                return None
            songs = await self.song_repo.get_by_video_id(
                video_id,
                limit=limit,
                offset=offset,
            )
            total = await self.song_repo.count_by_video_id(video_id)
            return Paginated(
                items=songs,
                total=total,
                limit=limit,
                offset=offset,
            )

        return await self.cache.remember(
            CATALOG_CACHE_NAMESPACE,
            {
                "operation": "list_video_songs",
                "video_id": video_id,
                "limit": limit,
                "offset": offset,
            },
            Paginated[Song] | None,
            load,
        )

    async def invalidate(self) -> None:
        await self.cache.invalidate(CATALOG_CACHE_NAMESPACE, REPORT_CACHE_NAMESPACE)


class ReportQueryService:
    def __init__(self, repo: ReportRepository, cache: ResponseCache) -> None:
        self.repo = repo
        self.cache = cache

    async def get_summary(self) -> SummaryReport:
        return await self.cache.remember(
            REPORT_CACHE_NAMESPACE,
            {"operation": "summary"},
            SummaryReport,
            self.repo.get_summary,
        )
