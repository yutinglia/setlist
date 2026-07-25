"""Integration tests for repository write path.

Requires a reachable Postgres (Compose/Dev Container defaults).
Skipped automatically when the database is unavailable.
"""

import os
import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from models.channel import YouTubeChannel
from models.song import Song
from models.video import YouTubeVideo
from repositories.channel_repository import ChannelRepository
from repositories.report_repository import ReportRepository
from repositories.song_repository import SongRepository
from repositories.video_repository import VideoRepository


def _database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://vks_db_user:vks_db_pwd@localhost:5432/vks_db",
    )


async def _db_available(url: str) -> bool:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def session():
    url = _database_url()
    if not await _db_available(url):
        pytest.skip("Postgres not available for repository integration tests")

    engine = create_async_engine(url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        try:
            yield sess
            await sess.rollback()
        finally:
            await sess.close()
    await engine.dispose()


@pytest.mark.asyncio
async def test_upsert_channel_video_and_replace_songs(session: AsyncSession):
    suffix = uuid.uuid4().hex[:8]
    channel_id = f"ch_test_{suffix}"
    video_id = f"vid_test_{suffix}"

    channel_repo = ChannelRepository(session)
    video_repo = VideoRepository(session)
    song_repo = SongRepository(session)
    report_repo = ReportRepository(session)
    before = await report_repo.get_summary()

    channel = await channel_repo.create(
        YouTubeChannel(
            id=channel_id,
            name="Test Channel",
            url=f"https://www.youtube.com/channel/{channel_id}",
        )
    )
    assert channel is not None
    assert channel.id == channel_id
    duplicate = await channel_repo.create(
        YouTubeChannel(
            id=channel_id,
            name="Duplicate",
            url=f"https://www.youtube.com/channel/{channel_id}",
        )
    )
    assert duplicate is None

    video = await video_repo.upsert(
        YouTubeVideo(
            id=video_id,
            title="Karaoke Test",
            url=f"https://www.youtube.com/watch?v={video_id}",
            channel_id=channel_id,
            type="karaoke",
            raw_data={"title": "Karaoke Test"},
            metadata_raw_data={"duration": 3600, "live_status": "was_live"},
        )
    )
    assert video.id == video_id

    # A later flat channel-tab scrape must update keys it knows without
    # destroying richer metadata used by classification.
    refreshed = await video_repo.upsert(
        YouTubeVideo(
            id=video_id,
            title="Karaoke Test (updated)",
            url=f"https://www.youtube.com/watch?v={video_id}",
            channel_id=channel_id,
            type="karaoke",
            raw_data={"title": "Karaoke Test (updated)"},
        )
    )
    assert refreshed.raw_data == {
        "title": "Karaoke Test (updated)",
    }
    assert refreshed.metadata_raw_data == {
        "duration": 3600,
        "live_status": "was_live",
    }
    refreshed.comments_raw_data = {"comments": [{"text": "one"}, {"text": "two"}]}
    refreshed.last_analyzed_at = datetime.now(UTC).replace(tzinfo=None)
    refreshed.has_song_list_comment = True
    refreshed.analysis_status = "done"
    await video_repo.update_analysis(refreshed)

    songs = await song_repo.replace_for_video(
        video_id,
        [
            Song(title="Song A", video_id=video_id, timestamp="0:10"),
            Song(title="Song B", video_id=video_id, timestamp="1:20"),
        ],
    )
    assert len(songs) == 2
    assert all(s.id is not None for s in songs)

    replaced = await song_repo.replace_for_video(
        video_id,
        [Song(title="Only Song", video_id=video_id, timestamp="2:00")],
    )
    assert len(replaced) == 1
    assert replaced[0].title == "Only Song"

    fetched = await song_repo.get_by_video_id(video_id)
    assert len(fetched) == 1
    assert fetched[0].title == "Only Song"

    await song_repo.replace_for_video(
        video_id,
        [
            Song(
                title="100% Love",
                video_id=video_id,
                timestamp="3:00",
                analyzed_by_llm=True,
            ),
            Song(title="1000 Love", video_id=video_id, timestamp="4:00"),
            Song(title="Under_score", video_id=video_id, timestamp="5:00"),
        ],
    )
    percent_hits, percent_total = await song_repo.search_by_title(
        "%", limit=20, offset=0, channel_id=channel_id
    )
    assert percent_total == 1
    assert [song.title for song in percent_hits] == ["100% Love"]
    underscore_hits, underscore_total = await song_repo.search_by_title(
        "_", limit=20, offset=0, channel_id=channel_id
    )
    assert underscore_total == 1
    assert [song.title for song in underscore_hits] == ["Under_score"]

    after = await report_repo.get_summary()
    assert after.channels == before.channels + 1
    assert after.backfill.done == before.backfill.done + 1
    assert after.videos.total == before.videos.total + 1
    assert after.videos.karaoke == before.videos.karaoke + 1
    assert after.videos.with_list_snapshot == before.videos.with_list_snapshot + 1
    assert (
        after.videos.with_metadata_snapshot == before.videos.with_metadata_snapshot + 1
    )
    assert after.videos.date_unknown == before.videos.date_unknown + 1
    assert after.analysis.attempted == before.analysis.attempted + 1
    assert after.analysis.with_setlist == before.analysis.with_setlist + 1
    assert (
        after.analysis.videos_with_comments == before.analysis.videos_with_comments + 1
    )
    assert after.analysis.comments == before.analysis.comments + 2
    assert after.analysis.status.done == before.analysis.status.done + 1
    assert after.songs.total == before.songs.total + 3
    assert after.songs.analyzed_by_llm == before.songs.analyzed_by_llm + 1
    assert after.videos.latest_discovered_at is not None
    assert after.analysis.latest_analyzed_at is not None

    # Leave DB clean even if outer rollback is skipped somehow
    await song_repo.replace_for_video(video_id, [])
    await session.rollback()


@pytest.mark.asyncio
async def test_non_karaoke_cleanup_preserves_expensive_source_observations(
    session: AsyncSession,
):
    suffix = uuid.uuid4().hex[:8]
    channel_id = f"ch_raw_{suffix}"
    video_id = f"vid_raw_{suffix}"
    channel_repo = ChannelRepository(session)
    video_repo = VideoRepository(session)
    await channel_repo.create(
        YouTubeChannel(
            id=channel_id,
            name="Raw Preservation Test",
            url=f"https://www.youtube.com/channel/{channel_id}",
        )
    )
    video = await video_repo.upsert(
        YouTubeVideo(
            id=video_id,
            title="Karaoke Test",
            url=f"https://www.youtube.com/watch?v={video_id}",
            channel_id=channel_id,
            type="karaoke",
            raw_data={"title": "Karaoke Test"},
            metadata_raw_data={"duration": 3600, "live_status": "was_live"},
        )
    )
    video.comments_raw_data = {
        "comments": [{"text": "0:10 Song A"}],
        "comments_available": True,
    }
    video.song_list_comment_raw_data = {"text": "0:10 Song A"}
    video.cleaned_song_list_comment = {"text": "0:10 Song A"}
    video.has_song_list_comment = True
    video.analysis_status = "done"
    video.last_analyzed_at = datetime.now(UTC).replace(tzinfo=None)
    video.cleaning_attempts = 1
    video.last_cleaned_at = video.last_analyzed_at
    await video_repo.update_analysis(video)

    # New full metadata proves the flat title was a false positive.
    await video_repo.upsert(
        video.model_copy(
            update={
                "type": "karaoke",
                "metadata_raw_data": {
                    "duration": 45,
                    "live_status": "not_live",
                },
            }
        )
    )
    assert await video_repo.reclassify_for_channel(channel_id) == 1
    assert await video_repo.clear_analysis_for_non_karaoke(
        channel_id,
        max_attempts=3,
    ) == [video_id]

    preserved = await video_repo.get_by_id(video_id)
    assert preserved is not None
    assert preserved.type == "other"
    assert preserved.analysis_status == "skipped"
    assert preserved.has_song_list_comment is False
    assert preserved.comments_raw_data == video.comments_raw_data
    assert preserved.song_list_comment_raw_data == video.song_list_comment_raw_data
    assert preserved.cleaned_song_list_comment is None
    assert preserved.analyze_attempts == 3

    await session.rollback()


@pytest.mark.asyncio
async def test_exact_upload_date_is_never_downgraded_by_flat_refresh(
    session: AsyncSession,
):
    suffix = uuid.uuid4().hex[:8]
    channel_id = f"ch_date_{suffix}"
    video_id = f"vid_date_{suffix}"
    channel_repo = ChannelRepository(session)
    video_repo = VideoRepository(session)
    await channel_repo.create(
        YouTubeChannel(
            id=channel_id,
            name="Date Test",
            url=f"https://www.youtube.com/channel/{channel_id}",
        )
    )

    approximate = await video_repo.upsert(
        YouTubeVideo(
            id=video_id,
            title="Karaoke",
            url=f"https://www.youtube.com/watch?v={video_id}",
            channel_id=channel_id,
            upload_date="20260726",
            upload_date_precision="approximate",
            type="karaoke",
            raw_data={"timestamp": 1_784_998_800},
        )
    )
    assert approximate.upload_date_precision == "approximate"

    exact = await video_repo.upsert(
        YouTubeVideo(
            id=video_id,
            title="Karaoke",
            url=f"https://www.youtube.com/watch?v={video_id}",
            channel_id=channel_id,
            upload_date="20260725",
            upload_date_precision="exact",
            type="karaoke",
            raw_data={"upload_date": "20260725"},
        )
    )
    assert (exact.upload_date, exact.upload_date_precision) == (
        "20260725",
        "exact",
    )

    preserved = await video_repo.upsert(
        YouTubeVideo(
            id=video_id,
            title="Karaoke",
            url=f"https://www.youtube.com/watch?v={video_id}",
            channel_id=channel_id,
            upload_date="20260726",
            upload_date_precision="approximate",
            type="karaoke",
            raw_data={"timestamp": 1_784_998_800},
        )
    )
    assert (preserved.upload_date, preserved.upload_date_precision) == (
        "20260725",
        "exact",
    )

    await session.rollback()


@pytest.mark.asyncio
async def test_get_by_channel_id_filters_has_song_list(session: AsyncSession):
    suffix = uuid.uuid4().hex[:8]
    channel_id = f"ch_setlist_{suffix}"
    channel_repo = ChannelRepository(session)
    video_repo = VideoRepository(session)
    await channel_repo.create(
        YouTubeChannel(
            id=channel_id,
            name="Setlist Filter Test",
            url=f"https://www.youtube.com/channel/{channel_id}",
        )
    )

    with_setlist = await video_repo.upsert(
        YouTubeVideo(
            id=f"vid_yes_{suffix}",
            title="With setlist",
            url=f"https://www.youtube.com/watch?v=vid_yes_{suffix}",
            channel_id=channel_id,
            type="karaoke",
            raw_data={},
        )
    )
    with_setlist.has_song_list_comment = True
    with_setlist.analysis_status = "done"
    await video_repo.update_analysis(with_setlist)

    await video_repo.upsert(
        YouTubeVideo(
            id=f"vid_no_{suffix}",
            title="Without setlist",
            url=f"https://www.youtube.com/watch?v=vid_no_{suffix}",
            channel_id=channel_id,
            type="karaoke",
            raw_data={},
        )
    )
    await video_repo.upsert(
        YouTubeVideo(
            id=f"vid_song_{suffix}",
            title="Song upload",
            url=f"https://www.youtube.com/watch?v=vid_song_{suffix}",
            channel_id=channel_id,
            type="song",
            raw_data={},
        )
    )

    all_karaoke = await video_repo.get_by_channel_id(channel_id, video_type="karaoke")
    assert {v.id for v in all_karaoke} == {
        f"vid_yes_{suffix}",
        f"vid_no_{suffix}",
    }
    assert await video_repo.count_by_channel_id(channel_id, video_type="karaoke") == 2

    only_with = await video_repo.get_by_channel_id(
        channel_id, video_type="karaoke", has_song_list=True
    )
    assert [v.id for v in only_with] == [f"vid_yes_{suffix}"]
    assert (
        await video_repo.count_by_channel_id(
            channel_id, video_type="karaoke", has_song_list=True
        )
        == 1
    )

    only_without = await video_repo.get_by_channel_id(
        channel_id, video_type="karaoke", has_song_list=False
    )
    assert [v.id for v in only_without] == [f"vid_no_{suffix}"]
    assert (
        await video_repo.count_by_channel_id(
            channel_id, video_type="karaoke", has_song_list=False
        )
        == 1
    )

    await session.rollback()


@pytest.mark.asyncio
async def test_search_by_title_filters_channel_type_and_date(session: AsyncSession):
    suffix = uuid.uuid4().hex[:8]
    channel_a = f"ch_sa_{suffix}"
    channel_b = f"ch_sb_{suffix}"
    channel_repo = ChannelRepository(session)
    video_repo = VideoRepository(session)
    song_repo = SongRepository(session)

    for channel_id, name in (
        (channel_a, "Search A"),
        (channel_b, "Search B"),
    ):
        await channel_repo.create(
            YouTubeChannel(
                id=channel_id,
                name=name,
                url=f"https://www.youtube.com/channel/{channel_id}",
            )
        )

    karaoke_a = await video_repo.upsert(
        YouTubeVideo(
            id=f"vid_ka_{suffix}",
            title="Karaoke A",
            url=f"https://www.youtube.com/watch?v=vid_ka_{suffix}",
            channel_id=channel_a,
            upload_date="20240615",
            upload_date_precision="exact",
            type="karaoke",
            raw_data={},
        )
    )
    song_upload_a = await video_repo.upsert(
        YouTubeVideo(
            id=f"vid_so_{suffix}",
            title="Song upload A",
            url=f"https://www.youtube.com/watch?v=vid_so_{suffix}",
            channel_id=channel_a,
            upload_date="20240110",
            upload_date_precision="exact",
            type="song",
            raw_data={},
        )
    )
    karaoke_b = await video_repo.upsert(
        YouTubeVideo(
            id=f"vid_kb_{suffix}",
            title="Karaoke B",
            url=f"https://www.youtube.com/watch?v=vid_kb_{suffix}",
            channel_id=channel_b,
            upload_date="20240801",
            upload_date_precision="exact",
            type="karaoke",
            raw_data={},
        )
    )
    undated = await video_repo.upsert(
        YouTubeVideo(
            id=f"vid_nd_{suffix}",
            title="No date",
            url=f"https://www.youtube.com/watch?v=vid_nd_{suffix}",
            channel_id=channel_a,
            type="karaoke",
            raw_data={},
        )
    )

    unique = f"FilterHit_{suffix}"
    await song_repo.replace_for_video(
        karaoke_a.id,
        [
            Song(title=unique, video_id=karaoke_a.id, timestamp="0:10"),
            Song(title=f"100%_{suffix}", video_id=karaoke_a.id, timestamp="1:00"),
        ],
    )
    await song_repo.replace_for_video(
        song_upload_a.id,
        [Song(title=unique, video_id=song_upload_a.id, timestamp="0:20")],
    )
    await song_repo.replace_for_video(
        karaoke_b.id,
        [Song(title=unique, video_id=karaoke_b.id, timestamp="0:30")],
    )
    await song_repo.replace_for_video(
        undated.id,
        [Song(title=unique, video_id=undated.id, timestamp="0:40")],
    )

    all_hits, all_total = await song_repo.search_by_title(unique, limit=20, offset=0)
    assert all_total == 4
    assert {hit.channel_id for hit in all_hits} == {channel_a, channel_b}

    channel_hits, channel_total = await song_repo.search_by_title(
        unique,
        limit=20,
        offset=0,
        channel_id=channel_a,
    )
    assert channel_total == 3
    assert {hit.channel_id for hit in channel_hits} == {channel_a}

    karaoke_hits, karaoke_total = await song_repo.search_by_title(
        unique,
        limit=20,
        offset=0,
        video_type="karaoke",
    )
    assert karaoke_total == 3
    assert {hit.video_id for hit in karaoke_hits} == {
        karaoke_a.id,
        karaoke_b.id,
        undated.id,
    }

    song_hits, song_total = await song_repo.search_by_title(
        unique,
        limit=20,
        offset=0,
        video_type="song",
    )
    assert song_total == 1
    assert song_hits[0].video_id == song_upload_a.id

    dated_hits, dated_total = await song_repo.search_by_title(
        unique,
        limit=20,
        offset=0,
        upload_date_from="20240601",
        upload_date_to="20240731",
    )
    assert dated_total == 1
    assert dated_hits[0].video_id == karaoke_a.id

    # LIKE wildcards remain literal even when filters are present.
    percent_hits, percent_total = await song_repo.search_by_title(
        "%",
        limit=20,
        offset=0,
        channel_id=channel_a,
        video_type="karaoke",
    )
    assert percent_total == 1
    assert percent_hits[0].title == f"100%_{suffix}"

    await session.rollback()
