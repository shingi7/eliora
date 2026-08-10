from __future__ import annotations

import hashlib
import html
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import format_datetime
from urllib.parse import quote

from ..config import SenderSettings
from ..models import DraftContent


@dataclass(frozen=True)
class RenderedEmail:
    content: DraftContent
    message_id: str
    raw_message: bytes


def _footer(sender: SenderSettings) -> str:
    return f"{sender.disclosure}\n{sender.postal_address}\n{sender.opt_out}"


def _html_body(body: str) -> str:
    paragraphs = body.split("\n\n")
    return "".join(
        f"<p>{html.escape(paragraph).replace(chr(10), '<br>')}</p>" for paragraph in paragraphs
    )


def render_draft(
    *,
    company_name: str,
    observation: str,
    hypothesis: str,
    service: str,
    source_fact_ids: list[str],
    sender: SenderSettings,
    step: int = 1,
    contact_first_name: str | None = None,
    subject: str | None = None,
    model: str = "deterministic",
    company_legal_name: str = "EliOra Tech Solutions LLC",
) -> DraftContent:
    if not sender.postal_address or not sender.disclosure or not sender.opt_out:
        raise ValueError(
            "Postal address, disclosure, and opt-out copy are required to render outreach"
        )
    greeting = (
        f"Hello {contact_first_name}," if contact_first_name else f"Hello {company_name} team,"
    )
    if step == 1:
        subject = subject or f"A reporting question for {company_name}"
        body = (
            f"{greeting}\n\nI noticed {observation} I wondered whether that change is creating extra manual work around {hypothesis}\n\n"
            f"EliOra builds compact reporting and data workflows that connect inputs, test the logic, and give operators one dependable view. A practical first step could be our {service}.\n\n"
            "Would a brief comparison of the current process be useful?\n\n"
            f"{sender.display_name}\n{sender.title}\n{company_legal_name}\n"
            f"{sender.disclosure}\n{sender.postal_address}\n{sender.opt_out}"
        )
    elif step == 2:
        subject = subject or f"One idea for {company_name}"
        body = (
            f"{greeting}\n\nFollowing up with one practical idea: the {service.lower()} could start by mapping the recurring inputs, owner checks, and final decision output before any larger change.\n\n"
            "If that workflow is already dependable, no action is needed.\n\n"
            f"{sender.display_name}\n{sender.title}\n{sender.disclosure}\n{sender.postal_address}\n{sender.opt_out}"
        )
    else:
        subject = subject or f"Closing the loop with {company_name}"
        body = (
            f"{greeting}\n\nI’ll close the loop here. If the workflow becomes useful to revisit, EliOra can start with a small, documented slice rather than a broad platform project. There will be no further automated follow-up.\n\n"
            f"{sender.display_name}\n{sender.title}\n{sender.disclosure}\n{sender.postal_address}\n{sender.opt_out}"
        )
    html_body = _html_body(body)
    return DraftContent(
        subject=subject,
        body=body,
        html_body=html_body,
        source_fact_ids=source_fact_ids,
        model=model,
    )


def deterministic_message_id(idempotency_key: str, sender_email: str) -> str:
    domain = sender_email.rsplit("@", 1)[-1].lower() if "@" in sender_email else "localhost"
    digest = hashlib.sha256(idempotency_key.encode()).hexdigest()[:24]
    return f"<eliora-outreach-{digest}@{domain}>"


def build_mime(
    *,
    content: DraftContent,
    sender: SenderSettings,
    recipient: str,
    message_id: str,
    now: datetime | None = None,
    in_reply_to: str | None = None,
    references: str | None = None,
    include_bcc_header: bool = False,
) -> EmailMessage:
    now = now or datetime.now(timezone.utc)
    message = EmailMessage()
    message["From"] = f"{sender.display_name} <{sender.email}>"
    message["To"] = recipient
    if include_bcc_header and sender.owner_bcc:
        message["Bcc"] = sender.owner_bcc
    message["Reply-To"] = sender.reply_to
    message["Date"] = format_datetime(now)
    message["Message-ID"] = message_id
    message["Subject"] = content.subject
    if sender.reply_to:
        message["List-Unsubscribe"] = f"<mailto:{sender.reply_to}?subject={quote('unsubscribe')}>"
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
    if references:
        message["References"] = references
    message["X-EliOra-Outreach-ID"] = hashlib.sha256(message_id.encode()).hexdigest()[:16]
    message.set_content(content.body)
    message.add_alternative(content.html_body, subtype="html")
    return message


def render_email(
    *,
    company_name: str,
    observation: str,
    hypothesis: str,
    service: str,
    source_fact_ids: list[str],
    sender: SenderSettings,
    recipient: str,
    step: int = 1,
    contact_first_name: str | None = None,
    subject: str | None = None,
    model: str = "deterministic",
    company_legal_name: str = "EliOra Tech Solutions LLC",
) -> RenderedEmail:
    content = render_draft(
        company_name=company_name,
        observation=observation,
        hypothesis=hypothesis,
        service=service,
        source_fact_ids=source_fact_ids,
        sender=sender,
        step=step,
        contact_first_name=contact_first_name,
        subject=subject,
        model=model,
        company_legal_name=company_legal_name,
    )
    key = f"{content.subject}:{content.source_fact_ids}:{step}"
    message_id = deterministic_message_id(key, sender.email)
    mime = build_mime(
        content=content,
        sender=sender,
        recipient=recipient,
        message_id=message_id,
    )
    return RenderedEmail(content, message_id, mime.as_bytes())
