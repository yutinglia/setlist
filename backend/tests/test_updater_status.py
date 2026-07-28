"""Unit tests for process-local updater status tracker."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import Response

from routers.v1.updater import PUBLIC_ERROR_MESSAGE, get_updater_status
from services.updater_runtime_state import (
    UpdaterOutcome,
    UpdaterRuntimeSnapshot,
)
from services.updater_status import UpdaterPhase, UpdaterStatusTracker
from services.updater_status import updater_status as shared_updater_status


def _container(runtime, *, enabled=False):
    return SimpleNamespace(
        updater_status=shared_updater_status,
        runtime_state_store=SimpleNamespace(read=AsyncMock(return_value=runtime)),
        youtube_cooldown=SimpleNamespace(remaining=lambda: 0),
        settings=SimpleNamespace(
            background_updater_enabled=enabled,
            updater_heartbeat_stale_seconds=120,
            data_update_interval=300,
            scrape_policy=SimpleNamespace(
                comment_scrapes_per_cycle=3,
                steady_scan_interval_seconds=21600,
                backfill_page_size=100,
                backfill_pages_per_cycle=3,
            ),
        ),
    )


def test_begin_and_end_cycle():
    status = UpdaterStatusTracker()
    status.begin_cycle()
    snap = status.snapshot()
    assert snap["phase"] == UpdaterPhase.STARTING.value
    assert snap["is_cycle_active"] is True
    assert snap["comment_scrapes_this_cycle"] == 0

    status.set(
        UpdaterPhase.SCRAPING_COMMENTS,
        detail="Scraping",
        channel_id="ch1",
        channel_name="Chan",
        video_id="vid1",
        video_title="Song stream",
        comment_scrapes_this_cycle=2,
    )
    snap = status.snapshot()
    assert snap["phase"] == "scraping_comments"
    assert snap["channel_name"] == "Chan"
    assert snap["video_id"] == "vid1"
    assert snap["comment_scrapes_this_cycle"] == 2

    status.end_cycle()
    snap = status.snapshot()
    assert snap["phase"] == "waiting"
    assert snap["is_cycle_active"] is False
    assert snap["channel_id"] is None
    assert snap["video_id"] is None
    assert snap["last_cycle_finished_at"] is not None


def test_end_cycle_preserves_cooldown_phase():
    status = UpdaterStatusTracker()
    status.begin_cycle()
    status.end_cycle(phase=UpdaterPhase.COOLDOWN, detail="blocked")
    snap = status.snapshot()
    assert snap["phase"] == "cooldown"
    assert snap["detail"] == "blocked"
    assert snap["is_cycle_active"] is False


def test_end_cycle_error():
    status = UpdaterStatusTracker()
    status.begin_cycle()
    status.end_cycle(error="boom")
    snap = status.snapshot()
    assert snap["phase"] == "error"
    assert snap["last_error"] == "boom"
    assert snap["is_cycle_active"] is False


def test_end_cycle_is_idempotent_for_last_finished_time():
    status = UpdaterStatusTracker()
    status.begin_cycle()
    status.end_cycle(error="first")
    first_finished = status.snapshot()["last_cycle_finished_at"]

    status.end_cycle(error="second")

    assert status.snapshot()["last_cycle_finished_at"] == first_finished


def test_stop_closes_active_cycle_and_clears_error():
    status = UpdaterStatusTracker()
    status.begin_cycle()
    status.set(UpdaterPhase.ERROR, last_error="old error")

    status.stop(detail="disabled")
    snap = status.snapshot()

    assert snap["phase"] == "idle"
    assert snap["detail"] == "disabled"
    assert snap["is_cycle_active"] is False
    assert snap["last_cycle_finished_at"] is not None
    assert snap["last_error"] is None


@pytest.mark.asyncio
async def test_public_status_redacts_internal_error_details():
    now = datetime.now(UTC).replace(tzinfo=None)
    runtime = UpdaterRuntimeSnapshot(
        cycle_started_at=now,
        cycle_finished_at=None,
        last_success_at=None,
        heartbeat_at=now,
        outcome=UpdaterOutcome.RUNNING.value,
        owner_id="test-owner",
    )
    shared_updater_status.set(
        UpdaterPhase.ERROR,
        detail="password=secret",
        last_error="database URL includes secret",
    )

    http_response = Response()
    response = await get_updater_status(http_response, _container(runtime))

    assert response.detail == PUBLIC_ERROR_MESSAGE
    assert response.last_error == PUBLIC_ERROR_MESSAGE
    assert response.persistent_outcome == UpdaterOutcome.RUNNING.value
    assert response.persistent_owner_id == "test-owner"
    assert response.is_stalled is False
    assert response.background_updater_enabled is not None
    assert http_response.headers["cache-control"] == "no-store"
    assert http_response.headers["vary"] == "Cookie"
    shared_updater_status.stop(detail="test cleanup")


@pytest.mark.asyncio
async def test_enabled_background_worker_reports_stale_durable_heartbeat():
    now = datetime.now(UTC).replace(tzinfo=None)
    runtime = UpdaterRuntimeSnapshot(
        cycle_started_at=now,
        cycle_finished_at=now,
        last_success_at=now,
        heartbeat_at=now.replace(year=now.year - 1),
        outcome=UpdaterOutcome.SUCCESS.value,
        owner_id="dead-owner",
    )
    shared_updater_status.stop(detail="waiting")

    response = await get_updater_status(
        Response(),
        _container(runtime, enabled=True),
    )

    assert response.is_stalled is True
