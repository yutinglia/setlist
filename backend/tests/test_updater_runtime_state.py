"""Durable updater lifecycle and heartbeat regressions."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from services.updater_runtime_state import (
    UpdaterOutcome,
    UpdaterRuntimeSnapshot,
    UpdaterRuntimeStateStore,
)


def _database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://vks_db_user:vks_db_pwd@localhost:5432/vks_db",
    )


@pytest.mark.asyncio
async def test_runtime_store_records_owned_cycle_and_last_success():
    engine = create_async_engine(_database_url())
    try:
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except Exception:
            pytest.skip("Postgres not available for updater runtime-state test")

        store = UpdaterRuntimeStateStore(engine)
        await store.mark_started("test-owner")
        running = await store.read()

        assert running.outcome == UpdaterOutcome.RUNNING.value
        assert running.owner_id == "test-owner"
        assert running.cycle_started_at is not None
        assert running.cycle_finished_at is None
        assert await store.heartbeat("different-owner") is False
        assert (
            await store.mark_finished("different-owner", UpdaterOutcome.ERROR) is False
        )

        assert await store.heartbeat("test-owner") is True
        assert await store.mark_finished("test-owner", UpdaterOutcome.SUCCESS) is True
        finished = await store.read()

        assert finished.outcome == UpdaterOutcome.SUCCESS.value
        assert finished.cycle_finished_at is not None
        assert finished.last_success_at is not None
        assert finished.is_stalled(stale_after_seconds=1) is False
        assert await store.heartbeat("test-owner") is True
    finally:
        await engine.dispose()


def test_initialized_snapshot_is_stalled_only_after_heartbeat_deadline():
    now = datetime.now(UTC).replace(tzinfo=None)
    running = UpdaterRuntimeSnapshot(
        cycle_started_at=now - timedelta(minutes=10),
        cycle_finished_at=None,
        last_success_at=None,
        heartbeat_at=now - timedelta(seconds=121),
        outcome=UpdaterOutcome.RUNNING.value,
        owner_id="dead-worker",
    )
    finished = UpdaterRuntimeSnapshot(
        cycle_started_at=running.cycle_started_at,
        cycle_finished_at=now,
        last_success_at=now,
        heartbeat_at=now,
        outcome=UpdaterOutcome.SUCCESS.value,
        owner_id="finished-worker",
    )

    assert running.is_stalled(stale_after_seconds=120, now=now) is True
    assert running.is_stalled(stale_after_seconds=122, now=now) is False
    assert finished.is_stalled(stale_after_seconds=120, now=now) is False

    never_started = UpdaterRuntimeSnapshot(
        cycle_started_at=None,
        cycle_finished_at=None,
        last_success_at=None,
        heartbeat_at=None,
        outcome=UpdaterOutcome.NEVER.value,
        owner_id=None,
    )
    assert never_started.is_stalled(stale_after_seconds=120, now=now) is False
