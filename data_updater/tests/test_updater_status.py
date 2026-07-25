"""Unit tests for process-local updater status tracker."""

from services.updater_status import UpdaterPhase, UpdaterStatusTracker


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
