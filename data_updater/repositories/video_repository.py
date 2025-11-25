from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Videos
from models.video import YouTubeVideo


class VideoRepository:
    """負責 Video 資料的存取操作"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self) -> list[YouTubeVideo]:
        """從資料庫取得所有影片列表"""
        result = await self.session.execute(select(Videos))
        videos = result.scalars().all()
        return [YouTubeVideo.model_validate(video) for video in videos]

    async def get_by_id(self, video_id: str) -> YouTubeVideo | None:
        """根據 ID 取得單一影片"""
        result = await self.session.execute(
            select(Videos).where(Videos.id == video_id)
        )
        video = result.scalar_one_or_none()
        return YouTubeVideo.model_validate(video) if video else None

    async def get_by_channel_id(self, channel_id: str) -> list[YouTubeVideo]:
        """根據頻道 ID 取得該頻道的所有影片"""
        result = await self.session.execute(
            select(Videos).where(Videos.channel_id == channel_id)
        )
        videos = result.scalars().all()
        return [YouTubeVideo.model_validate(video) for video in videos]
