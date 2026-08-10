from datetime import UTC, datetime

from sqlalchemy import case, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Channels, Songs, Videos
from models.search import SetlistContributor, SongSearchResult, SongSuggestion
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
        result = await self.session.execute(select(Songs).where(Songs.id == song_id))
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
        channel_ids: list[str] | None = None,
        video_type: str | None = None,
        upload_date_from: str | None = None,
        upload_date_to: str | None = None,
    ) -> tuple[list[SongSearchResult], int]:
        """ILIKE search on ``songs.title`` with video/channel context.

        Optional filters narrow by channel, video type, and inclusive
        ``YYYYMMDD`` upload-date bounds. When either date bound is set, rows
        with a null ``upload_date`` are excluded.

        Returns ``(items, total)``. Empty ``query`` yields no rows.
        """
        q = query.strip()
        if not q:
            return [], 0

        # Treat user input literally: SQL LIKE wildcards in titles are data,
        # not an alternate query language.
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        base = (
            select(Songs, Videos, Channels)
            .join(Videos, Songs.video_id == Videos.id)
            .join(Channels, Videos.channel_id == Channels.id)
            .where(Songs.title.ilike(pattern, escape="\\"))
        )
        if channel_ids:
            base = base.where(Videos.channel_id.in_(channel_ids))
        if video_type is not None:
            base = base.where(Videos.type == video_type)
        if upload_date_from is not None or upload_date_to is not None:
            base = base.where(Videos.upload_date.is_not(None))
            if upload_date_from is not None:
                base = base.where(Videos.upload_date >= upload_date_from)
            if upload_date_to is not None:
                base = base.where(Videos.upload_date <= upload_date_to)

        count_stmt = select(func.count()).select_from(base.subquery())
        total = int((await self.session.execute(count_stmt)).scalar_one())

        page_stmt = (
            base.order_by(
                Videos.upload_date.desc().nulls_last(),
                Songs.id,
            )
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.session.execute(page_stmt)).all()
        items = [
            SongSearchResult.from_parts(
                song=Song.model_validate(song),
                video_title=video.title,
                channel_id=channel.id,
                channel_name=channel.name,
                deep_link_url=youtube_url_with_timestamp(video.url, song.timestamp),
                setlist_comment_author=video.setlist_comment_author,
                setlist_comment_author_id=video.setlist_comment_author_id,
                setlist_comment_id=video.setlist_comment_id,
            )
            for song, video, channel in rows
        ]
        return items, total

    async def suggest_titles(
        self,
        query: str,
        *,
        limit: int = 8,
        channel_ids: list[str] | None = None,
        video_type: str | None = None,
        upload_date_from: str | None = None,
        upload_date_to: str | None = None,
    ) -> list[SongSuggestion]:
        """Return lightweight, case-insensitively deduplicated title suggestions."""
        q = query.strip()
        if not q:
            return []

        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        contains_pattern = f"%{escaped}%"
        prefix_pattern = f"{escaped.lower()}%"
        normalized_title = func.lower(Songs.title)
        occurrences = func.count(Songs.id).label("occurrences")

        stmt = (
            select(
                func.min(Songs.title).label("title"),
                occurrences,
            )
            .select_from(Songs)
            .where(Songs.title.ilike(contains_pattern, escape="\\"))
        )
        if (
            channel_ids
            or video_type is not None
            or upload_date_from is not None
            or upload_date_to is not None
        ):
            stmt = stmt.join(Videos, Songs.video_id == Videos.id)
            if channel_ids:
                stmt = stmt.where(Videos.channel_id.in_(channel_ids))
            if video_type is not None:
                stmt = stmt.where(Videos.type == video_type)
            if upload_date_from is not None or upload_date_to is not None:
                stmt = stmt.where(Videos.upload_date.is_not(None))
                if upload_date_from is not None:
                    stmt = stmt.where(Videos.upload_date >= upload_date_from)
                if upload_date_to is not None:
                    stmt = stmt.where(Videos.upload_date <= upload_date_to)

        stmt = (
            stmt.group_by(normalized_title)
            .order_by(
                case((normalized_title == q.lower(), 0), else_=1),
                case(
                    (
                        normalized_title.like(prefix_pattern, escape="\\"),
                        0,
                    ),
                    else_=1,
                ),
                occurrences.desc(),
                normalized_title,
            )
            .limit(limit)
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            SongSuggestion(title=row.title, occurrences=int(row.occurrences))
            for row in rows
        ]

    async def list_setlist_contributors(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[SetlistContributor], int]:
        """Aggregate indexed songs and source videos by stable comment author id."""
        author_label = func.max(Videos.setlist_comment_author).label("author")
        song_count = func.count(Songs.id).label("song_count")
        video_count = func.count(func.distinct(Videos.id)).label("video_count")
        eligible = (
            Videos.has_song_list_comment.is_(True)
            & Videos.setlist_comment_author.is_not(None)
            & Videos.setlist_comment_author_id.is_not(None)
        )
        stmt = (
            select(
                Videos.setlist_comment_author_id.label("author_id"),
                author_label,
                song_count,
                video_count,
            )
            .select_from(Videos)
            .join(Songs, Songs.video_id == Videos.id)
            .where(eligible)
            .group_by(Videos.setlist_comment_author_id)
            .order_by(
                song_count.desc(),
                video_count.desc(),
                func.lower(author_label),
                Videos.setlist_comment_author_id,
            )
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.session.execute(stmt)).all()
        total = int(
            (
                await self.session.execute(
                    select(func.count(func.distinct(Videos.setlist_comment_author_id)))
                    .select_from(Videos)
                    .join(Songs, Songs.video_id == Videos.id)
                    .where(eligible)
                )
            ).scalar_one()
        )
        return (
            [
                SetlistContributor(
                    author=row.author,
                    author_id=row.author_id,
                    song_count=int(row.song_count),
                    video_count=int(row.video_count),
                )
                for row in rows
            ],
            total,
        )

    async def get_recent(self, *, limit: int) -> list[SongSearchResult]:
        """Return the most recently persisted songs with catalog context."""
        stmt = (
            select(Songs, Videos, Channels)
            .join(Videos, Songs.video_id == Videos.id)
            .join(Channels, Videos.channel_id == Channels.id)
            .order_by(Songs.updated_at.desc().nulls_last(), Songs.id.desc())
            .limit(limit)
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            SongSearchResult.from_parts(
                song=Song.model_validate(song),
                video_title=video.title,
                channel_id=channel.id,
                channel_name=channel.name,
                deep_link_url=youtube_url_with_timestamp(video.url, song.timestamp),
                setlist_comment_author=video.setlist_comment_author,
                setlist_comment_author_id=video.setlist_comment_author_id,
                setlist_comment_id=video.setlist_comment_id,
            )
            for song, video, channel in rows
        ]

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
            video_title=video.title,
            channel_id=channel.id,
            channel_name=channel.name,
            deep_link_url=youtube_url_with_timestamp(video.url, song.timestamp),
            setlist_comment_author=video.setlist_comment_author,
            setlist_comment_author_id=video.setlist_comment_author_id,
            setlist_comment_id=video.setlist_comment_id,
        )

    async def replace_for_video(self, video_id: str, songs: list[Song]) -> list[Song]:
        """Replace all songs for ``video_id`` (delete + insert). Does not commit.

        Each song's ``video_id`` is forced to the given ``video_id``.
        """
        await self.session.execute(delete(Songs).where(Songs.video_id == video_id))

        if not songs:
            await self.session.flush()
            return []

        now = datetime.now(UTC).replace(tzinfo=None)
        rows = [
            {
                "title": song.title,
                "video_id": video_id,
                "timestamp": song.timestamp,
                "analyzed_by_llm": song.analyzed_by_llm,
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
