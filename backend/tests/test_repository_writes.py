"""Integration tests for repository write path.

Requires a reachable Postgres (Compose/Dev Container defaults).
Skipped automatically when the database is unavailable.
"""

import os
import uuid
from datetime import UTC, datetime, timedelta

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
    refreshed.song_list_comment_raw_data = {
        "id": f"comment_{suffix}",
        "author": f"@helper_{suffix}",
        "author_id": f"UC_helper_{suffix}",
        "text": "0:10 Song A",
    }
    refreshed.setlist_comment_author = f"@helper_{suffix}"
    refreshed.setlist_comment_author_id = f"UC_helper_{suffix}"
    refreshed.setlist_comment_id = f"comment_{suffix}"
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
        "%", limit=20, offset=0, channel_ids=[channel_id]
    )
    assert percent_total == 1
    assert [song.title for song in percent_hits] == ["100% Love"]
    underscore_hits, underscore_total = await song_repo.search_by_title(
        "_", limit=20, offset=0, channel_ids=[channel_id]
    )
    assert underscore_total == 1
    assert [song.title for song in underscore_hits] == ["Under_score"]
    assert percent_hits[0].setlist_comment_author == f"@helper_{suffix}"
    assert percent_hits[0].setlist_comment_author_id == f"UC_helper_{suffix}"
    assert percent_hits[0].setlist_comment_id == f"comment_{suffix}"

    contributors, contributor_total = await song_repo.list_setlist_contributors(
        limit=100,
        offset=0,
    )
    assert contributor_total >= 1
    contributor = next(
        item for item in contributors if item.author_id == f"UC_helper_{suffix}"
    )
    assert contributor.author == f"@helper_{suffix}"
    assert contributor.song_count == 3
    assert contributor.video_count == 1

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
        channel_ids=[channel_a],
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
        channel_ids=[channel_a],
        video_type="karaoke",
    )
    assert percent_total == 1
    assert percent_hits[0].title == f"100%_{suffix}"

    await session.rollback()


@pytest.mark.asyncio
async def test_suggest_titles_deduplicates_ranks_and_filters(session: AsyncSession):
    suffix = uuid.uuid4().hex[:8]
    channel_a = f"ch_suggest_a_{suffix}"
    channel_b = f"ch_suggest_b_{suffix}"
    channel_repo = ChannelRepository(session)
    video_repo = VideoRepository(session)
    song_repo = SongRepository(session)

    for channel_id in (channel_a, channel_b):
        await channel_repo.create(
            YouTubeChannel(
                id=channel_id,
                name=f"Suggestion {channel_id}",
                url=f"https://www.youtube.com/channel/{channel_id}",
            )
        )

    videos = []
    for video_id, channel_id, video_type in (
        (f"vid_suggest_a1_{suffix}", channel_a, "karaoke"),
        (f"vid_suggest_a2_{suffix}", channel_a, "song"),
        (f"vid_suggest_b1_{suffix}", channel_b, "karaoke"),
    ):
        videos.append(
            await video_repo.upsert(
                YouTubeVideo(
                    id=video_id,
                    title=f"Suggestion video {video_id}",
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    channel_id=channel_id,
                    upload_date="20240615",
                    upload_date_precision="exact",
                    type=video_type,
                    raw_data={},
                )
            )
        )

    needle = f"Glow{suffix}"
    await song_repo.replace_for_video(
        videos[0].id,
        [
            Song(title=needle, video_id=videos[0].id, timestamp="0:10"),
            Song(
                title=f"{needle} Acoustic",
                video_id=videos[0].id,
                timestamp="0:20",
            ),
            Song(
                title=f"After {needle}",
                video_id=videos[0].id,
                timestamp="0:30",
            ),
            Song(
                title=f"100% {needle}",
                video_id=videos[0].id,
                timestamp="0:40",
            ),
        ],
    )
    await song_repo.replace_for_video(
        videos[1].id,
        [Song(title=needle.lower(), video_id=videos[1].id, timestamp="0:10")],
    )
    await song_repo.replace_for_video(
        videos[2].id,
        [
            Song(
                title=f"{needle} Acoustic",
                video_id=videos[2].id,
                timestamp="0:10",
            ),
            Song(
                title=f"After {needle}",
                video_id=videos[2].id,
                timestamp="0:20",
            ),
        ],
    )

    suggestions = await song_repo.suggest_titles(needle, limit=8)
    normalized = [item.title.lower() for item in suggestions]
    assert len(normalized) == len(set(normalized))
    assert normalized[0] == needle.lower()
    assert normalized.index(f"{needle} Acoustic".lower()) < normalized.index(
        f"After {needle}".lower()
    )
    assert suggestions[0].occurrences == 2

    filtered = await song_repo.suggest_titles(
        needle,
        limit=8,
        channel_ids=[channel_b],
        video_type="karaoke",
        upload_date_from="20240101",
        upload_date_to="20241231",
    )
    assert {item.title.lower() for item in filtered} == {
        f"{needle} Acoustic".lower(),
        f"After {needle}".lower(),
    }

    literal_percent = await song_repo.suggest_titles("%", limit=8)
    assert any(item.title == f"100% {needle}" for item in literal_percent)

    await session.rollback()


