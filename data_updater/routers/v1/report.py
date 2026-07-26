"""Database-backed scraper/analyzer summary report."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_session
from models.report import SummaryReport
from repositories.report_repository import ReportRepository

router = APIRouter(prefix="/report", tags=["Report"])


@router.get("/summary", response_model=SummaryReport)
async def get_summary_report(
    session: AsyncSession = Depends(get_session),
) -> SummaryReport:
    """Return aggregate scraped, analyzed, comment, and song counts."""
    return await ReportRepository(session).get_summary()
