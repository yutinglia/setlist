from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Channels
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
    ) -> list[YouTubeChannel]:
        """從資料庫取得頻道列表 (optional pagination)."""
        stmt = select(Channels).order_by(Channels.name)
        if limit is not None:
            stmt = stmt.limit(limit).offset(offset)
        elif offset:
            stmt = stmt.offset(offset)
        result = await self.session.execute(stmt)
        channels = result.scalars().all()
        return [YouTubeChannel.model_validate(channel) for channel in channels]

    async def count_all(self) -> int:
        """Total number of tracked channels."""
        result = await self.session.execute(select(func.count()).select_from(Channels))
        return int(result.scalar_one())

    async def get_by_id(self, channel_id: str) -> YouTubeChannel | None:
        """根據 ID 取得單一頻道"""
        result = await self.session.execute(
            select(Channels).where(Channels.id == channel_id)
        )
        channel = result.scalar_one_or_none()
        return YouTubeChannel.model_validate(channel) if channel else None

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
        result = await self.session.execute(stmt)
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
