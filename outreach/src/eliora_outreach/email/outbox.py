from __future__ import annotations

import socket
from datetime import datetime, timedelta

from sqlalchemy import select

from ..db import Database, Draft, OutboxMessage, utcnow
from ..enums import OutboxState
from ..providers.base import EmailProvider, TransportResult
from .render import build_mime, deterministic_message_id


def outbox_key(draft: Draft) -> str:
    return f"company:{draft.company_id}:contact:{draft.contact_id}:step:{draft.sequence_step}:content:{draft.content_hash}"


def create_outbox(
    database: Database,
    draft: Draft,
    *,
    scheduled_for: datetime,
    sender,
    recipient: str,
    in_reply_to: str | None = None,
    references: str | None = None,
    data_origin: str = "production",
) -> OutboxMessage:
    if draft.contact_id is None:
        raise ValueError("Cannot create an outbox message for a draft without a contact")
    key = outbox_key(draft)
    with database.session() as session:
        existing = session.scalar(select(OutboxMessage).where(OutboxMessage.idempotency_key == key))
        if existing:
            return existing
        message_id = deterministic_message_id(key, sender.email)
        message = OutboxMessage(
            draft_id=draft.id,
            idempotency_key=key,
            message_id=message_id,
            rfc_message_id=message_id,
            mail_provider="namecheap_private_email",
            scheduled_for=scheduled_for,
            state=OutboxState.PENDING.value,
            data_origin=data_origin,
        )
        session.add(message)
        session.flush()
        return message


def lease_pending(
    database: Database,
    *,
    owner: str | None = None,
    now: datetime | None = None,
    lease_minutes: int = 10,
) -> OutboxMessage | None:
    now = now or utcnow()
    owner = owner or socket.gethostname()
    with database.session() as session:
        row = session.scalar(
            select(OutboxMessage)
            .where(
                OutboxMessage.state.in_(
                    [
                        OutboxState.PENDING.value,
                        OutboxState.RETRYABLE.value,
                    ]
                ),
                OutboxMessage.scheduled_for <= now,
            )
            .order_by(OutboxMessage.scheduled_for)
            .limit(1)
        )
        if not row:
            return None
        row.state = OutboxState.LEASED.value
        row.lease_owner = owner
        row.lease_expiry = now + timedelta(minutes=lease_minutes)
        row.attempt_count += 1
        return row


def lease_message(
    database: Database,
    message_id: str,
    *,
    owner: str | None = None,
    now: datetime | None = None,
    lease_minutes: int = 10,
) -> OutboxMessage | None:
    """Lease one already-selected pending message without scanning the queue."""
    now = now or utcnow()
    owner = owner or socket.gethostname()
    with database.session() as session:
        row = session.get(OutboxMessage, message_id)
        if row is None or row.state not in {
            OutboxState.PENDING.value,
            OutboxState.RETRYABLE.value,
        }:
            return None
        row.state = OutboxState.LEASED.value
        row.lease_owner = owner
        row.lease_expiry = now + timedelta(minutes=lease_minutes)
        row.attempt_count += 1
        return row


def send_leased(
    database: Database,
    provider: EmailProvider,
    message_id: str,
    *,
    sender,
    recipient: str,
    in_reply_to: str | None = None,
    references: str | None = None,
) -> OutboxMessage:
    with database.session() as session:
        row = session.get(OutboxMessage, message_id)
        if not row:
            raise ValueError("Outbox message not found")
        draft = session.get(Draft, row.draft_id)
        if not draft:
            raise ValueError("Outbox draft not found")
        if not row.message_id:
            raise ValueError("Outbox message has no RFC Message-ID and cannot be dispatched")
        content = __import__("eliora_outreach.models", fromlist=["DraftContent"]).DraftContent(
            subject=draft.subject,
            body=draft.plain_text_body,
            html_body=draft.html_body,
            source_fact_ids=draft.source_facts_used,
            model=draft.model,
            prompt_version=draft.prompt_version,
        )
        row.state = OutboxState.SENDING.value
        session.flush()
        raw = build_mime(
            content=content,
            sender=sender,
            recipient=recipient,
            message_id=row.message_id,
            in_reply_to=in_reply_to,
            references=references,
            include_bcc_header=False,
        ).as_bytes()
        owner_recipients = (
            [sender.owner_bcc]
            if sender.owner_bcc and sender.owner_bcc.lower() != recipient.lower()
            else []
        )
        envelope_recipients = [recipient, *owner_recipients]
        send_error: Exception | None = None
        result = None
        try:
            result = provider.send(
                raw,
                idempotency_key=row.idempotency_key,
                envelope_recipients=envelope_recipients,
            )
        except Exception as exc:
            if getattr(exc, "uncertain", False):
                row.state = OutboxState.UNCERTAIN.value
                row.last_error_category = "uncertain_delivery"
            elif getattr(exc, "transient", False):
                row.state = OutboxState.RETRYABLE.value
                row.last_error_category = getattr(exc, "category", type(exc).__name__)
            else:
                row.state = OutboxState.FAILED.value
                row.last_error_category = getattr(exc, "category", type(exc).__name__)
            send_error = exc
        if result is None:
            if send_error is None:
                row.state = OutboxState.FAILED.value
                row.last_error_category = "missing_transport_result"
                send_error = RuntimeError("Mail provider returned no transport result")
            session.commit()
            raise send_error
        value = result.value
        if isinstance(value, TransportResult):
            provider_message_id = value.provider_message_id
            provider_thread_id = value.provider_thread_id
            rfc_message_id = value.rfc_message_id
            mailbox_uid = value.mailbox_uid
        elif isinstance(value, dict):
            provider_message_id = value.get("provider_message_id") or value.get("id")
            provider_thread_id = value.get("provider_thread_id") or value.get("threadId")
            rfc_message_id = value.get("rfc_message_id") or row.message_id
            mailbox_uid = value.get("mailbox_uid")
        else:
            provider_message_id = provider_thread_id = mailbox_uid = None
            rfc_message_id = row.message_id
        row.state = OutboxState.SENT.value
        row.sent_at = utcnow()
        row.last_error_category = None
        row.rfc_message_id = rfc_message_id
        row.provider_message_id = provider_message_id
        row.provider_thread_id = provider_thread_id
        row.mailbox_uid = mailbox_uid
        row.mail_provider = "namecheap_private_email"
        row.api_request_id = result.request_id
        return row


def reconcile_uncertain(database: Database, provider: EmailProvider, row: OutboxMessage) -> bool:
    identifier = row.rfc_message_id or row.message_id
    if not identifier:
        return False
    found = provider.find_by_message_id(identifier)
    if not found:
        return False
    with database.session() as session:
        current = session.get(OutboxMessage, row.id)
        if current:
            current.state = OutboxState.SENT.value
            current.sent_at = utcnow()
            current.last_error_category = "reconciled"
            current.api_request_id = found.request_id
            value = found.value
            if isinstance(value, TransportResult):
                current.rfc_message_id = value.rfc_message_id
                current.provider_message_id = value.provider_message_id
                current.provider_thread_id = value.provider_thread_id
                current.mailbox_uid = value.mailbox_uid
            elif isinstance(value, dict):
                current.provider_message_id = value.get("provider_message_id") or value.get("id")
                current.provider_thread_id = value.get("provider_thread_id") or value.get(
                    "threadId"
                )
                current.mailbox_uid = value.get("mailbox_uid")
            current.mail_provider = "namecheap_private_email"
    return True
