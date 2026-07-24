from datetime import datetime, timezone

from sqlalchemy import case, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Videos
from models.video import YouTubeVideo

# Columns refreshed from channel/video list scrapes. Analysis fields are preserved.
_METADATA_UPDATE_KEYS = (
    "title",
    "url",
    "channel_id",
    "upload_date",
    "type",
    "raw_data",
)


class VideoRepository:
    """Video read/write access. Does not commit — caller owns transactions."""

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

    async def get_needing_analysis(
        self,
        channel_id: str,
        *,
        max_attempts: int,
        limit: int,
    ) -> list[YouTubeVideo]:
        """Videos that still need comment analysis.

        Prefers karaoke-ish titles, then newest ``upload_date``.
        Skips rows that already have a song-list comment or have exhausted
        ``analyze_attempts`` (>= ``max_attempts``).
        """
        if limit <= 0:
            return []

        karaoke_rank = case(
            (Videos.title.ilike("%歌枠%"), 0),
            (Videos.title.ilike("%karaoke%"), 0),
            (Videos.title.ilike("%カラOK%"), 0),
            (Videos.title.ilike("%歌回%"), 0),
            else_=1,
        )
        stmt = (
            select(Videos)
            .where(
                Videos.channel_id == channel_id,
                Videos.has_song_list_comment.is_(False),
                Videos.analyze_attempts < max_attempts,
            )
            .order_by(karaoke_rank, Videos.upload_date.desc().nulls_last())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        videos = result.scalars().all()
        return [YouTubeVideo.model_validate(video) for video in videos]

    async def upsert(self, video: YouTubeVideo) -> YouTubeVideo:
        """Insert or update video metadata by primary key ``id``.

        On conflict, only scrape metadata is updated so analysis fields
        (attempts, song-list flags, comments) are preserved. Does not commit.
        """
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        insert_values = self._to_row_values(video, now)
        update_values = {
            key: insert_values[key] for key in _METADATA_UPDATE_KEYS
        }
        update_values["updated_at"] = now

        stmt = (
            insert(Videos)
            .values(**insert_values)
            .on_conflict_do_update(
                index_elements=[Videos.id],
                set_=update_values,
            )
            .returning(Videos)
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one()
        await self.session.flush()
        return YouTubeVideo.model_validate(row)

    async def upsert_many(self, videos: list[YouTubeVideo]) -> list[YouTubeVideo]:
        """Upsert multiple videos. Does not commit. Returns rows in input order."""
        return [await self.upsert(video) for video in videos]

    async def update_analysis(self, video: YouTubeVideo) -> YouTubeVideo:
        """Persist analysis / comment fields for an existing video. Does not commit."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        stmt = (
            update(Videos)
            .where(Videos.id == video.id)
            .values(
                comments_raw_data=video.comments_raw_data,
                analyze_attempts=(
                    video.analyze_attempts if video.analyze_attempts is not None else 0
                ),
                last_analyzed_at=video.last_analyzed_at,
                has_song_list_comment=(
                    video.has_song_list_comment
                    if video.has_song_list_comment is not None
                    else False
                ),
                song_list_comment_raw_data=video.song_list_comment_raw_data,
                updated_at=now,
            )
            .returning(Videos)
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one()
        await self.session.flush()
        return YouTubeVideo.model_validate(row)

    @staticmethod
    def _to_row_values(video: YouTubeVideo, now: datetime) -> dict:
        return {
            "id": video.id,
            "title": video.title,
            "url": video.url,
            "channel_id": video.channel_id,
            "upload_date": video.upload_date,
            "type": video.type,
            "raw_data": video.raw_data,
            "comments_raw_data": video.comments_raw_data,
            "analyze_attempts": video.analyze_attempts if video.analyze_attempts is not None else 0,
            "last_analyzed_at": video.last_analyzed_at,
            "has_song_list_comment": (
                video.has_song_list_comment
                if video.has_song_list_comment is not None
                else False
            ),
            "song_list_comment_raw_data": video.song_list_comment_raw_data,
            "cleaning_attempts": (
                video.cleaning_attempts if video.cleaning_attempts is not None else 0
            ),
            "last_cleaned_at": video.last_cleaned_at,
            "cleaned_song_list_comment": video.cleaned_song_list_comment,
            "created_at": video.created_at or now,
            "updated_at": now,
        }
