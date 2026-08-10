from __future__ import annotations

from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from pathlib import Path

import pytest
from typer.testing import CliRunner

import eliora_outreach.cli as cli_module
from eliora_outreach.cli import app
from eliora_outreach.config import SenderSettings, Settings
from eliora_outreach.db import Company, Contact, Database, Draft, OutboxMessage
from eliora_outreach.email.outbox import create_outbox
from eliora_outreach.explicit_send import ExplicitSendError, send_explicit
from eliora_outreach.paths import AppPaths
from eliora_outreach.pipeline import dispatch_pending
from eliora_outreach.providers.base import MailTransportError
from eliora_outreach.providers.fake import FakeEmailProvider

SENT_AT = datetime(2026, 8, 10, 15, 30, tzinfo=timezone.utc)


class CountingProvider(FakeEmailProvider):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def send(self, raw_message: bytes, *, idempotency_key: str, envelope_recipients=None):
        self.calls += 1
        return super().send(
            raw_message,
            idempotency_key=idempotency_key,
            envelope_recipients=envelope_recipients,
        )


class FailingProvider:
    def __init__(self, *, uncertain: bool = False) -> None:
        self.calls = 0
        self.uncertain = uncertain

    def send(self, raw_message: bytes, *, idempotency_key: str, envelope_recipients=None):
        self.calls += 1
        raise MailTransportError(
            "simulated transport failure",
            category="uncertain_delivery" if self.uncertain else "permanent_server",
            transient=self.uncertain,
            uncertain=self.uncertain,
        )

    def find_by_message_id(self, message_id: str):
        return None


def _fixture(tmp_path: Path, *, draft_status: str = "approved"):
    database = Database(tmp_path / "explicit-send.sqlite3")
    database.create()
    sender = SenderSettings(
        email="owner@elioratechsolutions.com",
        reply_to="owner@elioratechsolutions.com",
        owner_bcc="owner@elioratechsolutions.com",
        postal_address="100 EliOra Way, New York, NY 10001",
    )
    settings = Settings(
        sender=sender,
        providers={"mailbox_username": sender.email},
        live={"enabled": False},
    )
    company = Company(
        id="explicit-company",
        name="Explicit Customer",
        registrable_domain="explicit-customer.com",
        official_website="https://explicit-customer.com",
        country="United States",
        vertical="operational_business",
        permission_basis="unknown",
        data_origin="production",
    )
    contact = Contact(
        id="explicit-contact",
        company_id=company.id,
        email="operations@explicit-customer.com",
        title="Revenue Operations",
        source_id="explicit-source",
        source_url="https://explicit-customer.com/team",
        extraction_method="visible_text",
        official_domain=True,
        role_inbox_category="relevant_role",
        syntactic_valid=True,
        mx_result="not_checked",
        appropriateness_status="eligible",
        source_verification_status="verified",
        no_guessed_address=True,
    )
    draft = Draft(
        id="explicit-draft",
        company_id=company.id,
        contact_id=contact.id,
        sequence_step=1,
        subject="A practical reporting idea",
        plain_text_body="Hello, this is a focused outreach note.",
        html_body="<p>Hello, this is a focused outreach note.</p>",
        source_facts_used=["fact-1"],
        model="test",
        prompt_version="test",
        content_hash="explicit-content",
        quality_findings={"passed": True},
        status=draft_status,
        data_origin="production",
    )
    with database.session() as session:
        session.add_all([company, contact, draft])
    return database, settings, company, contact, draft


def _row(database: Database) -> OutboxMessage:
    with database.session() as session:
        return session.query(OutboxMessage).one()


def test_confirmed_explicit_send_uses_one_transport_call_and_persists_history(
    tmp_path: Path,
) -> None:
    database, settings, _company, contact, draft = _fixture(tmp_path)
    provider = CountingProvider()

    result = send_explicit(
        database,
        settings,
        draft_id=draft.id,
        provider=provider,
        recipient=contact.email,
    )

    assert result.status == "sent"
    assert provider.calls == 1
    row = _row(database)
    assert row.state == "sent"
    assert row.sent_at is not None
    assert row.mail_provider == "namecheap_private_email"
    assert row.data_origin == "production"
    assert row.message_id is not None
    assert row.rfc_message_id is not None
    with database.session() as session:
        assert session.get(Draft, draft.id).status == "sent"
    raw = provider.sent[next(iter(provider.sent))]["raw"]
    message = BytesParser(policy=policy.default).parsebytes(raw)
    assert message["To"] == contact.email
    assert message["Subject"] == draft.subject


def test_duplicate_draft_send_is_blocked_without_second_transport_call(tmp_path: Path) -> None:
    database, settings, _company, contact, draft = _fixture(tmp_path)
    provider = CountingProvider()
    send_explicit(database, settings, draft_id=draft.id, provider=provider)

    with pytest.raises(ExplicitSendError, match="already been sent"):
        send_explicit(
            database,
            settings,
            draft_id=draft.id,
            provider=provider,
            recipient=contact.email,
        )
    assert provider.calls == 1
    with database.session() as session:
        assert session.query(OutboxMessage).count() == 1


