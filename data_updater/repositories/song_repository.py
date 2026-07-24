from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Songs
from models.song import Song


class SongRepository:
    """Song read/write access. Does not commit — caller owns transactions.

    Write policy for a video's setlist: ``replace_for_video`` deletes all
    existing songs for that ``video_id`` and inserts the new list. Prefer this
    over per-row upsert so re-analysis can shrink or reorder the setlist cleanly.
    """

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

    async def replace_for_video(self, video_id: str, songs: list[Song]) -> list[Song]:
        """Replace all songs for ``video_id`` (delete + insert). Does not commit.

        Each song's ``video_id`` is forced to the given ``video_id``.
        """
        await self.session.execute(delete(Songs).where(Songs.video_id == video_id))

        if not songs:
            await self.session.flush()
            return []

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        rows = [
            {
                "title": song.title,
                "video_id": video_id,
                "timestamp": song.timestamp,
                "analyzed_by_llm": (
                    song.analyzed_by_llm if song.analyzed_by_llm is not None else False
                ),
                "created_at": now,
                "updated_at": now,
            }
            for song in songs
        ]
        stmt = insert(Songs).values(rows).returning(Songs)
        result = await self.session.execute(stmt)
        inserted = result.scalars().all()
        await self.session.flush()
        return [Song.model_validate(row) for row in inserted]
