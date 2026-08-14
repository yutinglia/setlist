"""Management channel creation and bounded bulk-add regressions."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from models.channel import ChannelBulkCreate, ChannelCreate, YouTubeChannel
from routers.v1 import search
from services.channel_creator import ChannelCreator
from services.youtube_cooldown import YouTubeCooldown
from services.yt_scraper.errors import YouTubeAccessBlocked


def _channel(
    channel_id: str = "UC-new",
    handle: str = "new-channel",
) -> YouTubeChannel:
    return YouTubeChannel(
        id=channel_id,
        name=f"Channel {channel_id}",
        url=f"https://www.youtube.com/@{handle}",
        raw_data={},
    )


def _repo(*, created=None, get_by_id=None):
    return SimpleNamespace(
        get_youtube_cooldown_until=AsyncMock(return_value=None),
        get_channel_add_cooldown_until=AsyncMock(return_value=None),
        set_channel_add_cooldown_until=AsyncMock(),
        set_youtube_cooldown_until=AsyncMock(),
        get_by_url=AsyncMock(return_value=None),
        get_by_id=AsyncMock(return_value=get_by_id),
        create=AsyncMock(return_value=created),
    )


def _creator(
    session,
    repo,
    *,
    scrape,
    sleep=None,
    cooldown=None,
    ingest_repo=None,
    cache=None,
):
    return ChannelCreator(
        session,
        repo,
        ingest_repo=ingest_repo,
        cooldown=cooldown or YouTubeCooldown(60),
        scraper_factory=SimpleNamespace(
            channel=Mock(return_value=SimpleNamespace(get_channel_info=Mock()))
        ),
        scrape_executor=SimpleNamespace(run=scrape),
        cache=cache,
        sleep=sleep or AsyncMock(),
    )


def _container(trigger, *, enabled=True):
    return SimpleNamespace(
        settings=SimpleNamespace(
            background_updater_enabled=enabled,
            channel_add_cooldown_seconds=10,
        ),
        update_cycle_trigger=trigger,
    )


@pytest.mark.asyncio
async def test_create_channel_commits_before_requesting_immediate_backfill():
    order: list[str] = []
    scraped = _channel()
    persisted = scraped.model_copy(
        update={"video_backfill_status": "pending", "video_backfill_offset": 1}
    )
    repo = _repo(created=persisted)
    session = SimpleNamespace(
        commit=AsyncMock(side_effect=lambda: order.append("commit")),
        rollback=AsyncMock(),
    )
    trigger = SimpleNamespace(
        request=Mock(side_effect=lambda **_kwargs: order.append("request") or True)
    )
    scrape = AsyncMock(return_value=scraped)
    creator = _creator(session, repo, scrape=scrape)

    created = await search.create_channel(
        ChannelCreate(url=scraped.url),
        None,
        creator,
        _container(trigger),
    )

    assert created.video_backfill_status == "pending"
    assert order == ["commit", "request"]
    session.commit.assert_awaited_once()
    repo.set_channel_add_cooldown_until.assert_awaited_once()
    trigger.request.assert_called_once_with(priority_channel_id=scraped.id)


@pytest.mark.asyncio
async def test_atomic_create_conflict_commits_cooldown_but_does_not_wake():
    scraped = _channel()
    repo = _repo(created=None)
    repo.get_by_id = AsyncMock(side_effect=[None, scraped])
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    trigger = SimpleNamespace(request=Mock(return_value=True))
    creator = _creator(session, repo, scrape=AsyncMock(return_value=scraped))

    with pytest.raises(search.HTTPException) as exc_info:
        await search.create_channel(
            ChannelCreate(url=scraped.url),
            None,
            creator,
            _container(trigger),
        )

    assert exc_info.value.status_code == 409
    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()
    trigger.request.assert_not_called()


@pytest.mark.asyncio
async def test_separate_channel_add_is_rejected_during_admin_cooldown():
    scraped = _channel()
    deadline = datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=8)
    repo = _repo(created=scraped)
    repo.get_channel_add_cooldown_until = AsyncMock(return_value=deadline)
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    scrape = AsyncMock(return_value=scraped)
    creator = _creator(session, repo, scrape=scrape)

    with pytest.raises(search.HTTPException) as exc_info:
        await search.create_channel(
            ChannelCreate(url=scraped.url),
            None,
            creator,
            _container(SimpleNamespace(request=Mock())),
        )

    assert exc_info.value.status_code == 429
    assert int(exc_info.value.headers["Retry-After"]) >= 1
    scrape.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_bulk_add_paces_items_and_queues_only_one_general_wake():
    first = _channel("UC-one", "one")
    second = _channel("UC-two", "two")
    first_persisted = first.model_copy(update={"video_backfill_status": "pending"})
    second_persisted = second.model_copy(update={"video_backfill_status": "pending"})
    deadline = datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=5)
    repo = _repo()
    repo.get_channel_add_cooldown_until = AsyncMock(side_effect=[None, deadline])
    repo.get_by_id = AsyncMock(return_value=None)
    repo.create = AsyncMock(side_effect=[first_persisted, second_persisted])
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    trigger = SimpleNamespace(request=Mock(return_value=True))
    scrape = AsyncMock(side_effect=[first, second])
    sleep = AsyncMock()

    creator = _creator(session, repo, scrape=scrape, sleep=sleep)

    response = await search.create_channels_bulk(
        ChannelBulkCreate(urls=[first.url, second.url]),
        None,
        creator,
        _container(trigger),
    )

    assert response.created == 2
    assert response.failed == 0
    assert [item.status for item in response.items] == ["created", "created"]
    assert session.commit.await_count == 2
    sleep.assert_awaited_once()
    assert sleep.await_args.args[0] > 0
    trigger.request.assert_called_once_with()


@pytest.mark.asyncio
async def test_bulk_add_reports_invalid_item_without_contacting_youtube():
    valid = _channel()
    persisted = valid.model_copy(update={"video_backfill_status": "pending"})
    repo = _repo(created=persisted)
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    trigger = SimpleNamespace(request=Mock(return_value=True))
    scrape = AsyncMock(return_value=valid)

    creator = _creator(session, repo, scrape=scrape)

    response = await search.create_channels_bulk(
        ChannelBulkCreate(urls=["not-youtube", valid.url]),
        None,
        creator,
        _container(trigger),
    )

    assert response.created == 1
    assert response.failed == 1
    assert [item.status for item in response.items] == ["invalid", "created"]
    scrape.assert_awaited_once()
    trigger.request.assert_called_once_with()


@pytest.mark.asyncio
async def test_bulk_add_stops_remaining_items_and_persists_block_cooldown():
    first = _channel("UC-one", "one")
    second = _channel("UC-two", "two")
    repo = _repo()
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    trigger = SimpleNamespace(request=Mock(return_value=True))
    scrape = AsyncMock(side_effect=YouTubeAccessBlocked("HTTP Error 429"))

    creator = _creator(session, repo, scrape=scrape)

    response = await search.create_channels_bulk(
        ChannelBulkCreate(urls=[first.url, second.url]),
        None,
        creator,
        _container(trigger),
    )

    assert [item.status for item in response.items] == ["failed", "skipped"]
    assert response.skipped == 1
    repo.set_channel_add_cooldown_until.assert_awaited_once()
    repo.set_youtube_cooldown_until.assert_awaited_once()
    session.commit.assert_awaited_once()
    trigger.request.assert_not_called()


@pytest.mark.asyncio
async def test_bulk_add_requeues_batch_when_cooldown_starts_mid_request():
    first = _channel("UC-one", "one")
    second = _channel("UC-two", "two")
    repo = _repo()
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    trigger = SimpleNamespace(request=Mock(return_value=True))
    ingest_repo = SimpleNamespace(
        enqueue=AsyncMock(
            side_effect=[
                (SimpleNamespace(id=31), True),
                (SimpleNamespace(id=32), True),
            ]
        )
    )
    creator = _creator(
        session,
        repo,
        scrape=AsyncMock(side_effect=YouTubeAccessBlocked("HTTP Error 429")),
        ingest_repo=ingest_repo,
    )

    response = await search.create_channels_bulk(
        ChannelBulkCreate(urls=[first.url, second.url]),
        None,
        creator,
        _container(trigger),
    )

    assert [item.status for item in response.items] == ["queued", "queued"]
    assert response.queued == 2
    assert session.commit.await_count == 2
    repo.set_youtube_cooldown_until.assert_awaited_once()
    trigger.request.assert_called_once_with()


@pytest.mark.asyncio
async def test_bulk_add_does_not_requeue_an_earlier_resolution_failure():
    first = _channel("UC-one", "one")
    second = _channel("UC-two", "two")
    third = _channel("UC-three", "three")
    repo = _repo()
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    trigger = SimpleNamespace(request=Mock(return_value=True))
    ingest_repo = SimpleNamespace(
        enqueue=AsyncMock(
            side_effect=[
                (SimpleNamespace(id=33), True),
                (SimpleNamespace(id=34), True),
            ]
        )
    )
    creator = _creator(
        session,
        repo,
        scrape=AsyncMock(
            side_effect=[
                RuntimeError("Extractor failed"),
                YouTubeAccessBlocked("HTTP Error 429"),
            ]
        ),
        ingest_repo=ingest_repo,
    )

    response = await search.create_channels_bulk(
        ChannelBulkCreate(urls=[first.url, second.url, third.url]),
        None,
        creator,
        _container(trigger),
    )

    assert [item.status for item in response.items] == [
        "failed",
        "queued",
        "queued",
    ]
    assert response.failed == 1
    assert response.queued == 2
    assert [queued.args[0] for queued in ingest_repo.enqueue.await_args_list] == [
        second.url,
        third.url,
    ]
    assert session.commit.await_count == 3
    trigger.request.assert_called_once_with()


@pytest.mark.asyncio
async def test_bulk_add_exact_duplicate_needs_no_youtube_request_or_cooldown():
    existing = _channel()
    repo = _repo()
    repo.get_by_url = AsyncMock(return_value=existing)
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    trigger = SimpleNamespace(request=Mock(return_value=True))
    scrape = AsyncMock()

    creator = _creator(session, repo, scrape=scrape)

    response = await search.create_channels_bulk(
        ChannelBulkCreate(urls=[existing.url]),
        None,
        creator,
        _container(trigger),
    )

    assert response.already_exists == 1
    assert response.items[0].channel_id == existing.id
    scrape.assert_not_awaited()
    repo.set_channel_add_cooldown_until.assert_not_awaited()
    session.commit.assert_not_awaited()
    trigger.request.assert_not_called()


@pytest.mark.asyncio
async def test_bulk_add_queues_without_youtube_during_global_cooldown():
    first = _channel("UC-one", "one")
    second = _channel("UC-two", "two")
    repo = _repo()
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    trigger = SimpleNamespace(request=Mock(return_value=True))
    scrape = AsyncMock()
    cache = SimpleNamespace(invalidate=AsyncMock())
    ingest_repo = SimpleNamespace(
        enqueue=AsyncMock(
            side_effect=[
                (SimpleNamespace(id=41), True),
                (SimpleNamespace(id=42), True),
            ]
        )
    )
    cooldown = YouTubeCooldown(60)
    cooldown.activate(60)
    creator = _creator(
        session,
        repo,
        scrape=scrape,
        cooldown=cooldown,
        ingest_repo=ingest_repo,
        cache=cache,
    )

    response = await search.create_channels_bulk(
        ChannelBulkCreate(urls=[first.url, second.url]),
        None,
        creator,
        _container(trigger),
    )

    assert [item.status for item in response.items] == ["queued", "queued"]
    assert [item.queue_id for item in response.items] == [41, 42]
    assert response.queued == 2
    assert response.created == 0
    scrape.assert_not_awaited()
    session.commit.assert_awaited_once()
    cache.invalidate.assert_not_awaited()
    trigger.request.assert_called_once_with()


@pytest.mark.asyncio
async def test_single_add_returns_accepted_queue_result_during_global_cooldown():
    channel = _channel()
    repo = _repo()
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    trigger = SimpleNamespace(request=Mock(return_value=True))
    ingest_repo = SimpleNamespace(
        enqueue=AsyncMock(return_value=(SimpleNamespace(id=51), True))
    )
    cooldown = YouTubeCooldown(60)
    cooldown.activate(60)
    creator = _creator(
        session,
        repo,
        scrape=AsyncMock(),
        cooldown=cooldown,
        ingest_repo=ingest_repo,
    )

    response = await search.create_channel(
        ChannelCreate(url=channel.url),
        None,
        creator,
        _container(trigger),
    )

    assert response.status_code == 202
    assert b'"status":"queued"' in response.body
    assert b'"queue_id":51' in response.body
    trigger.request.assert_called_once_with()


def test_bulk_add_rejects_more_than_ten_urls():
    with pytest.raises(ValidationError):
        ChannelBulkCreate(
            urls=[f"https://www.youtube.com/@channel-{index}" for index in range(11)]
        )
