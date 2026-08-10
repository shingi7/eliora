"""One-draft, owner-authorized sending through the existing mail transport."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from .config import Settings, is_placeholder_email, looks_like_email
from .db import AuditEvent, Company, Contact, Database, Draft, OutboxMessage
from .email.outbox import create_outbox, lease_message, send_leased
from .enums import DraftStatus, OutboxState
from .providers.base import EmailProvider
from .research.canonicalize import is_reserved_domain, registrable_domain
from .research.contacts import validate_public_contact
from .suppression import is_suppressed
from .usage import increment_usage


class ExplicitSendError(ValueError):
    """A safe, actionable error before an explicit send is attempted."""


@dataclass(frozen=True)
class ExplicitSendPreview:
    draft_id: str
    company: str
    recipient: str
    subject: str
    body: str
    sender: str
    contact_id: str


@dataclass(frozen=True)
class ExplicitSendResult:
    status: str
    draft_id: str
    outbox_id: str
    company: str
    recipient: str
    subject: str
    sent_at: datetime
    message_id: str | None
    provider_message_id: str | None
    provider_thread_id: str | None
    mailbox_uid: str | None
    data_origin: str


def _safe_recipient(value: str) -> str:
    normalized = value.strip().lower()
    if not looks_like_email(normalized):
        raise ExplicitSendError("recipient must be a valid email address")
    domain = normalized.rsplit("@", 1)[-1]
    if is_reserved_domain(f"https://{domain}"):
        raise ExplicitSendError("recipient domain is reserved, private, or a placeholder")
    return normalized


def _validate_sender(settings: Settings) -> None:
    if settings.providers.mail_provider != "namecheap_private_email":
        raise ExplicitSendError("configured mail provider is not Namecheap Private Email")
    addresses = (settings.sender.email, settings.sender.reply_to, settings.sender.owner_bcc)
    if not all(looks_like_email(value) for value in addresses):
        raise ExplicitSendError("sender, Reply-To, and owner BCC must be configured addresses")
    if any(is_placeholder_email(value) for value in addresses):
        raise ExplicitSendError("sender configuration contains a placeholder address")
    mailbox = settings.providers.mailbox_username or settings.sender.email
    if mailbox.casefold() != settings.sender.email.casefold():
        raise ExplicitSendError("mailbox username must match the configured sender identity")
    if not settings.sender.postal_address.strip():
        raise ExplicitSendError("sender postal address is required")
    if not settings.sender.disclosure.strip() or not settings.sender.opt_out.strip():
        raise ExplicitSendError("sender disclosure and opt-out copy are required")


def _load_validated_context(
    database: Database,
    settings: Settings,
    *,
    draft_id: str,
    recipient: str | None,
) -> tuple[Draft, Company, Contact, str]:
    _validate_sender(settings)
    with database.session() as session:
        draft = session.get(Draft, draft_id)
        if draft is None:
            raise ExplicitSendError("Draft not found")
        if draft.status in {DraftStatus.SENT.value, DraftStatus.SENT_MANUALLY.value}:
            raise ExplicitSendError("draft has already been sent")
        if draft.status != DraftStatus.APPROVED.value:
            raise ExplicitSendError(f"draft must be approved; current status is {draft.status}")
        company = session.get(Company, draft.company_id)
        contact = session.get(Contact, draft.contact_id) if draft.contact_id else None
        if company is None:
            raise ExplicitSendError("Draft company is not persisted")
        if company.data_origin in {"synthetic", "owner_test"}:
            raise ExplicitSendError("synthetic/demo drafts cannot send prospect email")
        if contact is None:
            raise ExplicitSendError(
                "A persisted contact is required; attach one with lead add-contact first"
            )
        effective_recipient = _safe_recipient(recipient or contact.email)
        if effective_recipient != contact.email.strip().casefold():
            raise ExplicitSendError(f"recipient must match the persisted contact ({contact.email})")
        if (
            not contact.syntactic_valid
            or not contact.official_domain
            or not contact.no_guessed_address
        ):
            raise ExplicitSendError("persisted contact failed domain/provenance safety checks")
        if contact.appropriateness_status in {"inappropriate", "rejected"}:
            raise ExplicitSendError("persisted contact is not an appropriate business recipient")
        validation = validate_public_contact(
            contact.email,
            company.registrable_domain,
            source_url=contact.source_url,
            extraction_method=contact.extraction_method,
            role=contact.title,
            mx_valid=contact.mx_valid,
            mx_result=contact.mx_result or "not_checked",
        )
        if not validation.valid:
            raise ExplicitSendError(f"persisted contact failed validation: {validation.reason}")
        if is_suppressed(
            database,
            email=contact.email,
            domain=company.registrable_domain,
            company_id=company.id,
        ):
            raise ExplicitSendError("recipient, company, or domain is actively suppressed")
        if is_reserved_domain(f"https://{registrable_domain(company.registrable_domain)}"):
            raise ExplicitSendError("company domain is reserved, private, or a placeholder")
        return draft, company, contact, effective_recipient


def preview_explicit_send(
    database: Database,
    settings: Settings,
    *,
    draft_id: str,
    recipient: str | None = None,
) -> ExplicitSendPreview:
    draft, company, contact, effective_recipient = _load_validated_context(
        database, settings, draft_id=draft_id, recipient=recipient
    )
    return ExplicitSendPreview(
        draft_id=draft.id,
        company=company.name,
        recipient=effective_recipient,
        subject=draft.subject,
        body=draft.plain_text_body,
        sender=settings.sender.email,
        contact_id=contact.id,
    )


def _existing_outbox(database: Database, draft_id: str) -> OutboxMessage | None:
    with database.session() as session:
        rows = session.scalars(
            select(OutboxMessage)
            .where(OutboxMessage.draft_id == draft_id)
            .order_by(OutboxMessage.scheduled_for.desc(), OutboxMessage.id.desc())
        ).all()
    if len(rows) > 1:
        raise ExplicitSendError("draft has multiple outbox/history rows; refusing another send")
    return rows[0] if rows else None


def _block_existing_outbox(row: OutboxMessage | None) -> None:
    if row is None:
        return
    if row.state == OutboxState.SENT.value:
        raise ExplicitSendError("draft has already been sent")
    if row.state == OutboxState.UNCERTAIN.value:
        raise ExplicitSendError(
            "draft has uncertain delivery; reconcile it before attempting any retry"
        )
    raise ExplicitSendError(f"draft already has an outbox row in state {row.state}")


def send_explicit(
    database: Database,
    settings: Settings,
    *,
    draft_id: str,
    provider: EmailProvider,
    recipient: str | None = None,
) -> ExplicitSendResult:
    """Send exactly one approved contact-backed draft through the existing provider."""
    draft, company, contact, effective_recipient = _load_validated_context(
        database, settings, draft_id=draft_id, recipient=recipient
    )
    _block_existing_outbox(_existing_outbox(database, draft.id))
    now = datetime.now().astimezone()
    message = create_outbox(
        database,
        draft,
        scheduled_for=now,
        sender=settings.sender,
        recipient=effective_recipient,
        data_origin=draft.data_origin,
    )
    leased = lease_message(database, message.id, now=now)
    if leased is None:
        raise ExplicitSendError("draft could not be exclusively leased for explicit sending")
    sent = send_leased(
        database,
        provider,
        leased.id,
        sender=settings.sender,
        recipient=effective_recipient,
    )
    with database.session() as session:
        stored_draft = session.get(Draft, draft.id)
        if stored_draft is not None:
            stored_draft.status = DraftStatus.SENT.value
        session.add(
            AuditEvent(
                actor="owner",
                action="explicit_send_completed",
                entity_type="outbox_message",
                entity_id=sent.id,
                metadata_json={
                    "authorization": "owner_explicit_one_draft",
                    "company_id": company.id,
                    "contact_id": contact.id,
                    "recipient": effective_recipient,
                    "subject": draft.subject,
                    "transport": "namecheap_private_email",
                    "data_origin": sent.data_origin,
                    "rfc_message_id": sent.rfc_message_id,
                    "provider_message_id": sent.provider_message_id,
                    "provider_thread_id": sent.provider_thread_id,
                    "mailbox_uid": sent.mailbox_uid,
                },
            )
        )
    sent_at = sent.sent_at
    if sent_at is None:
        raise RuntimeError("successful transport returned no sent_at")
    day = sent_at.astimezone(ZoneInfo(settings.schedule.fallback_timezone)).date()
    increment_usage(
        database,
        day,
        settings.schedule.fallback_timezone,
        initial_messages_sent=1 if draft.sequence_step == 1 else 0,
        followups_sent=1 if draft.sequence_step > 1 else 0,
        total_recipients=1
        + int(settings.sender.owner_bcc.casefold() != effective_recipient.casefold()),
    )
    return ExplicitSendResult(
        status="sent",
        draft_id=draft.id,
        outbox_id=sent.id,
        company=company.name,
        recipient=effective_recipient,
        subject=draft.subject,
        sent_at=sent_at,
        message_id=sent.rfc_message_id or sent.message_id,
        provider_message_id=sent.provider_message_id,
        provider_thread_id=sent.provider_thread_id,
        mailbox_uid=sent.mailbox_uid,
        data_origin=sent.data_origin,
    )
