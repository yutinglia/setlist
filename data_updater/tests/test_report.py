"""Summary report API and DTO regressions without PostgreSQL."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from main import app
from models.report import SummaryReport
from routers.v1 import report


def _summary() -> SummaryReport:
    return SummaryReport(
        generated_at=datetime(2026, 7, 26, 12, 0),
        channels=3,
        backfill={"pending": 1, "running": 1, "done": 1, "failed": 0},
        videos={
            "total": 20,
            "karaoke": 12,
            "song": 8,
            "other": 0,
            "with_list_snapshot": 20,
            "with_metadata_snapshot": 10,
            "date_unknown": 2,
            "date_approximate": 8,
            "date_exact": 10,
            "latest_discovered_at": datetime(2026, 7, 26, 11, 0),
        },
        analysis={
            "attempted": 10,
            "with_setlist": 7,
            "videos_with_comments": 10,
            "comments": 120,
            "latest_analyzed_at": datetime(2026, 7, 26, 11, 30),
            "status": {
                "pending": 2,
                "retry": 1,
                "no_setlist": 2,
                "done": 7,
                "exhausted": 0,
                "skipped": 8,
            },
        },
        songs={"total": 98, "analyzed_by_llm": 4},
    )


def test_summary_report_route_is_registered():
    assert "/v1/report/summary" in app.openapi()["paths"]


@pytest.mark.asyncio
async def test_summary_report_route_returns_repository_result(monkeypatch):
    expected = _summary()
    get_summary = AsyncMock(return_value=expected)
    monkeypatch.setattr(
        report,
        "ReportRepository",
        lambda _session: SimpleNamespace(get_summary=get_summary),
    )

    result = await report.get_summary_report(SimpleNamespace())

    assert result == expected
    get_summary.assert_awaited_once()
