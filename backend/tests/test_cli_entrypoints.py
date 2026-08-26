"""Coverage and behavior for administrator maintenance entry points."""

from argparse import Namespace
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import generate_admin_password_hash
import reanalyze_stored_data
import run_updater_once
from services.stored_data_reanalyzer import StoredDataReanalysisResult


class _SessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, traceback):
        return False


def test_generate_admin_password_hash_rejects_short_and_mismatched_passwords(
    monkeypatch,
):
    monkeypatch.setattr(
        generate_admin_password_hash,
        "getpass",
        Mock(side_effect=["short", "short"]),
    )
    with pytest.raises(SystemExit, match="at least 12"):
        generate_admin_password_hash.main()

    monkeypatch.setattr(
        generate_admin_password_hash,
        "getpass",
        Mock(side_effect=["long-enough-password", "different-password"]),
    )
    with pytest.raises(SystemExit, match="do not match"):
        generate_admin_password_hash.main()


def test_generate_admin_password_hash_prints_argon2id_hash(monkeypatch, capsys):
    hasher = SimpleNamespace(hash=Mock(return_value="$argon2id$test"))
    monkeypatch.setattr(
        generate_admin_password_hash,
        "getpass",
        Mock(side_effect=["long-enough-password", "long-enough-password"]),
    )
    monkeypatch.setattr(
        generate_admin_password_hash,
        "PasswordHasher",
        Mock(return_value=hasher),
    )

    generate_admin_password_hash.main()

    assert capsys.readouterr().out.strip() == "$argon2id$test"
    hasher.hash.assert_called_once_with("long-enough-password")


def test_reanalysis_cli_arguments(monkeypatch):
    monkeypatch.setattr("sys.argv", ["reanalyze_stored_data.py"])
    args = reanalyze_stored_data.parse_args()
    assert args.apply is False
    assert args.include_successful is False
    assert args.requeue_unresolved is False
    assert args.approve_clear_video_id == []
    assert args.approve_successful_video_id == []
    monkeypatch.setattr(
        "sys.argv",
        [
            "reanalyze_stored_data.py",
            "--apply",
            "--include-successful",
            "--requeue-unresolved",
            "--approve-clear-video-id",
            "unsafe-video",
            "--approve-successful-video-id",
            "reviewed-video",
        ],
    )
    args = reanalyze_stored_data.parse_args()
    assert args.apply is True
    assert args.include_successful is True
    assert args.requeue_unresolved is True
    assert args.approve_clear_video_id == ["unsafe-video"]
    assert args.approve_successful_video_id == ["reviewed-video"]


@pytest.mark.asyncio
async def test_reanalysis_cli_runs_service_prints_result_and_closes(
    monkeypatch,
    capsys,
):
    result = StoredDataReanalysisResult(
        applied=True,
        reclassified_videos=1,
        cleared_non_karaoke_videos=2,
        stored_comment_videos=3,
        detected_setlists=4,
        recovered_setlists=5,
        changed_setlists=6,
        skipped_existing_setlists=7,
        skipped_cleaned_setlists=7,
        requeued_unresolved_videos=8,
        songs_before=8,
        songs_after=9,
    )
    service = SimpleNamespace(run=AsyncMock(return_value=result))
    container = SimpleNamespace(
        session_factory=lambda: _SessionContext("session"),
        stored_data_reanalyzer=Mock(return_value=service),
        close=AsyncMock(),
    )
    monkeypatch.setattr(
        reanalyze_stored_data,
        "ApplicationContainer",
        SimpleNamespace(build=Mock(return_value=container)),
    )
    monkeypatch.setattr(
        reanalyze_stored_data,
        "parse_args",
        Mock(
            return_value=Namespace(
                apply=True,
                include_successful=False,
                requeue_unresolved=True,
                approve_clear_video_id=[],
                approve_successful_video_id=[],
            )
        ),
    )

    await reanalyze_stored_data.main()

    output = capsys.readouterr().out
    assert "APPLIED" in output
    assert "songs_after: 9" in output
    service.run.assert_awaited_once_with(
        apply=True,
        include_successful=False,
        requeue_unresolved=True,
        approved_clear_video_ids=frozenset(),
        approved_successful_video_ids=frozenset(),
    )
    container.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_reanalysis_cli_reports_dry_run(monkeypatch, capsys):
    result = StoredDataReanalysisResult(
        applied=False,
        reclassified_videos=0,
        cleared_non_karaoke_videos=0,
        stored_comment_videos=0,
        detected_setlists=0,
        recovered_setlists=0,
        changed_setlists=0,
        skipped_existing_setlists=0,
        skipped_cleaned_setlists=0,
        requeued_unresolved_videos=0,
        songs_before=0,
        songs_after=0,
    )
    container = SimpleNamespace(
        session_factory=lambda: _SessionContext("session"),
        stored_data_reanalyzer=Mock(
            return_value=SimpleNamespace(run=AsyncMock(return_value=result))
        ),
        close=AsyncMock(),
    )
    monkeypatch.setattr(
        reanalyze_stored_data,
        "ApplicationContainer",
        SimpleNamespace(build=Mock(return_value=container)),
    )
    monkeypatch.setattr(
        reanalyze_stored_data,
        "parse_args",
        Mock(
            return_value=Namespace(
                apply=False,
                include_successful=False,
                requeue_unresolved=False,
                approve_clear_video_id=[],
                approve_successful_video_id=[],
            )
        ),
    )

    await reanalyze_stored_data.main()

    assert "DRY RUN (rolled back)" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_run_updater_once_uses_production_service_path_and_closes(monkeypatch):
    updater = SimpleNamespace(update=AsyncMock())
    container = SimpleNamespace(
        session_factory=lambda: _SessionContext("session"),
        data_updater=Mock(return_value=updater),
        close=AsyncMock(),
    )
    monkeypatch.setattr(
        run_updater_once,
        "ApplicationContainer",
        SimpleNamespace(build=Mock(return_value=container)),
    )

    await run_updater_once.main()

    container.data_updater.assert_called_once_with("session")
    updater.update.assert_awaited_once()
    container.close.assert_awaited_once()
