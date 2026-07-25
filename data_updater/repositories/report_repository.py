"""Aggregate read model for the summary report page."""

from datetime import UTC, datetime

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Channels, Songs, Videos
from models.report import (
    AnalysisReport,
    AnalysisStatusReport,
    BackfillReport,
    SongReport,
    SummaryReport,
    VideoReport,
)


class ReportRepository:
    """Read-only aggregate queries. Does not commit."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_summary(self) -> SummaryReport:
        channel_counts = (
            await self.session.execute(
                select(
                    func.count().label("total"),
                    func.count()
                    .filter(Channels.video_backfill_status == "pending")
                    .label("pending"),
                    func.count()
                    .filter(Channels.video_backfill_status == "running")
                    .label("running"),
                    func.count()
                    .filter(Channels.video_backfill_status == "done")
                    .label("done"),
                    func.count()
                    .filter(Channels.video_backfill_status == "failed")
                    .label("failed"),
                )
            )
        ).one()

        comments_value = Videos.comments_raw_data["comments"]
        comments_per_video = case(
            (
                func.jsonb_typeof(comments_value) == "array",
                func.jsonb_array_length(comments_value),
            ),
            else_=0,
        )
        video_counts = (
            await self.session.execute(
                select(
                    func.count().label("total"),
                    func.count().filter(Videos.type == "karaoke").label("karaoke"),
                    func.count().filter(Videos.type == "song").label("song"),
                    func.max(Videos.created_at).label("latest_discovered_at"),
                    func.count()
                    .filter(Videos.last_analyzed_at.is_not(None))
                    .label("attempted"),
                    func.count()
                    .filter(Videos.has_song_list_comment.is_(True))
                    .label("with_setlist"),
                    func.count()
                    .filter(Videos.comments_raw_data.is_not(None))
                    .label("videos_with_comments"),
                    func.coalesce(func.sum(comments_per_video), 0).label("comments"),
                    func.max(Videos.last_analyzed_at).label("latest_analyzed_at"),
                    func.count()
                    .filter(Videos.analysis_status == "pending")
                    .label("analysis_pending"),
                    func.count()
                    .filter(Videos.analysis_status == "retry")
                    .label("analysis_retry"),
                    func.count()
                    .filter(Videos.analysis_status == "no_setlist")
                    .label("analysis_no_setlist"),
                    func.count()
                    .filter(Videos.analysis_status == "done")
                    .label("analysis_done"),
                    func.count()
                    .filter(Videos.analysis_status == "exhausted")
                    .label("analysis_exhausted"),
                    func.count()
                    .filter(Videos.analysis_status == "skipped")
                    .label("analysis_skipped"),
                )
            )
        ).one()

        song_counts = (
            await self.session.execute(
                select(
                    func.count().label("total"),
                    func.count()
                    .filter(Songs.analyzed_by_llm.is_(True))
                    .label("analyzed_by_llm"),
                )
            )
        ).one()

        return SummaryReport(
            generated_at=datetime.now(UTC).replace(tzinfo=None),
            channels=int(channel_counts.total),
            backfill=BackfillReport(
                pending=int(channel_counts.pending),
                running=int(channel_counts.running),
                done=int(channel_counts.done),
                failed=int(channel_counts.failed),
            ),
            videos=VideoReport(
                total=int(video_counts.total),
                karaoke=int(video_counts.karaoke),
                song=int(video_counts.song),
                latest_discovered_at=video_counts.latest_discovered_at,
            ),
            analysis=AnalysisReport(
                attempted=int(video_counts.attempted),
                with_setlist=int(video_counts.with_setlist),
                videos_with_comments=int(video_counts.videos_with_comments),
                comments=int(video_counts.comments),
                latest_analyzed_at=video_counts.latest_analyzed_at,
                status=AnalysisStatusReport(
                    pending=int(video_counts.analysis_pending),
                    retry=int(video_counts.analysis_retry),
                    no_setlist=int(video_counts.analysis_no_setlist),
                    done=int(video_counts.analysis_done),
                    exhausted=int(video_counts.analysis_exhausted),
                    skipped=int(video_counts.analysis_skipped),
                ),
            ),
            songs=SongReport(
                total=int(song_counts.total),
                analyzed_by_llm=int(song_counts.analyzed_by_llm),
            ),
        )
