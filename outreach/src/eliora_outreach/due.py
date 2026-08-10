from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


def parse_time(value: str) -> time:
    hour, minute = (int(part) for part in value.split(":", 1))
    return time(hour, minute)


def is_business_day(day: date) -> bool:
    return day.weekday() < 5


def add_business_days(start: date, days: int) -> date:
    current = start
    remaining = days
    while remaining:
        current += timedelta(days=1)
        if is_business_day(current):
            remaining -= 1
    return current


def within_send_window(
    now: datetime, start: str = "07:00", end: str = "19:00", timezone: str = "America/New_York"
) -> bool:
    local = now.astimezone(ZoneInfo(timezone))
    return is_business_day(local.date()) and parse_time(start) <= local.time().replace(
        tzinfo=None
    ) <= parse_time(end)


def research_is_due(
    now: datetime, research_time: str = "09:00", timezone: str = "America/New_York"
) -> bool:
    local = now.astimezone(ZoneInfo(timezone))
    return is_business_day(local.date()) and local.time().replace(tzinfo=None) >= parse_time(
        research_time
    )


def current_local_date(now: datetime, timezone: str) -> date:
    return now.astimezone(ZoneInfo(timezone)).date()


@dataclass(frozen=True)
class DueDecision:
    research_due: bool
    dispatch_allowed: bool
    local_date: date
    reason: str


def decide_due(
    now: datetime,
    *,
    timezone: str,
    research_time: str,
    send_start: str,
    send_end: str,
    paused: bool = False,
) -> DueDecision:
    local = now.astimezone(ZoneInfo(timezone))
    if paused:
        return DueDecision(False, False, local.date(), "paused")
    if not is_business_day(local.date()):
        return DueDecision(False, False, local.date(), "weekend")
    research_due_now = local.time().replace(tzinfo=None) >= parse_time(research_time)
    dispatch = parse_time(send_start) <= local.time().replace(tzinfo=None) <= parse_time(send_end)
    reason = (
        "send_window" if dispatch else ("research_only" if research_due_now else "before_research")
    )
    return DueDecision(research_due_now, dispatch, local.date(), reason)
