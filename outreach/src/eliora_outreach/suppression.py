from __future__ import annotations

import re
from collections.abc import Iterable

from sqlalchemy import select

from .db import Database, Suppression
from .enums import SuppressionScope


def normalize_scope_value(value: str, scope: SuppressionScope | str) -> str:
    scope = SuppressionScope(scope)
    normalized = value.strip().lower()
    if scope is SuppressionScope.EMAIL:
        return normalized
    if scope is SuppressionScope.DOMAIN:
        return normalized.removeprefix("www.")
    return re.sub(r"\s+", " ", normalized)


def add_suppression(
    database: Database,
    value: str,
    scope: SuppressionScope | str,
    reason: str,
    source_event_id: str | None = None,
    data_origin: str = "production",
) -> Suppression:
    normalized = normalize_scope_value(value, scope)
    with database.session() as session:
        existing = session.scalar(
            select(Suppression).where(
                Suppression.scope == str(scope),
                Suppression.normalized_value == normalized,
                Suppression.removed_at.is_(None),
            )
        )
        if existing:
            return existing
        row = Suppression(
            scope=str(scope),
            normalized_value=normalized,
            reason=reason,
            source_event_id=source_event_id,
            data_origin=data_origin,
        )
        session.add(row)
        session.flush()
        return row


def is_suppressed(
    database: Database,
    *,
    email: str | None = None,
    domain: str | None = None,
    company_id: str | None = None,
) -> bool:
    checks: list[tuple[SuppressionScope, str | None]] = [
        (SuppressionScope.EMAIL, email),
        (SuppressionScope.DOMAIN, domain),
        (SuppressionScope.COMPANY, company_id),
    ]
    with database.session() as session:
        for scope, value in checks:
            if value and session.scalar(
                select(Suppression.id).where(
                    Suppression.scope == str(scope),
                    Suppression.normalized_value == normalize_scope_value(value, scope),
                    Suppression.removed_at.is_(None),
                )
            ):
                return True
    return False


def active_suppressions(database: Database) -> Iterable[Suppression]:
    with database.session() as session:
        return list(session.scalars(select(Suppression).where(Suppression.removed_at.is_(None))))


def remove_suppression(database: Database, suppression_id: str, reason: str) -> bool:
    with database.session() as session:
        row = session.get(Suppression, suppression_id)
        if not row or row.removed_at is not None:
            return False
        from .db import utcnow

        row.removed_at = utcnow()
        row.removal_reason = reason
        return True
