from __future__ import annotations

from datetime import date

from .config import LimitSettings
from .db import DailyUsage, Database


def usage_for(database: Database, day: date, timezone: str) -> DailyUsage:
    with database.session() as session:
        row = session.get(DailyUsage, (day.isoformat(), timezone))
        if row is None:
            row = DailyUsage(date=day.isoformat(), timezone=timezone)
            session.add(row)
            session.flush()
        return row


def within_limit(
    database: Database, day: date, timezone: str, field: str, increment: int, limit: int
) -> bool:
    row = usage_for(database, day, timezone)
    return getattr(row, field) + increment <= limit


def increment_usage(database: Database, day: date, timezone: str, **increments: int) -> DailyUsage:
    with database.session() as session:
        row = session.get(DailyUsage, (day.isoformat(), timezone))
        if row is None:
            row = DailyUsage(date=day.isoformat(), timezone=timezone)
            session.add(row)
        for field, increment in increments.items():
            if not hasattr(row, field):
                raise ValueError(f"Unknown usage field: {field}")
            # SQLAlchemy applies mapped column defaults at flush time; a newly
            # created row therefore still exposes None before that flush.
            setattr(row, field, (getattr(row, field) or 0) + increment)
        session.flush()
        return row


def caps_summary(limits: LimitSettings) -> dict[str, int]:
    return {
        "prospect_messages": limits.hard_daily_prospect_messages,
        "recipients": limits.hard_daily_recipients,
        "initials_recommended": limits.recommended_daily_initials,
        "followups_recommended": limits.recommended_daily_followups,
        "openai_calls": limits.openai_calls,
        "web_search_calls": limits.web_search_calls,
    }


def warmup_caps(activation_date: date, today: date) -> tuple[int, int]:
    """Return (initials, follow-ups) for the conservative activation ramp."""
    elapsed_days = (today - activation_date).days + 1
    if elapsed_days <= 7:
        return 3, 1
    if elapsed_days <= 14:
        return 5, 2
    return 7, 3


def dispatch_capacity(
    database: Database,
    day: date,
    timezone: str,
    limits: LimitSettings,
    *,
    activation_date: date | None = None,
    sequence_step: int = 1,
) -> bool:
    """Check prospect and total-recipient ceilings, counting the owner BCC."""
    row = usage_for(database, day, timezone)
    warm_initials, warm_followups = (
        warmup_caps(activation_date, day)
        if activation_date
        else (
            limits.recommended_daily_initials,
            limits.recommended_daily_initials,
        )
    )
    if row.initial_messages_sent + (1 if sequence_step == 1 else 0) > min(
        limits.hard_daily_prospect_messages,
        warm_initials,
    ):
        return False
    if sequence_step > 1 and row.followups_sent + 1 > min(
        limits.hard_daily_followups,
        warm_followups,
    ):
        return False
    return row.total_recipients + 2 <= limits.hard_daily_recipients