@pytest.mark.asyncio
async def test_channel_repository_preserves_cursors_and_persists_schedules(
    session: AsyncSession,
):
    """Exercise channel state transitions through their public repository API."""
    suffix = uuid.uuid4().hex[:8]
    channel_id = f"ch_state_{suffix}"
    channel_url = f"https://www.youtube.com/channel/{channel_id}"
    repo = ChannelRepository(session)

    created = await repo.upsert(
        YouTubeChannel(
            id=channel_id,
            name="Stateful Channel",
            url=channel_url,
            thumbnail_url="https://images.test/old.jpg",
            raw_data={"source": "initial"},
            video_backfill_status="pending",
            video_backfill_offset=7,
        )
    )
    assert created.video_backfill_status == "pending"
    assert created.video_backfill_offset == 7

    assert await repo.count_all() >= 1
    assert (await repo.get_by_id(channel_id)).name == "Stateful Channel"
    assert await repo.get_by_id(f"missing_{suffix}") is None
    assert (await repo.get_by_url(channel_url)).id == channel_id
    assert await repo.get_by_url(f"https://invalid.test/{suffix}") is None
    assert any(item.id == channel_id for item in await repo.get_all())
    assert len(await repo.get_all(limit=1, offset=0)) == 1
    assert isinstance(await repo.get_all(offset=1), list)

    refreshed = await repo.upsert(
        YouTubeChannel(
            id=channel_id,
            name="Renamed Channel",
            url=channel_url,
            thumbnail_url="https://images.test/new.jpg",
            raw_data={"source": "refresh"},
            video_backfill_status="done",
            video_backfill_offset=99,
        )
    )
    assert refreshed.name == "Renamed Channel"
    assert refreshed.raw_data == {"source": "refresh"}
    assert refreshed.video_backfill_status == "pending"
    assert refreshed.video_backfill_offset == 7

    backfill = await repo.update_video_backfill(
        channel_id,
        status="running",
        offset=0,
    )
    assert backfill.video_backfill_status == "running"
    assert backfill.video_backfill_offset == 1
    assert (
        await repo.update_video_backfill(
            f"missing_{suffix}",
            status="failed",
            offset=3,
        )
        is None
    )

    first_due = datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=5)
    failed_scan = await repo.schedule_video_scan(
        channel_id,
        next_scan_at=first_due,
        succeeded=False,
    )
    assert failed_scan.next_video_scan_at == first_due
    assert failed_scan.video_scan_failures == 1

    second_due = first_due + timedelta(hours=6)
    successful_scan = await repo.schedule_video_scan(
        channel_id,
        next_scan_at=second_due,
        succeeded=True,
    )
    assert successful_scan.next_video_scan_at == second_due
    assert successful_scan.video_scan_failures == 0
    assert successful_scan.last_video_scan_at is not None
    assert (
        await repo.schedule_video_scan(
            f"missing_{suffix}",
            next_scan_at=second_due,
            succeeded=True,
        )
        is None
    )

    youtube_cooldown = datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=15)
    add_cooldown = youtube_cooldown + timedelta(minutes=1)
    await repo.set_youtube_cooldown_until(youtube_cooldown)
    await repo.set_channel_add_cooldown_until(add_cooldown)
    assert await repo.get_youtube_cooldown_until() == youtube_cooldown
    assert await repo.get_channel_add_cooldown_until() == add_cooldown

    await session.rollback()


