"""Record-only workflow for prospect messages sent outside EliOra.

This module deliberately has no SMTP dependency.  Recording changes the local
outbox state so normal dispatch, metrics, and reply tracking see the real send.
The optional reconciliation function accepts an IMAP-capable provider supplied
by the caller and only enriches an already-recorded manual row.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_, select

from .db import AuditEvent, Company, Contact, Database, Draft, OutboxMessage
from .email.outbox import outbox_key

MANUAL_MAIL_PROVIDER = "manual_private_email"
MANUAL_DATA_ORIGIN = "manual_send"


class ManualSendError(ValueError):
    """A safe, actionable manual-send recording error."""


@dataclass(frozen=True)
class ManualSendResult:
    status: str
    draft_id: str
    outbox_id: str
    company: str
    recipient: str
    subject: str
    sent_at: datetime
    message_id_known: bool
    source: str


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ManualSendError(
            "sent_at must include a timezone, for example 2026-08-10T14:30:00-04:00"
        )
    return value.astimezone(timezone.utc)


def _clean_optional(value: str | None) -> str | None:
    cleaned = value.strip() if value else None
    return cleaned or None


def _check_identifier_collisions(
    session: Any,
    *,
    current_id: str | None,
    rfc_message_id: str | None,
) -> None:
    if not rfc_message_id:
        return
    matches = session.scalars(
        select(OutboxMessage).where(
            or_(
                OutboxMessage.message_id == rfc_message_id,
                OutboxMessage.rfc_message_id == rfc_message_id,
            )
        )
    ).all()
    if any(row.id != current_id for row in matches):
        raise ManualSendError(
            f"RFC Message-ID {rfc_message_id!r} is already attached to another outbox message"
        )


def _attach_known_metadata(
    session: Any,
    row: OutboxMessage,
    *,
    rfc_message_id: str | None,
    provider_message_id: str | None,
    provider_thread_id: str | None,
    mailbox_uid: str | None,
) -> None:
    _check_identifier_collisions(session, current_id=row.id, rfc_message_id=rfc_message_id)
    if rfc_message_id:
        if row.rfc_message_id and row.rfc_message_id != rfc_message_id:
            raise ManualSendError("The recorded row already has a different RFC Message-ID")
        if row.message_id and row.message_id != rfc_message_id:
            raise ManualSendError("The recorded row already has a different message identifier")
        row.rfc_message_id = rfc_message_id
        row.message_id = rfc_message_id
    if provider_message_id:
        if row.provider_message_id and row.provider_message_id != provider_message_id:
            raise ManualSendError("The recorded row already has a different provider Message-ID")
        row.provider_message_id = provider_message_id
    if provider_thread_id:
        if row.provider_thread_id and row.provider_thread_id != provider_thread_id:
            raise ManualSendError("The recorded row already has a different provider thread ID")
        row.provider_thread_id = provider_thread_id
    if mailbox_uid:
        if row.mailbox_uid and row.mailbox_uid != mailbox_uid:
            raise ManualSendError("The recorded row already has a different Sent mailbox UID")
        row.mailbox_uid = mailbox_uid


def record_manual_send(
    database: Database,
    *,
    draft_id: str,
    recipient: str,
    subject: str | None = None,
    sent_at: datetime,
    rfc_message_id: str | None = None,
    provider_message_id: str | None = None,
    provider_thread_id: str | None = None,
    mailbox_uid: str | None = None,
    note: str | None = None,
) -> ManualSendResult:
    """Record an already-completed manual send without invoking mail transport."""
    recorded_at = _utc(sent_at)
    recipient = recipient.strip()
    if not recipient or "@" not in recipient:
        raise ManualSendError("recipient must be a valid email address")
    rfc_message_id = _clean_optional(rfc_message_id)
    provider_message_id = _clean_optional(provider_message_id)
    provider_thread_id = _clean_optional(provider_thread_id)
    mailbox_uid = _clean_optional(mailbox_uid)
    note = _clean_optional(note)

    with database.session() as session:
        draft = session.get(Draft, draft_id)
        if draft is None:
            raise ManualSendError("Draft not found")
        company = session.get(Company, draft.company_id)
        contact = session.get(Contact, draft.contact_id) if draft.contact_id else None
        if company is None:
            raise ManualSendError("The draft's company is not persisted")
        if company.data_origin in {"synthetic", "owner_test"}:
            raise ManualSendError("Synthetic/demo drafts cannot be recorded as real manual sends")
        if contact is None:
            raise ManualSendError(
                "This draft has no persisted contact; manual recording requires one"
            )
        if recipient.casefold() != contact.email.strip().casefold():
            raise ManualSendError(
                f"recipient must match the persisted contact ({contact.email}) for this draft"
            )
        manual_subject = _clean_optional(subject) or draft.subject

        key = outbox_key(draft)
        row = session.scalar(select(OutboxMessage).where(OutboxMessage.idempotency_key == key))
        if row is not None and row.state == "sent":
            if row.data_origin == MANUAL_DATA_ORIGIN:
                _attach_known_metadata(
                    session,
                    row,
                    rfc_message_id=rfc_message_id,
                    provider_message_id=provider_message_id,
                    provider_thread_id=provider_thread_id,
                    mailbox_uid=mailbox_uid,
                )
                return ManualSendResult(
                    status="already_recorded",
                    draft_id=draft.id,
                    outbox_id=row.id,
                    company=company.name,
                    recipient=contact.email,
                    subject=row.manual_subject or manual_subject,
                    sent_at=row.sent_at or recorded_at,
                    message_id_known=bool(row.rfc_message_id or row.message_id),
                    source=MANUAL_DATA_ORIGIN,
                )
            return ManualSendResult(
                status="already_recorded",
                draft_id=draft.id,
                outbox_id=row.id,
                company=company.name,
                recipient=contact.email,
                subject=row.manual_subject or manual_subject,
                sent_at=row.sent_at or recorded_at,
                message_id_known=bool(row.rfc_message_id or row.message_id),
                source=row.data_origin,
            )

        if row is None:
            _check_identifier_collisions(session, current_id=None, rfc_message_id=rfc_message_id)
            row = OutboxMessage(
                draft_id=draft.id,
                idempotency_key=key,
                # No deterministic or fabricated identifier for an unknown
                # manually-sent RFC message.
                message_id=rfc_message_id,
                manual_subject=manual_subject,
                rfc_message_id=rfc_message_id,
                scheduled_for=recorded_at,
                state="sent",
                sent_at=recorded_at,
                mail_provider=MANUAL_MAIL_PROVIDER,
                data_origin=MANUAL_DATA_ORIGIN,
            )
            session.add(row)
            session.flush()
        else:
            _attach_known_metadata(
                session,
                row,
                rfc_message_id=rfc_message_id,
                provider_message_id=provider_message_id,
                provider_thread_id=provider_thread_id,
                mailbox_uid=mailbox_uid,
            )
            row.state = "sent"
            row.scheduled_for = recorded_at
            row.sent_at = recorded_at
            row.lease_owner = None
            row.lease_expiry = None
            row.last_error_category = None
            row.mail_provider = MANUAL_MAIL_PROVIDER
            row.data_origin = MANUAL_DATA_ORIGIN
            row.manual_subject = manual_subject

        # For a newly-created row, attach the optional provider fields after
        # flush so all collision checks use the persisted row identity.
        _attach_known_metadata(
            session,
            row,
            rfc_message_id=rfc_message_id,
            provider_message_id=provider_message_id,
            provider_thread_id=provider_thread_id,
            mailbox_uid=mailbox_uid,
        )
        draft.status = "sent_manually"
        metadata: dict[str, Any] = {
            "recipient": contact.email,
            "subject": manual_subject,
            "sent_at": recorded_at.isoformat(),
            "transport": "manual",
            "source": MANUAL_DATA_ORIGIN,
            "rfc_message_id_known": bool(rfc_message_id),
            "provider_thread_id_known": bool(provider_thread_id),
            "mailbox_uid_known": bool(mailbox_uid),
        }
        if note:
            metadata["note"] = note[:1000]
        session.add(
            AuditEvent(
                actor="owner",
                action="manual_send_recorded",
                entity_type="outbox_message",
                entity_id=row.id,
                metadata_json=metadata,
            )
        )
        return ManualSendResult(
            status="recorded",
            draft_id=draft.id,
            outbox_id=row.id,
            company=company.name,
            recipient=contact.email,
            subject=manual_subject,
            sent_at=recorded_at,
            message_id_known=bool(row.rfc_message_id or row.message_id),
            source=MANUAL_DATA_ORIGIN,
        )


def manual_send_candidates(database: Database) -> list[dict[str, str]]:
    """Return persisted, contact-backed real drafts that have not been sent."""
    with database.session() as session:
        sent_drafts = select(OutboxMessage.draft_id).where(OutboxMessage.state == "sent")
        rows = session.execute(
            select(Draft, Company, Contact)
            .join(Company, Company.id == Draft.company_id)
            .join(Contact, Contact.id == Draft.contact_id)
            .where(
                Draft.contact_id.is_not(None),
                Company.data_origin.not_in(["synthetic", "owner_test"]),
                ~Draft.id.in_(sent_drafts),
            )
            .order_by(Draft.created_at.desc())
        ).all()
        return [
            {
                "company": company.name,
                "draft_id": draft.id,
                "recipient": contact.email,
                "subject": draft.subject,
                "status": draft.status,
            }
            for draft, company, contact in rows
        ]


def _candidate_metadata(candidate: Any) -> dict[str, Any] | None:
    if hasattr(candidate, "value"):
        candidate = candidate.value
    return candidate if isinstance(candidate, dict) else None


def reconcile_manual_sends(
    database: Database,
    provider: Any,
    *,
    window_minutes: int = 180,
    draft_id: str | None = None,
) -> dict[str, int]:
    """Attach narrowly matched Sent-folder metadata to manual rows.

    Providers must return one exact candidate or ``None``.  The service also
    verifies recipient/subject metadata when supplied, so a broad or unrelated
    provider response cannot be attached accidentally.
    """
    if window_minutes < 1 or window_minutes > 24 * 60:
        raise ManualSendError("window_minutes must be between 1 and 1440")
    finder = getattr(provider, "find_recent_sent", None)
    if not callable(finder):
        raise ManualSendError(
            "The selected mailbox provider does not support narrow Sent reconciliation"
        )

    counts = {"checked": 0, "reconciled": 0, "pending": 0, "ambiguous": 0}
    with database.session() as session:
        query = (
            select(OutboxMessage, Draft, Contact)
            .join(Draft, Draft.id == OutboxMessage.draft_id)
            .join(Contact, Contact.id == Draft.contact_id)
            .where(
                OutboxMessage.state == "sent",
                OutboxMessage.data_origin == MANUAL_DATA_ORIGIN,
                OutboxMessage.rfc_message_id.is_(None),
                OutboxMessage.provider_message_id.is_(None),
                OutboxMessage.provider_thread_id.is_(None),
                OutboxMessage.mailbox_uid.is_(None),
            )
        )
        if draft_id:
            query = query.where(Draft.id == draft_id)
        pending_rows = [
            (row.id, draft.id, contact.email, row.manual_subject or draft.subject, row.sent_at)
            for row, draft, contact in session.execute(query).all()
        ]

    for outbox_id, current_draft_id, recipient, subject, sent_at in pending_rows:
        counts["checked"] += 1
        if sent_at is None:
            counts["pending"] += 1
            continue
        candidate = _candidate_metadata(
            finder(
                recipient=recipient,
                subject=subject,
                # SQLite returns timezone-aware values as naive datetimes for
                # this schema.  They were normalized to UTC on record.
                sent_at=(
                    sent_at.replace(tzinfo=timezone.utc)
                    if sent_at.tzinfo is None
                    else _utc(sent_at)
                ),
                window_minutes=window_minutes,
            )
        )
        if not candidate:
            counts["pending"] += 1
            continue
        candidate_recipient = candidate.get("recipient")
        candidate_subject = candidate.get("subject")
        if candidate_recipient and str(candidate_recipient).casefold() != recipient.casefold():
            counts["ambiguous"] += 1
            continue
        if candidate_subject and str(candidate_subject).casefold() != subject.casefold():
            counts["ambiguous"] += 1
            continue
        rfc_message_id = _clean_optional(candidate.get("rfc_message_id"))
        provider_message_id = _clean_optional(candidate.get("provider_message_id"))
        provider_thread_id = _clean_optional(candidate.get("provider_thread_id"))
        mailbox_uid = _clean_optional(candidate.get("mailbox_uid"))
        if not any((rfc_message_id, provider_message_id, provider_thread_id, mailbox_uid)):
            counts["ambiguous"] += 1
            continue
        try:
            with database.session() as session:
                row = session.get(OutboxMessage, outbox_id)
                draft = session.get(Draft, current_draft_id)
                if row is None or draft is None:
                    counts["pending"] += 1
                    continue
                _attach_known_metadata(
                    session,
                    row,
                    rfc_message_id=rfc_message_id,
                    provider_message_id=provider_message_id,
                    provider_thread_id=provider_thread_id,
                    mailbox_uid=mailbox_uid,
                )
                session.add(
                    AuditEvent(
                        actor="owner",
                        action="manual_send_reconciled",
                        entity_type="outbox_message",
                        entity_id=row.id,
                        metadata_json={
                            "recipient": recipient,
                            "subject": subject,
                            "transport": "manual",
                            "source": MANUAL_DATA_ORIGIN,
                            "rfc_message_id": rfc_message_id,
                            "provider_thread_id": provider_thread_id,
                            "mailbox_uid": mailbox_uid,
                        },
                    )
                )
            counts["reconciled"] += 1
        except ManualSendError:
            counts["ambiguous"] += 1
    return counts
