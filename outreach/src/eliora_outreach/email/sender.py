"""Small sender facade used by future workers and the local CLI."""

from __future__ import annotations

from ..config import SenderSettings
from ..db import Database, OutboxMessage
from ..providers.base import EmailProvider
from .outbox import reconcile_uncertain, send_leased


def send_leased_message(
    database: Database,
    provider: EmailProvider,
    message: OutboxMessage,
    *,
    sender: SenderSettings,
    recipient: str,
    in_reply_to: str | None = None,
    references: str | None = None,
) -> OutboxMessage:
    """Send one already leased message; caller owns window/quota/suppression gates."""
    return send_leased(
        database,
        provider,
        message.id,
        sender=sender,
        recipient=recipient,
        in_reply_to=in_reply_to,
        references=references,
    )


__all__ = ["send_leased_message", "reconcile_uncertain"]
