from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Channels
from models.channel import YouTubeChannel


class ChannelRepository:
    """負責 Channel 資料的存取操作"""

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
