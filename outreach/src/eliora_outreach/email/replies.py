from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ..enums import EventClass


@dataclass(frozen=True)
class ReplyClassification:
    event_class: EventClass
    confidence: float
    summary: str


BOUNCE = (
    "delivery failed",
    "mail delivery subsystem",
    "address not found",
    "user unknown",
    "550 ",
    "undeliverable",
    "diagnostic-code",
    "status: 5",
)
UNSUBSCRIBE = (
    "unsubscribe",
    "remove me",
    "stop contacting",
    "stop emailing",
    "no thanks",
    "do not contact",
    "don't contact",
)
NOT_INTERESTED = ("not interested", "no interest", "pass for now")
OOO = ("out of office", "automatic reply", "away from the office", "vacation auto")


def classify_reply(
    subject: str,
    body: str,
    *,
    sender_is_owner: bool = False,
    headers: Mapping[str, str] | None = None,
) -> ReplyClassification:
    normalized_headers = {key.lower(): value.lower() for key, value in (headers or {}).items()}
    content_type = normalized_headers.get("content-type", "")
    sender = normalized_headers.get("from", "")
    if (
        "delivery-status" in content_type
        or "report-type=delivery-status" in content_type
        or "mailer-daemon" in sender
        or "postmaster" in sender
        or "final-recipient" in normalized_headers
        or "diagnostic-code" in normalized_headers
    ):
        return ReplyClassification(EventClass.BOUNCE, 0.99, "Delivery-status notification detected")
    text = f"{subject}\n{body}".lower()
    if any(marker in text for marker in BOUNCE):
        return ReplyClassification(EventClass.BOUNCE, 0.99, "Delivery failure detected")
    if any(marker in text for marker in UNSUBSCRIBE):
        return ReplyClassification(EventClass.UNSUBSCRIBE, 0.99, "Reply-based opt-out detected")
    if any(marker in text for marker in NOT_INTERESTED):
        return ReplyClassification(
            EventClass.NOT_INTERESTED, 0.98, "Not-interested response detected"
        )
    if sender_is_owner:
        return ReplyClassification(
            EventClass.HUMAN_OWNER_REPLY, 0.99, "Owner wrote in tracked thread"
        )
    if any(marker in text for marker in OOO):
        return ReplyClassification(
            EventClass.OUT_OF_OFFICE, 0.95, "Out-of-office response detected"
        )
    if any(
        marker in text for marker in ("yes", "interested", "learn more", "available", "schedule")
    ):
        return ReplyClassification(
            EventClass.POSITIVE, 0.75, "Potentially substantive positive response"
        )
    if "?" in text:
        return ReplyClassification(
            EventClass.QUESTION, 0.75, "Inbound question requires owner action"
        )
    if text.strip():
        return ReplyClassification(EventClass.AMBIGUOUS, 0.65, "Human reply requires review")
    return ReplyClassification(EventClass.NEUTRAL, 0.4, "No substantive reply text")


def is_human_reply(event: dict[str, object]) -> bool:
    return str(event.get("direction", "inbound")) == "inbound" and not bool(
        event.get("automated", False)
    )
