from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Channels, Songs, Videos
from models.search import SongSearchResult
from models.song import Song
from utils.youtube_timestamp import youtube_url_with_timestamp


class SongRepository:
    """Song read/write access. Does not commit — caller owns transactions.

    **Re-analysis / conflict policy:** ``replace_for_video`` is authoritative.
    Each successful analysis deletes all songs for that ``video_id`` and inserts
    the new list — there is no merge with the previous setlist. Last successful
    write wins. Within a single extract, ``CommentAnalyzer`` already drops
    duplicate ``(timestamp, casefold(title))`` rows (first occurrence kept).
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

    async def get_by_video_id(
        self,
        video_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Song]:
        """根據影片 ID 取得該影片的所有歌曲 (optional pagination)."""
        stmt = select(Songs).where(Songs.video_id == video_id).order_by(Songs.id)
        if limit is not None:
            stmt = stmt.limit(limit).offset(offset)
        elif offset:
            stmt = stmt.offset(offset)
        result = await self.session.execute(stmt)
        songs = result.scalars().all()
        return [Song.model_validate(song) for song in songs]

    async def count_by_video_id(self, video_id: str) -> int:
        """Count songs belonging to ``video_id``."""
        result = await self.session.execute(
            select(func.count()).select_from(Songs).where(Songs.video_id == video_id)
        )
        return int(result.scalar_one())

    async def search_by_title(
        self,
        query: str,
        *,
        limit: int,
        offset: int = 0,
    ) -> tuple[list[SongSearchResult], int]:
        """ILIKE search on ``songs.title`` with video/channel context.

        Returns ``(items, total)``. Empty ``query`` yields no rows.
        """
        q = query.strip()
        if not q:
            return [], 0

        pattern = f"%{q}%"
        base = (
            select(Songs, Videos, Channels)
            .join(Videos, Songs.video_id == Videos.id)
            .join(Channels, Videos.channel_id == Channels.id)
            .where(Songs.title.ilike(pattern))
        )
        count_stmt = select(func.count()).select_from(base.subquery())
        total = int((await self.session.execute(count_stmt)).scalar_one())

        page_stmt = base.order_by(Songs.id).limit(limit).offset(offset)
        rows = (await self.session.execute(page_stmt)).all()
        items = [
            SongSearchResult.from_parts(
                song=Song.model_validate(song),
                video_url=video.url,
                video_title=video.title,
                channel_id=channel.id,
                channel_name=channel.name,
                deep_link_url=youtube_url_with_timestamp(video.url, song.timestamp),
            )
            for song, video, channel in rows
        ]
        return items, total

    async def get_detail(self, song_id: int) -> SongSearchResult | None:
        """Song detail with video deep link and channel info."""
        stmt = (
            select(Songs, Videos, Channels)
            .join(Videos, Songs.video_id == Videos.id)
            .join(Channels, Videos.channel_id == Channels.id)
            .where(Songs.id == song_id)
        )
        row = (await self.session.execute(stmt)).one_or_none()
        if row is None:
            return None
        song, video, channel = row
        return SongSearchResult.from_parts(
            song=Song.model_validate(song),
            video_url=video.url,
            video_title=video.title,
            channel_id=channel.id,
            channel_name=channel.name,
            deep_link_url=youtube_url_with_timestamp(video.url, song.timestamp),
        )

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
