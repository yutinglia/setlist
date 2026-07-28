"""Database-backed scraper/analyzer summary report."""

from fastapi import APIRouter, Depends

from deps import get_report_query_service
from models.report import SummaryReport
from services.queries import ReportQueryService

router = APIRouter(prefix="/report", tags=["Report"])


@router.get("/summary", response_model=SummaryReport)
async def get_summary_report(
    queries: ReportQueryService = Depends(get_report_query_service),
) -> SummaryReport:
    """Return aggregate scraped, analyzed, comment, and song counts."""
    return await queries.get_summary()
