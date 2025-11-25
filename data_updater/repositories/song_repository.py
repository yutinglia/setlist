from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Songs
from models.song import Song


class SongRepository:
    """負責 Song 資料的存取操作"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self) -> list[Song]:
        """從資料庫取得所有歌曲列表"""
        result = await self.session.execute(select(Songs))
        songs = result.scalars().all()
        return [Song.model_validate(song) for song in songs]

    async def get_by_id(self, song_id: int) -> Song | None:
        """根據 ID 取得單一歌曲"""
        result = await self.session.execute(
            select(Songs).where(Songs.id == song_id)
        )
        song = result.scalar_one_or_none()
        return Song.model_validate(song) if song else None

    async def get_by_video_id(self, video_id: str) -> list[Song]:
        """根據影片 ID 取得該影片的所有歌曲"""
        result = await self.session.execute(
            select(Songs).where(Songs.video_id == video_id)
        )
        songs = result.scalars().all()
        return [Song.model_validate(song) for song in songs]