def test_confirmation_cancellation_sends_nothing(tmp_path: Path, monkeypatch) -> None:
    database, settings, _company, contact, draft = _fixture(tmp_path)
    provider = CountingProvider()
    monkeypatch.setattr(cli_module, "_paths_db", lambda: (AppPaths(tmp_path / "state"), database))
    monkeypatch.setattr(cli_module, "load_settings", lambda paths=None: settings)
    monkeypatch.setattr(cli_module, "PrivateEmailProvider", lambda *args, **kwargs: provider)

    result = CliRunner().invoke(
        app,
        ["send-now", draft.id, "--recipient", contact.email],
        input="n\n",
    )

    assert result.exit_code == 0, result.output
    assert "Cancelled; no email sent." in result.output
    assert provider.calls == 0
    with database.session() as session:
        assert session.query(OutboxMessage).count() == 0


def test_yes_flag_sends_without_prompt(tmp_path: Path, monkeypatch) -> None:
    database, settings, _company, contact, draft = _fixture(tmp_path)
    provider = CountingProvider()
    monkeypatch.setattr(cli_module, "_paths_db", lambda: (AppPaths(tmp_path / "state"), database))
    monkeypatch.setattr(cli_module, "load_settings", lambda paths=None: settings)
    monkeypatch.setattr(cli_module, "PrivateEmailProvider", lambda *args, **kwargs: provider)

    result = CliRunner().invoke(
        app,
        ["send-now", draft.id, "--recipient", contact.email, "--yes"],
    )

    assert result.exit_code == 0, result.output
    assert "Preview" in result.output
    assert "prospect_messages_sent: 1" in result.output
    assert provider.calls == 1


@pytest.mark.parametrize("uncertain", [False, True])
def test_transport_failure_does_not_mark_sent_and_uncertain_is_not_retried(
    tmp_path: Path, uncertain: bool
) -> None:
    database, settings, _company, contact, draft = _fixture(tmp_path)
    provider = FailingProvider(uncertain=uncertain)

    with pytest.raises(MailTransportError):
        send_explicit(
            database,
            settings,
            draft_id=draft.id,
            provider=provider,
            recipient=contact.email,
        )
    row = _row(database)
    assert row.state == ("uncertain" if uncertain else "failed")
    assert row.sent_at is None
    with database.session() as session:
        assert session.get(Draft, draft.id).status == "approved"
    if uncertain:
        with pytest.raises(ExplicitSendError, match="uncertain delivery"):
            send_explicit(database, settings, draft_id=draft.id, provider=provider)
        assert provider.calls == 1


def test_approved_draft_and_recipient_invariants_are_required(tmp_path: Path) -> None:
    database, settings, _company, contact, draft = _fixture(tmp_path, draft_status="generated")
    provider = CountingProvider()
    with pytest.raises(ExplicitSendError, match="must be approved"):
        send_explicit(database, settings, draft_id=draft.id, provider=provider)
    assert provider.calls == 0

    database, settings, _company, contact, draft = _fixture(tmp_path / "invalid")
    with pytest.raises(ExplicitSendError, match="must match the persisted contact"):
        send_explicit(
            database,
            settings,
            draft_id=draft.id,
            recipient="person@other-company.com",
            provider=provider,
        )
    with pytest.raises(ExplicitSendError, match="valid email"):
        send_explicit(
            database,
            settings,
            draft_id=draft.id,
            recipient="not-an-email",
            provider=provider,
        )
    assert provider.calls == 0


def test_explicit_path_does_not_change_autonomous_permission_gate(tmp_path: Path) -> None:
    database, settings, company, contact, draft = _fixture(tmp_path)
    provider = CountingProvider()
    send_explicit(database, settings, draft_id=draft.id, provider=provider)

    with database.session() as session:
        queued = Draft(
            id="queued-draft",
            company_id=company.id,
            contact_id=contact.id,
            sequence_step=1,
            subject="Queued second draft",
            plain_text_body="Hello",
            html_body="<p>Hello</p>",
            source_facts_used=["fact-1"],
            model="test",
            prompt_version="test",
            content_hash="queued-content",
            quality_findings={"passed": True},
            status="approved",
            data_origin="production",
        )
        session.add(queued)
    create_outbox(
        database,
        queued,
        scheduled_for=SENT_AT,
        sender=settings.sender,
        recipient=contact.email,
    )
    autonomous_settings = settings.model_copy(
        update={
            "live": settings.live.model_copy(update={"enabled": True}),
            "providers": settings.providers.model_copy(
                update={"permission_policy_acknowledged": True}
            ),
        }
    )
    result = dispatch_pending(
        database,
        autonomous_settings,
        provider=provider,
        now=SENT_AT,
    )
    assert result == {"sent": 0, "blocked": "permission_basis_required"}
    assert provider.calls == 1
    with database.session() as session:
        assert session.get(OutboxMessage, "missing") is None
        queued_row = session.query(OutboxMessage).filter(OutboxMessage.draft_id == queued.id).one()
        assert queued_row.state == "pending"
