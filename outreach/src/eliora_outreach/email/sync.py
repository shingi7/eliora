from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from ..db import (
    Company,
    Contact,
    Database,
    Draft,
    MailboxCheckpoint,
    OutboxMessage,
    ThreadEvent,
    utcnow,
)
from ..email.followups import cancel_sequence
from ..email.replies import classify_reply
from ..enums import EventClass, SuppressionReason, SuppressionScope
from ..providers.base import MailboxProvider
from ..suppression import add_suppression


def _body_text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return str(value or "")


def sync_tracked_replies(
    database: Database,
    provider: MailboxProvider,
    *,
    owner_email: str,
) -> dict[str, int]:
    """Import only inbox messages tied to a sent RFC/thread identifier.

    Classification is local and deterministic. Any substantive inbound reply stops
    the related sequence; opt-outs and bounces additionally create suppressions.
    """
    checkpoint_folder = getattr(
        getattr(getattr(provider, "imap", None), "folders", None), "inbox", "INBOX"
    )
    with database.session() as session:
        checkpoint = session.get(
            MailboxCheckpoint,
            {"mail_provider": "namecheap_private_email", "folder": checkpoint_folder},
        )
        if checkpoint is not None and hasattr(provider, "uid_checkpoint"):
            mailbox_provider: Any = provider
            mailbox_provider.uid_checkpoint = checkpoint.uid
        tracked = list(
            session.scalars(
                select(OutboxMessage)
                .where(OutboxMessage.state == "sent")
                .order_by(OutboxMessage.sent_at)
            )
        )
        links: dict[str, OutboxMessage] = {}
        for row in tracked:
            for identifier in (row.provider_thread_id, row.rfc_message_id, row.message_id):
                if identifier:
                    links[identifier] = row
    identifiers = list(links)
    if not identifiers:
        return {"fetched": 0, "recorded": 0, "suppressed": 0, "cancelled": 0}

    fetched = provider.tracked_events(identifiers)
    provider_checkpoint = getattr(provider, "uid_checkpoint", None)
    counts = {"fetched": len(fetched), "recorded": 0, "suppressed": 0, "cancelled": 0}
    for event in fetched:
        headers = {
            str(key).lower(): str(value) for key, value in (event.get("headers") or {}).items()
        }
        references = f"{headers.get('in-reply-to', '')} {headers.get('references', '')}"
        matched_row = next((links[key] for key in identifiers if key in references), None)
        if matched_row is None and event.get("thread_id"):
            matched_row = links.get(str(event["thread_id"]))
        if matched_row is None:
            continue
        row = matched_row
        provider_message_id = str(
            event.get("provider_message_id") or headers.get("message-id") or ""
        )
        if not provider_message_id:
            continue
        with database.session() as session:
            existing = session.scalar(
                select(ThreadEvent).where(
                    (ThreadEvent.provider_message_id == provider_message_id)
                    | (ThreadEvent.gmail_message_id == provider_message_id)
                )
            )
            if existing:
                continue
            draft = session.get(Draft, row.draft_id)
            contact = session.get(Contact, draft.contact_id) if draft else None
            company = session.get(Company, draft.company_id) if draft else None
            if not contact or not company:
                continue
            body = _body_text(event.get("body"))
            sender = headers.get("from", "")
            classification = classify_reply(
                headers.get("subject", ""),
                body,
                sender_is_owner=owner_email.lower() in sender.lower(),
                headers=headers,
            )
            thread_event = ThreadEvent(
                outbox_message_id=row.id,
                gmail_message_id=provider_message_id,
                provider_message_id=provider_message_id,
                mailbox_uid=str(event.get("mailbox_uid")) if event.get("mailbox_uid") else None,
                mail_provider="namecheap_private_email",
                direction="inbound",
                timestamp=datetime.now(timezone.utc),
                event_class=classification.event_class.value,
                confidence=classification.confidence,
                redacted_summary=classification.summary,
                action_taken="sequence cancellation pending"
                if classification.event_class != EventClass.OUT_OF_OFFICE
                else "review return date",
            )
            session.add(thread_event)
            session.flush()
            event_id = thread_event.id
            counts["recorded"] += 1
            should_cancel = classification.event_class not in {
                EventClass.OUT_OF_OFFICE,
                EventClass.AUTOMATED_SEND,
            }
            if should_cancel:
                counts["cancelled"] += 1
        if should_cancel:
            cancel_sequence(
                database, company_id=company.id, reason=classification.event_class.value
            )
        if classification.event_class in {
            EventClass.UNSUBSCRIBE,
            EventClass.NOT_INTERESTED,
            EventClass.BOUNCE,
        }:
            add_suppression(
                database,
                contact.email,
                SuppressionScope.EMAIL,
                {
                    EventClass.BOUNCE: SuppressionReason.BOUNCE.value,
                    EventClass.UNSUBSCRIBE: SuppressionReason.OPT_OUT.value,
                    EventClass.NOT_INTERESTED: SuppressionReason.NOT_INTERESTED.value,
                }[classification.event_class],
                source_event_id=event_id,
            )
            counts["suppressed"] += 1
    if isinstance(provider_checkpoint, int):
        with database.session() as session:
            checkpoint = session.get(
                MailboxCheckpoint,
                {"mail_provider": "namecheap_private_email", "folder": checkpoint_folder},
            )
            if checkpoint is None:
                checkpoint = MailboxCheckpoint(
                    mail_provider="namecheap_private_email",
                    folder=checkpoint_folder,
                    uid=provider_checkpoint,
                )
                session.add(checkpoint)
            else:
                checkpoint.uid = max(checkpoint.uid, provider_checkpoint)
                checkpoint.updated_at = utcnow()
    return counts
