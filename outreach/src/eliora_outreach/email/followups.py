from __future__ import annotations

from datetime import date

from sqlalchemy import select

from ..db import Database, OutboxMessage
from ..due import add_business_days
from ..enums import OutboxState


def followup_due(
    initial_sent: date,
    sequence_step: int,
    today: date,
    delays: list[int] | tuple[int, int] = (5, 12),
) -> bool:
    if sequence_step not in (2, 3):
        return False
    delay = delays[sequence_step - 2]
    return today >= add_business_days(initial_sent, delay)


def cancel_sequence(
    database: Database,
    *,
    company_id: str | None = None,
    contact_id: str | None = None,
    reason: str = "reply",
) -> int:
    with database.session() as session:
        query = select(OutboxMessage).where(
            OutboxMessage.state.in_(
                [OutboxState.PENDING.value, OutboxState.RETRYABLE.value, OutboxState.LEASED.value]
            )
        )
        rows = list(session.scalars(query))
        count = 0
        for row in rows:
            if company_id and not row.idempotency_key.startswith(f"company:{company_id}:"):
                continue
            if contact_id and f":contact:{contact_id}:" not in row.idempotency_key:
                continue
            row.state = OutboxState.CANCELLED.value
            row.last_error_category = reason
            count += 1
        return count


def max_automated_followup(sequence_step: int) -> bool:
    return sequence_step <= 3
