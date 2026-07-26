"""Concurrency tests for the PostgreSQL-backed YouTube operation lock."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from services.data_updater import DataUpdater
from services.youtube_operation_lock import (
    YouTubeUpdaterBusyError,
    postgres_youtube_operation_lock,
)


async def _database() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://vks_db_user:vks_db_pwd@localhost:5432/vks_db",
    )
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        await engine.dispose()
        pytest.skip("Postgres not available for updater concurrency tests")
    return engine, async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest.mark.asyncio
async def test_only_one_database_connection_can_hold_youtube_lock():
    engine, factory = await _database()
    try:
        async with factory() as first, factory() as second:
            async with postgres_youtube_operation_lock(first) as first_acquired:
                assert first_acquired is True
                async with postgres_youtube_operation_lock(second) as second_acquired:
                    assert second_acquired is False

            async with postgres_youtube_operation_lock(second) as reacquired:
                assert reacquired is True
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_database_lock_is_released_after_operation_failure():
    engine, factory = await _database()
    try:
        async with factory() as first, factory() as second:
            with pytest.raises(RuntimeError, match="simulated crash"):
                async with postgres_youtube_operation_lock(first) as acquired:
                    assert acquired is True
                    raise RuntimeError("simulated crash")

            async with postgres_youtube_operation_lock(second) as reacquired:
                assert reacquired is True
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_background_cycle_skips_when_cross_process_lock_is_busy(monkeypatch):
    @asynccontextmanager
    async def busy_guard(_session):
        yield False

    get_all = AsyncMock()
    updater = DataUpdater(
        SimpleNamespace(),
        SimpleNamespace(get_all=get_all),
        SimpleNamespace(),
        SimpleNamespace(),
    )
    monkeypatch.setattr("services.data_updater.youtube_operation_guard", busy_guard)

    await updater.update()

    get_all.assert_not_awaited()


@pytest.mark.asyncio
async def test_manual_operation_fails_fast_when_cross_process_lock_is_busy(monkeypatch):
    @asynccontextmanager
    async def busy_guard(_session):
        yield False

    updater = DataUpdater(
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
    )
    monkeypatch.setattr("services.data_updater.youtube_operation_guard", busy_guard)

    with pytest.raises(YouTubeUpdaterBusyError):
        await updater.refresh_channel_video_list(SimpleNamespace())
