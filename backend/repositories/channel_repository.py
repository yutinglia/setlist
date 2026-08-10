from datetime import UTC, datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Channels, ScraperState
from models.channel import (
    VIDEO_BACKFILL_DONE,
    VideoBackfillStatus,
    YouTubeChannel,
)


class ChannelRepository:
    """Channel read/write access. Does not commit — caller owns transactions."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(
        self,
        *,
        limit: int | None = None,
        offset: int = 0,
        query: str | None = None,
    ) -> list[YouTubeChannel]:
        """從資料庫取得頻道列表 (optional pagination and literal search)."""
        stmt = select(Channels).order_by(Channels.name)
        search_filter = self._search_filter(query)
        if search_filter is not None:
            stmt = stmt.where(search_filter)
        if limit is not None:
            stmt = stmt.limit(limit).offset(offset)
        elif offset:
            stmt = stmt.offset(offset)
        result = await self.session.execute(stmt)
        channels = result.scalars().all()
        return [YouTubeChannel.model_validate(channel) for channel in channels]

    async def count_all(self, *, query: str | None = None) -> int:
        """Total number of tracked channels matching an optional search."""
        stmt = select(func.count()).select_from(Channels)
        search_filter = self._search_filter(query)
        if search_filter is not None:
            stmt = stmt.where(search_filter)
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def get_recent(self, *, limit: int) -> list[YouTubeChannel]:
        """Return channels ordered by their latest persisted update."""
        result = await self.session.execute(
            select(Channels)
            .order_by(Channels.updated_at.desc().nulls_last(), Channels.id)
            .limit(limit)
        )
        return [
            YouTubeChannel.model_validate(channel) for channel in result.scalars().all()
        ]

    @staticmethod
    def _search_filter(query: str | None):
        if query is None or not (normalized := query.strip()):
            return None
        escaped = (
            normalized.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        pattern = f"%{escaped}%"
        return or_(
            Channels.name.ilike(pattern, escape="\\"),
            Channels.id.ilike(pattern, escape="\\"),
        )

    async def get_by_id(self, channel_id: str) -> YouTubeChannel | None:
        """根據 ID 取得單一頻道"""
        result = await self.session.execute(
            select(Channels).where(Channels.id == channel_id)
        )
        channel = result.scalar_one_or_none()
        return YouTubeChannel.model_validate(channel) if channel else None

    async def get_by_url(self, channel_url: str) -> YouTubeChannel | None:
        """Return an exact normalized URL match without contacting YouTube."""
        result = await self.session.execute(
            select(Channels).where(Channels.url == channel_url)
        )
        channel = result.scalar_one_or_none()
        return YouTubeChannel.model_validate(channel) if channel else None

    async def create(self, channel: YouTubeChannel) -> YouTubeChannel | None:
        """Atomically insert a channel, returning ``None`` on an id conflict."""
        now = datetime.now(UTC).replace(tzinfo=None)
        stmt = (
            insert(Channels)
            .values(
                id=channel.id,
                name=channel.name,
                url=channel.url,
                thumbnail_url=channel.thumbnail_url,
                raw_data=channel.raw_data,
                created_at=now,
                updated_at=now,
                video_backfill_status=channel.video_backfill_status
                or VIDEO_BACKFILL_DONE,
                video_backfill_offset=channel.video_backfill_offset or 1,
                video_backfill_updated_at=channel.video_backfill_updated_at,
                last_video_scan_at=channel.last_video_scan_at,
                next_video_scan_at=channel.next_video_scan_at,
                video_scan_failures=channel.video_scan_failures,
            )
            .on_conflict_do_nothing(index_elements=[Channels.id])
            .returning(Channels)
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        await self.session.flush()
        return YouTubeChannel.model_validate(row) if row else None

    async def upsert(self, channel: YouTubeChannel) -> YouTubeChannel:
        """Insert or update a channel by primary key ``id``. Does not commit.

        Backfill columns are written on insert only so metadata refreshes do not
        reset paced full-catalog progress.
        """
        now = datetime.now(UTC).replace(tzinfo=None)
        values = {
            "id": channel.id,
            "name": channel.name,
            "url": channel.url,
            "thumbnail_url": channel.thumbnail_url,
            "raw_data": channel.raw_data,
            "updated_at": now,
        }
        insert_values = {
            **values,
            "created_at": now,
            "video_backfill_status": channel.video_backfill_status
            or VIDEO_BACKFILL_DONE,
            "video_backfill_offset": channel.video_backfill_offset or 1,
            "video_backfill_updated_at": channel.video_backfill_updated_at,
            "last_video_scan_at": channel.last_video_scan_at,
            "next_video_scan_at": channel.next_video_scan_at,
            "video_scan_failures": channel.video_scan_failures,
        }
        stmt = (
            insert(Channels)
            .values(**insert_values)
            .on_conflict_do_update(
                index_elements=[Channels.id],
                set_={
                    "name": values["name"],
                    "url": values["url"],
                    "thumbnail_url": values["thumbnail_url"],
                    "raw_data": values["raw_data"],
                    "updated_at": now,
                },
            )
            .returning(Channels)
        )
        result = await self.session.execute(
            stmt.execution_options(populate_existing=True)
        )
        row = result.scalar_one()
        await self.session.flush()
        return YouTubeChannel.model_validate(row)

    async def update_video_backfill(
        self,
        channel_id: str,
        *,
        status: VideoBackfillStatus,
        offset: int,
    ) -> YouTubeChannel | None:
        """Persist paced video-list backfill cursor. Does not commit."""
        now = datetime.now(UTC).replace(tzinfo=None)
        stmt = (
            update(Channels)
            .where(Channels.id == channel_id)
            .values(
                video_backfill_status=status,
                video_backfill_offset=max(1, offset),
                video_backfill_updated_at=now,
                updated_at=now,
            )
            .returning(Channels)
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        await self.session.flush()
        return YouTubeChannel.model_validate(row) if row else None

    async def schedule_video_scan(
        self,
        channel_id: str,
        *,
        next_scan_at: datetime,
        succeeded: bool,
    ) -> YouTubeChannel | None:
        """Persist steady-state discovery cadence. Does not commit."""
        now = datetime.now(UTC).replace(tzinfo=None)
        values: dict = {
            "next_video_scan_at": next_scan_at,
            "updated_at": now,
        }
        if succeeded:
            values.update(last_video_scan_at=now, video_scan_failures=0)
        else:
            values["video_scan_failures"] = Channels.video_scan_failures + 1
        stmt = (
            update(Channels)
            .where(Channels.id == channel_id)
            .values(**values)
            .returning(Channels)
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        await self.session.flush()
        return YouTubeChannel.model_validate(row) if row else None

    async def get_youtube_cooldown_until(self) -> datetime | None:
        """Return the process-independent YouTube cooldown deadline."""
        result = await self.session.execute(
            select(ScraperState.youtube_cooldown_until).where(ScraperState.id == 1)
        )
        return result.scalar_one_or_none()

    async def set_youtube_cooldown_until(self, until: datetime) -> None:
        """Persist the global YouTube cooldown. Does not commit."""
        now = datetime.now(UTC).replace(tzinfo=None)
        stmt = (
            insert(ScraperState)
            .values(id=1, youtube_cooldown_until=until, updated_at=now)
            .on_conflict_do_update(
                index_elements=[ScraperState.id],
                set_={
                    "youtube_cooldown_until": until,
                    "updated_at": now,
                },
            )
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def get_channel_add_cooldown_until(self) -> datetime | None:
        """Return the process-independent administrator add deadline."""
        result = await self.session.execute(
            select(ScraperState.channel_add_cooldown_until).where(ScraperState.id == 1)
        )
        return result.scalar_one_or_none()

    async def set_channel_add_cooldown_until(self, until: datetime) -> None:
        """Persist the next time an administrator may resolve a channel."""
        now = datetime.now(UTC).replace(tzinfo=None)
        stmt = (
            insert(ScraperState)
            .values(id=1, channel_add_cooldown_until=until, updated_at=now)
            .on_conflict_do_update(
                index_elements=[ScraperState.id],
                set_={
                    "channel_add_cooldown_until": until,
                    "updated_at": now,
                },
            )
        )
        await self.session.execute(stmt)
        await self.session.flush()
