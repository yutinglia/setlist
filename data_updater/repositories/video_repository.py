from datetime import UTC, datetime

from sqlalchemy import case, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Videos
from models.video import (
    ANALYSIS_PENDING,
    ANALYSIS_SKIPPED,
    YouTubeVideo,
)
from utils.video_type import (
    VIDEO_TYPE_KARAOKE,
    classify_video_type,
    should_scrape_comments,
)
from utils.youtube_upload_date import (
    UPLOAD_DATE_APPROXIMATE,
    UPLOAD_DATE_EXACT,
    best_upload_date_info,
)
from utils.ytdlp_snapshot import merged_video_metadata, snapshot_payload

# Columns refreshed from channel/video list scrapes. Analysis fields are preserved.
_METADATA_UPDATE_KEYS = (
    "title",
    "url",
    "channel_id",
    "upload_date",
    "upload_date_precision",
    "playlist_position",
    "type",
    "raw_data",
    "metadata_raw_data",
    "list_scraped_at",
    "metadata_scraped_at",
)


def _effective_upload_date_order():
    """Stable upload-date ordering.

    New writes always derive ``upload_date`` from timestamp metadata first.
    Migration V3 backfills old rows, avoiding unsafe JSON-to-float casts during
    every list query.
    """
    return Videos.upload_date


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
        list_data = snapshot_payload(model.raw_data)
        metadata_data = snapshot_payload(model.metadata_raw_data)
        derived = best_upload_date_info(list_data, metadata_data)
        if not derived:
            return model
        return model.model_copy(
            update={
                "upload_date": derived.value,
                "upload_date_precision": derived.precision,
            }
        )

    async def get_all(self) -> list[YouTubeVideo]:
        """從資料庫取得所有影片列表"""
        result = await self.session.execute(select(Videos))
        videos = result.scalars().all()
        return [self._to_model(video) for video in videos]

    async def get_by_id(self, video_id: str) -> YouTubeVideo | None:
        """根據 ID 取得單一影片"""
        result = await self.session.execute(select(Videos).where(Videos.id == video_id))
        video = result.scalar_one_or_none()
        return self._to_model(video) if video else None

    async def get_by_channel_id(
        self,
        channel_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
        video_type: str | None = None,
        has_song_list: bool | None = None,
    ) -> list[YouTubeVideo]:
        """List channel videos (optional pagination / type / setlist filter)."""
        stmt = select(Videos).where(Videos.channel_id == channel_id)
        if video_type is not None:
            stmt = stmt.where(Videos.type == video_type)
        if has_song_list is not None:
            stmt = stmt.where(Videos.has_song_list_comment.is_(has_song_list))
        stmt = stmt.order_by(
            _effective_upload_date_order().desc().nulls_last(),
            Videos.playlist_position.asc().nulls_last(),
            Videos.created_at.desc().nulls_last(),
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
        has_song_list: bool | None = None,
    ) -> int:
        """Count videos for ``channel_id`` (optional type / setlist filter)."""
        stmt = (
            select(func.count())
            .select_from(Videos)
            .where(Videos.channel_id == channel_id)
        )
        if video_type is not None:
            stmt = stmt.where(Videos.type == video_type)
        if has_song_list is not None:
            stmt = stmt.where(Videos.has_song_list_comment.is_(has_song_list))
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
                Videos.analysis_status.in_(("pending", "retry", "no_setlist")),
                func.coalesce(Videos.analyze_attempts, 0) < max_attempts,
                (
                    Videos.next_analysis_at.is_(None)
                    | (
                        Videos.next_analysis_at
                        <= datetime.now(UTC).replace(tzinfo=None)
                    )
                ),
            )
            .order_by(
                _effective_upload_date_order().desc().nulls_last(),
                Videos.playlist_position.asc().nulls_last(),
                Videos.created_at.desc().nulls_last(),
            )
            .limit(max(limit * 3, limit))
        )
        result = await self.session.execute(stmt)
        videos = result.scalars().all()
        out: list[YouTubeVideo] = []
        for video in videos:
            model = self._to_model(video)
            raw = merged_video_metadata(model.raw_data, model.metadata_raw_data)
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

    async def get_analysis_queue(
        self,
        *,
        max_attempts: int,
        limit: int,
        now: datetime | None = None,
    ) -> list[YouTubeVideo]:
        """Globally fair, newest-first queue of due karaoke archives."""
        if limit <= 0:
            return []
        due = now or datetime.now(UTC).replace(tzinfo=None)
        stmt = (
            select(Videos)
            .where(
                Videos.type == VIDEO_TYPE_KARAOKE,
                Videos.analysis_status.in_(("pending", "retry", "no_setlist")),
                func.coalesce(Videos.analyze_attempts, 0) < max_attempts,
                (Videos.next_analysis_at.is_(None) | (Videos.next_analysis_at <= due)),
            )
            .order_by(
                Videos.next_analysis_at.asc().nulls_first(),
                _effective_upload_date_order().desc().nulls_last(),
                Videos.playlist_position.asc().nulls_last(),
                Videos.created_at.desc().nulls_last(),
                Videos.id,
            )
            .limit(max(limit * 3, limit))
        )
        result = await self.session.execute(stmt)
        out: list[YouTubeVideo] = []
        for video in result.scalars().all():
            model = self._to_model(video)
            raw = merged_video_metadata(model.raw_data, model.metadata_raw_data)
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
        """Recompute ``type`` from list + full metadata for all channel videos.

        Full-video metadata overrides the flat-list observation. Does not
        commit. Returns how many rows changed.
        """
        result = await self.session.execute(
            select(Videos).where(Videos.channel_id == channel_id)
        )
        rows = result.scalars().all()
        now = datetime.now(UTC).replace(tzinfo=None)
        changed = 0
        for row in rows:
            raw = merged_video_metadata(row.raw_data, row.metadata_raw_data)
            new_type = classify_video_type(
                row.title or "",
                live_status=raw.get("live_status"),
                duration=raw.get("duration"),
            )
            if new_type == row.type:
                continue
            old_type = row.type
            row.type = new_type
            if new_type == VIDEO_TYPE_KARAOKE and old_type != VIDEO_TYPE_KARAOKE:
                # A row previously exhausted as non-karaoke must be eligible
                # once corrected metadata/title classifies it as karaoke.
                row.analyze_attempts = 0
                row.last_analyzed_at = None
                row.analysis_status = ANALYSIS_PENDING
                row.next_analysis_at = None
            elif new_type != VIDEO_TYPE_KARAOKE:
                row.analysis_status = ANALYSIS_SKIPPED
                row.next_analysis_at = None
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
        """Clear derived analysis state for videos that are not karaoke streams.

        Also sets ``analyze_attempts`` to ``max_attempts`` so the background
        updater never re-queues them. Raw comments and selected setlist inputs
        are preserved for future reclassification/parser improvements. Does
        not commit. Returns cleared video ids.
        """
        result = await self.session.execute(
            select(Videos).where(Videos.channel_id == channel_id)
        )
        rows = result.scalars().all()
        now = datetime.now(UTC).replace(tzinfo=None)
        cleared_ids: list[str] = []
        for row in rows:
            raw = merged_video_metadata(row.raw_data, row.metadata_raw_data)
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

            needs_clear = any(
                (
                    bool(row.has_song_list_comment),
                    row.analyze_attempts != max_attempts,
                    bool(row.cleaning_attempts),
                    row.last_analyzed_at is not None,
                    row.last_cleaned_at is not None,
                )
            )
            if not needs_clear:
                continue

            # Source observations are expensive and remain useful if rules
            # later classify this record as karaoke again.
            row.has_song_list_comment = False
            row.cleaned_song_list_comment = None
            # Exhaust attempts so the periodic updater never re-queues this row.
            row.analyze_attempts = max_attempts
            row.last_analyzed_at = None
            row.cleaning_attempts = 0
            row.last_cleaned_at = None
            row.analysis_status = ANALYSIS_SKIPPED
            row.next_analysis_at = None
            row.updated_at = now
            cleared_ids.append(row.id)

        if cleared_ids:
            await self.session.flush()
        return cleared_ids

    async def upsert(self, video: YouTubeVideo) -> YouTubeVideo:
        """Insert or update video metadata by primary key ``id``.

        On conflict, only scrape metadata is updated so analysis fields
        (attempts, song-list flags, comments) are preserved. Does not commit.

        Flat extracts use an approximate date. Never overwrite an exact date
        with NULL or an approximate value on conflict.
        """
        now = datetime.now(UTC).replace(tzinfo=None)
        insert_values = self._to_row_values(video, now)
        update_values = {key: insert_values[key] for key in _METADATA_UPDATE_KEYS}
        incoming_date = insert_values["upload_date"]
        incoming_precision = insert_values["upload_date_precision"]
        if incoming_date is None:
            update_values["upload_date"] = Videos.upload_date
            update_values["upload_date_precision"] = Videos.upload_date_precision
        elif incoming_precision == UPLOAD_DATE_APPROXIMATE:
            # Legacy non-null dates without precision are treated as
            # authoritative. Migration V8 fills their precision explicitly.
            existing_is_authoritative = Videos.upload_date.is_not(None) & (
                Videos.upload_date_precision.is_(None)
                | (Videos.upload_date_precision == UPLOAD_DATE_EXACT)
            )
            update_values["upload_date"] = case(
                (existing_is_authoritative, Videos.upload_date),
                else_=incoming_date,
            )
            update_values["upload_date_precision"] = case(
                (
                    existing_is_authoritative,
                    func.coalesce(
                        Videos.upload_date_precision,
                        UPLOAD_DATE_EXACT,
                    ),
                ),
                else_=UPLOAD_DATE_APPROXIMATE,
            )
        else:
            # Exact full metadata upgrades an approximate list date.
            update_values["upload_date"] = incoming_date
            update_values["upload_date_precision"] = UPLOAD_DATE_EXACT
        update_values["playlist_position"] = func.coalesce(
            insert_values["playlist_position"],
            Videos.playlist_position,
        )
        # Keep one latest observation per source. A sparse channel-tab snapshot
        # cannot erase the separate, richer full-video metadata snapshot.
        if insert_values["raw_data"] is None:
            update_values["raw_data"] = Videos.raw_data
            update_values["list_scraped_at"] = Videos.list_scraped_at
        else:
            update_values["raw_data"] = insert_values["raw_data"]
            update_values["list_scraped_at"] = insert_values["list_scraped_at"] or now
        if insert_values["metadata_raw_data"] is None:
            update_values["metadata_raw_data"] = Videos.metadata_raw_data
            update_values["metadata_scraped_at"] = Videos.metadata_scraped_at
        else:
            update_values["metadata_raw_data"] = insert_values["metadata_raw_data"]
            update_values["metadata_scraped_at"] = (
                insert_values["metadata_scraped_at"] or now
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
        now = datetime.now(UTC).replace(tzinfo=None)
        stmt = (
            update(Videos)
            .where(Videos.id == video.id)
            .values(
                comments_raw_data=video.comments_raw_data,
                analyze_attempts=video.analyze_attempts,
                last_analyzed_at=video.last_analyzed_at,
                has_song_list_comment=video.has_song_list_comment,
                song_list_comment_raw_data=video.song_list_comment_raw_data,
                cleaning_attempts=video.cleaning_attempts,
                last_cleaned_at=video.last_cleaned_at,
                cleaned_song_list_comment=video.cleaned_song_list_comment,
                analysis_status=video.analysis_status,
                next_analysis_at=video.next_analysis_at,
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
            "upload_date_precision": video.upload_date_precision,
            "playlist_position": video.playlist_position,
            "type": video.type,
            "raw_data": video.raw_data,
            "metadata_raw_data": video.metadata_raw_data,
            "list_scraped_at": video.list_scraped_at,
            "metadata_scraped_at": video.metadata_scraped_at,
            "comments_raw_data": video.comments_raw_data,
            "analyze_attempts": video.analyze_attempts,
            "last_analyzed_at": video.last_analyzed_at,
            "has_song_list_comment": video.has_song_list_comment,
            "song_list_comment_raw_data": video.song_list_comment_raw_data,
            "cleaning_attempts": video.cleaning_attempts,
            "last_cleaned_at": video.last_cleaned_at,
            "cleaned_song_list_comment": video.cleaned_song_list_comment,
            "analysis_status": video.analysis_status,
            "next_analysis_at": video.next_analysis_at,
            "created_at": video.created_at or now,
            "updated_at": now,
        }
