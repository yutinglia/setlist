from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Channels
from models.channel import YouTubeChannel


class ChannelRepository:
    """Channel read/write access. Does not commit — caller owns transactions."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self) -> list[YouTubeChannel]:
        """從資料庫取得所有頻道列表"""
        result = await self.session.execute(select(Channels))
        channels = result.scalars().all()
        return [YouTubeChannel.model_validate(channel) for channel in channels]

    async def get_by_id(self, channel_id: str) -> YouTubeChannel | None:
        """根據 ID 取得單一頻道"""
        result = await self.session.execute(
            select(Channels).where(Channels.id == channel_id)
        )
        channel = result.scalar_one_or_none()
        return YouTubeChannel.model_validate(channel) if channel else None

    async def upsert(self, channel: YouTubeChannel) -> YouTubeChannel:
        """Insert or update a channel by primary key ``id``. Does not commit."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        values = {
            "id": channel.id,
            "name": channel.name,
            "url": channel.url,
            "thumbnail_url": channel.thumbnail_url,
            "raw_data": channel.raw_data,
            "updated_at": now,
        }
        stmt = (
            insert(Channels)
            .values(**values, created_at=now)
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
