from datetime import datetime, timezone

from sqlalchemy import Float, cast, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Videos
from models.video import YouTubeVideo
from utils.video_type import (
    PERSISTED_VIDEO_TYPES,
    VIDEO_TYPE_KARAOKE,
    classify_video_type,
    should_scrape_comments,
)
from utils.youtube_upload_date import upload_date_from_entry

# Columns refreshed from channel/video list scrapes. Analysis fields are preserved.
_METADATA_UPDATE_KEYS = (
    "title",
    "url",
    "channel_id",
    "upload_date",
    "type",
    "raw_data",
)


def _effective_upload_date_order():
    """``upload_date`` or YYYYMMDD derived from flat-extract timestamps."""
    ts = cast(Videos.raw_data["timestamp"].as_string(), Float)
    release_ts = cast(Videos.raw_data["release_timestamp"].as_string(), Float)
    return func.coalesce(
        Videos.upload_date,
        func.to_char(func.to_timestamp(ts), "YYYYMMDD"),
        func.to_char(func.to_timestamp(release_ts), "YYYYMMDD"),
    )


class VideoRepository:
    """Video read/write access. Does not commit — caller owns transactions."""

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _to_model(video: Videos) -> YouTubeVideo:
        """ORM → DTO, filling ``upload_date`` from raw_data when the column is empty."""
        model = YouTubeVideo.model_validate(video)
        if (model.upload_date or "").strip():
            return model
        derived = upload_date_from_entry(
            model.raw_data if isinstance(model.raw_data, dict) else None
        )
        if not derived:
            return model
        return model.model_copy(update={"upload_date": derived})

    async def get_all(self) -> list[YouTubeVideo]:
        """從資料庫取得所有影片列表"""
        result = await self.session.execute(select(Videos))
        videos = result.scalars().all()
        return [self._to_model(video) for video in videos]

    async def get_by_id(self, video_id: str) -> YouTubeVideo | None:
        """根據 ID 取得單一影片"""
        result = await self.session.execute(
            select(Videos).where(Videos.id == video_id)
        )
        video = result.scalar_one_or_none()
        return self._to_model(video) if video else None

    async def get_by_channel_id(
        self,
        channel_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
        video_type: str | None = None,
    ) -> list[YouTubeVideo]:
        """根據頻道 ID 取得該頻道的影片列表 (optional pagination / type filter)."""
        stmt = select(Videos).where(Videos.channel_id == channel_id)
        if video_type is not None:
            stmt = stmt.where(Videos.type == video_type)
        stmt = stmt.order_by(
            _effective_upload_date_order().desc().nulls_last(),
            Videos.id,
        )
        if limit is not None:
            stmt = stmt.limit(limit).offset(offset)
        elif offset:
            stmt = stmt.offset(offset)
        result = await self.session.execute(stmt)
        videos = result.scalars().all()
        return [self._to_model(video) for video in videos]

    async def count_by_channel_id(
        self,
        channel_id: str,
        *,
        video_type: str | None = None,
    ) -> int:
        """Count videos for ``channel_id`` (optional type filter)."""
        stmt = (
            select(func.count())
            .select_from(Videos)
            .where(Videos.channel_id == channel_id)
        )
        if video_type is not None:
            stmt = stmt.where(Videos.type == video_type)
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def get_needing_analysis(
        self,
        channel_id: str,
        *,
        max_attempts: int,
        limit: int,
    ) -> list[YouTubeVideo]:
        """Karaoke stream records that still need comment analysis.

        Prefers ``type=karaoke`` rows, then re-checks title/metadata so song /
        MV / cover uploads are never queued even if ``type`` is stale.
        """
        if limit <= 0:
            return []

        # Over-fetch then filter: song titles must not consume the analyze quota.
        stmt = (
            select(Videos)
            .where(
                Videos.channel_id == channel_id,
                Videos.type == VIDEO_TYPE_KARAOKE,
                Videos.has_song_list_comment.is_(False),
                Videos.analyze_attempts < max_attempts,
            )
            .order_by(_effective_upload_date_order().desc().nulls_last())
            .limit(max(limit * 3, limit))
        )
        result = await self.session.execute(stmt)
        videos = result.scalars().all()
        out: list[YouTubeVideo] = []
        for video in videos:
            model = self._to_model(video)
            raw = model.raw_data if isinstance(model.raw_data, dict) else {}
            if not should_scrape_comments(
                model.title or "",
                live_status=raw.get("live_status"),
                duration=raw.get("duration"),
                stored_type=model.type,
            ):
                continue
            out.append(model)
            if len(out) >= limit:
                break
        return out

    async def reclassify_for_channel(self, channel_id: str) -> int:
        """Recompute ``type`` from title + stored raw_data for all channel videos.

        Uses ``live_status`` / ``duration`` from ``raw_data`` when present (soft
        karaoke confirms). Does not commit. Returns how many rows changed.
        """
        result = await self.session.execute(
            select(Videos).where(Videos.channel_id == channel_id)
        )
        rows = result.scalars().all()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        changed = 0
        for row in rows:
            raw = row.raw_data if isinstance(row.raw_data, dict) else {}
            new_type = classify_video_type(
                row.title or "",
                live_status=raw.get("live_status"),
                duration=raw.get("duration"),
            )
            if new_type == row.type:
                continue
            row.type = new_type
            row.updated_at = now
            changed += 1
        if changed:
            await self.session.flush()
        return changed

    async def clear_analysis_for_non_karaoke(
        self,
        channel_id: str,
        *,
        max_attempts: int,
    ) -> list[str]:
        """Clear comment/setlist data for videos that are not karaoke streams.

        Also sets ``analyze_attempts`` to ``max_attempts`` so the background
        updater never re-queues them. Does not commit. Returns cleared video ids.
        """
        result = await self.session.execute(
            select(Videos).where(Videos.channel_id == channel_id)
        )
        rows = result.scalars().all()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        cleared_ids: list[str] = []
        for row in rows:
            raw = row.raw_data if isinstance(row.raw_data, dict) else {}
            live_status = raw.get("live_status")
            duration = raw.get("duration")
            # Keep stored type in sync while deciding.
            new_type = classify_video_type(
                row.title or "",
                live_status=live_status,
                duration=duration,
            )
            if row.type != new_type:
                row.type = new_type

            if should_scrape_comments(
                row.title or "",
                live_status=live_status,
                duration=duration,
                stored_type=new_type,
            ):
                continue

            row.comments_raw_data = None
            row.song_list_comment_raw_data = None
            row.cleaned_song_list_comment = None
            row.has_song_list_comment = False
            # Exhaust attempts so the periodic updater never re-queues this row.
            row.analyze_attempts = max_attempts
            row.updated_at = now
            cleared_ids.append(row.id)

        if cleared_ids:
            await self.session.flush()
        return cleared_ids

    async def delete_all_for_channel(self, channel_id: str) -> int:
        """Delete every video for ``channel_id`` (cascades songs). Does not commit."""
        result = await self.session.execute(
            delete(Videos).where(Videos.channel_id == channel_id)
        )
        await self.session.flush()
        return int(result.rowcount or 0)

    async def delete_non_persisted_for_channel(self, channel_id: str) -> int:
        """Delete videos that are not song/karaoke (type ``other`` or legacy).

        Cascades to ``songs``. Does not commit. Returns number of rows deleted.
        """
        # Reclassify first so type reflects current title rules.
        await self.reclassify_for_channel(channel_id)

        result = await self.session.execute(
            select(Videos).where(Videos.channel_id == channel_id)
        )
        rows = result.scalars().all()
        to_delete: list[str] = []
        for row in rows:
            raw = row.raw_data if isinstance(row.raw_data, dict) else {}
            classified = classify_video_type(
                row.title or "",
                live_status=raw.get("live_status"),
                duration=raw.get("duration"),
            )
            if classified in PERSISTED_VIDEO_TYPES:
                if row.type != classified:
                    row.type = classified
                continue
            to_delete.append(row.id)

        if not to_delete:
            await self.session.flush()
            return 0

        await self.session.execute(
            delete(Videos).where(Videos.id.in_(to_delete))
        )
        await self.session.flush()
        return len(to_delete)

    async def upsert(self, video: YouTubeVideo) -> YouTubeVideo:
        """Insert or update video metadata by primary key ``id``.

        On conflict, only scrape metadata is updated so analysis fields
        (attempts, song-list flags, comments) are preserved. Does not commit.

        Flat extracts often omit ``upload_date``; never overwrite a known date
        with NULL on conflict.
        """
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        insert_values = self._to_row_values(video, now)
        update_values = {
            key: insert_values[key] for key in _METADATA_UPDATE_KEYS
        }
        # Prefer newly scraped date; keep existing when scrape has none.
        update_values["upload_date"] = func.coalesce(
            insert_values["upload_date"],
            Videos.upload_date,
        )
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
        return self._to_model(row)

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
                cleaning_attempts=(
                    video.cleaning_attempts
                    if video.cleaning_attempts is not None
                    else 0
                ),
                last_cleaned_at=video.last_cleaned_at,
                cleaned_song_list_comment=video.cleaned_song_list_comment,
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
