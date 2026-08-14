"""Persistence for deferred administrator channel ingest."""

from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ChannelIngestQueue
from models.channel import ChannelIngestItem


class ChannelIngestRepository:
    """Queue access without transaction ownership."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def enqueue(self, channel_url: str) -> tuple[ChannelIngestItem, bool]:
        """Insert one pending URL or return its existing pending item."""
        now = self._utc_now()
        stmt = (
            insert(ChannelIngestQueue)
            .values(
                channel_url=channel_url,
                status="pending",
                attempts=0,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(
                index_elements=[ChannelIngestQueue.channel_url],
                index_where=ChannelIngestQueue.status == "pending",
            )
            .returning(ChannelIngestQueue)
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        created = row is not None
        if row is None:
            existing = await self.session.execute(
                select(ChannelIngestQueue).where(
                    ChannelIngestQueue.channel_url == channel_url,
                    ChannelIngestQueue.status == "pending",
                )
            )
            row = existing.scalar_one()
        await self.session.flush()
        return ChannelIngestItem.model_validate(row), created

    async def list_pending(
        self,
        *,
        limit: int,
        offset: int = 0,
    ) -> list[ChannelIngestItem]:
        """Return the oldest pending URLs first."""
        result = await self.session.execute(
            select(ChannelIngestQueue)
            .where(ChannelIngestQueue.status == "pending")
            .order_by(ChannelIngestQueue.created_at, ChannelIngestQueue.id)
            .limit(max(0, limit))
            .offset(max(0, offset))
        )
        return [
            ChannelIngestItem.model_validate(item) for item in result.scalars().all()
        ]

    async def count_pending(self) -> int:
        """Return the number of URLs awaiting resolution."""
        result = await self.session.execute(
            select(func.count())
            .select_from(ChannelIngestQueue)
            .where(ChannelIngestQueue.status == "pending")
        )
        return int(result.scalar_one())

    async def mark_completed(
        self,
        item_id: int,
        *,
        channel_id: str,
    ) -> ChannelIngestItem | None:
        """Finish a pending item and record the resolved channel."""
        now = self._utc_now()
        result = await self.session.execute(
            update(ChannelIngestQueue)
            .where(
                ChannelIngestQueue.id == item_id,
                ChannelIngestQueue.status == "pending",
            )
            .values(
                status="completed",
                attempts=ChannelIngestQueue.attempts + 1,
                channel_id=channel_id,
                error_message=None,
                updated_at=now,
                completed_at=now,
            )
            .returning(ChannelIngestQueue)
        )
        row = result.scalar_one_or_none()
        await self.session.flush()
        return ChannelIngestItem.model_validate(row) if row is not None else None

    async def mark_failed(
        self,
        item_id: int,
        *,
        error_message: str,
    ) -> ChannelIngestItem | None:
        """Finish a non-block resolution failure with redacted detail."""
        now = self._utc_now()
        result = await self.session.execute(
            update(ChannelIngestQueue)
            .where(
                ChannelIngestQueue.id == item_id,
                ChannelIngestQueue.status == "pending",
            )
            .values(
                status="failed",
                attempts=ChannelIngestQueue.attempts + 1,
                error_message=error_message[:500],
                updated_at=now,
                completed_at=now,
            )
            .returning(ChannelIngestQueue)
        )
        row = result.scalar_one_or_none()
        await self.session.flush()
        return ChannelIngestItem.model_validate(row) if row is not None else None

    async def mark_attempted(self, item_id: int) -> ChannelIngestItem | None:
        """Record a blocked attempt while keeping the item pending."""
        now = self._utc_now()
        result = await self.session.execute(
            update(ChannelIngestQueue)
            .where(
                ChannelIngestQueue.id == item_id,
                ChannelIngestQueue.status == "pending",
            )
            .values(
                attempts=ChannelIngestQueue.attempts + 1,
                updated_at=now,
            )
            .returning(ChannelIngestQueue)
        )
        row = result.scalar_one_or_none()
        await self.session.flush()
        return ChannelIngestItem.model_validate(row) if row is not None else None

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(UTC).replace(tzinfo=None)