@pytest.mark.asyncio
async def test_video_repository_analysis_queue_filters_ineligible_archives(
    session: AsyncSession,
):
    """Queue only due karaoke archives while retaining reusable observations."""
    suffix = uuid.uuid4().hex[:8]
    channel_id = f"ch_queue_{suffix}"
    channel_repo = ChannelRepository(session)
    repo = VideoRepository(session)
    await channel_repo.create(
        YouTubeChannel(
            id=channel_id,
            name="Queue Test",
            url=f"https://www.youtube.com/channel/{channel_id}",
        )
    )

    eligible = await repo.upsert(
        YouTubeVideo(
            id=f"vid_eligible_{suffix}",
            title="【歌枠】Queue Test",
            url=f"https://www.youtube.com/watch?v=eligible_{suffix}",
            channel_id=channel_id,
            upload_date="20260729",
            type="karaoke",
            raw_data={"title": "【歌枠】Queue Test"},
            metadata_raw_data={"duration": 3600, "live_status": "was_live"},
        )
    )
    eligible.comments_raw_data = {"comments": [{"text": "0:10 Song"}]}
    await repo.update_analysis(eligible)

    false_positive = await repo.upsert(
        YouTubeVideo(
            id=f"vid_false_{suffix}",
            title="Official MV",
            url=f"https://www.youtube.com/watch?v=false_{suffix}",
            channel_id=channel_id,
            upload_date="20260728",
            type="karaoke",
            raw_data={"title": "Official MV"},
            metadata_raw_data={"duration": 240, "live_status": "not_live"},
        )
    )
    deferred = await repo.upsert(
        YouTubeVideo(
            id=f"vid_deferred_{suffix}",
            title="KARAOKE later",
            url=f"https://www.youtube.com/watch?v=deferred_{suffix}",
            channel_id=channel_id,
            upload_date="20260727",
            type="karaoke",
            raw_data={},
            metadata_raw_data={"duration": 3600, "live_status": "was_live"},
        )
    )
    deferred.analysis_status = "retry"
    deferred.next_analysis_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(
        hours=1
    )
    await repo.update_analysis(deferred)

    all_videos = await repo.get_all()
    assert {eligible.id, false_positive.id, deferred.id} <= {
        item.id for item in all_videos
    }
    stored = await repo.get_with_stored_comments()
    assert eligible.id in {item.id for item in stored}

    assert (
        await repo.get_needing_analysis(
            channel_id,
            max_attempts=3,
            limit=0,
        )
        == []
    )
    needing = await repo.get_needing_analysis(
        channel_id,
        max_attempts=3,
        limit=10,
    )
    assert [item.id for item in needing] == [eligible.id]

    now = datetime.now(UTC).replace(tzinfo=None)
    assert await repo.get_analysis_queue(max_attempts=3, limit=0, now=now) == []
    queued = await repo.get_analysis_queue(max_attempts=3, limit=10, now=now)
    assert [item.id for item in queued] == [eligible.id]

    assert await repo.reclassify_by_ids([]) == 0
    assert await repo.reclassify_by_ids([false_positive.id]) == 1
    reclassified = await repo.get_by_id(false_positive.id)
    assert reclassified.type == "song"
    assert reclassified.analysis_status == "skipped"

    assert (
        await repo.clear_analysis_for_non_karaoke_by_ids(
            [],
            max_attempts=3,
        )
        == []
    )
    assert await repo.clear_analysis_for_non_karaoke_by_ids(
        [false_positive.id],
        max_attempts=3,
    ) == [false_positive.id]
    cleared = await repo.get_by_id(false_positive.id)
    assert cleared.analyze_attempts == 3
    assert cleared.analysis_status == "skipped"

    await session.rollback()
