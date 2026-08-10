from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from typer.testing import CliRunner

import eliora_outreach.cli as cli
from eliora_outreach.config import SenderSettings, Settings
from eliora_outreach.dashboard.app import create_app
from eliora_outreach.db import (
    AuditEvent,
    Company,
    Contact,
    Database,
    Draft,
    LeadScore,
    OutboxMessage,
    ThreadEvent,
)
from eliora_outreach.email.outbox import create_outbox
from eliora_outreach.email.sync import sync_tracked_replies
from eliora_outreach.manual_send import reconcile_manual_sends, record_manual_send
from eliora_outreach.paths import AppPaths
from eliora_outreach.pipeline import dispatch_pending
from eliora_outreach.providers.fake import FakeEmailProvider

SENT_AT = datetime(2026, 8, 10, 15, 30, tzinfo=timezone.utc)


def make_fixture(tmp_path: Path) -> tuple[Database, SenderSettings, Draft, Contact, Company]:
    database = Database(tmp_path / "manual-send.sqlite3")
    database.create()
    company = Company(
        id="manual-company",
        name="Manual Customer",
        registrable_domain="manual-customer.com",
        official_website="https://manual-customer.com",
        country="United States",
        vertical="operational_business",
        permission_basis="existing_relationship",
    )
    contact = Contact(
        id="manual-contact",
        company_id=company.id,
        email="hello@manual-customer.com",
        title="Operations",
        source_id="manual-source",
        source_url="https://manual-customer.com/contact",
        extraction_method="mailto",
        official_domain=True,
        syntactic_valid=True,
        appropriateness_status="eligible",
        source_verification_status="verified",
    )
    draft = Draft(
        id="manual-draft",
        company_id=company.id,
        contact_id=contact.id,
        sequence_step=1,
        subject="A practical operations idea",
        plain_text_body="Hello",
        html_body="<p>Hello</p>",
        source_facts_used=[],
        model="test",
        prompt_version="test",
        content_hash="manual-content",
        quality_findings={"passed": True},
        status="approved",
    )
    sender = SenderSettings(
        email="owner@eliora.example",
        reply_to="owner@eliora.example",
        owner_bcc="owner@eliora.example",
        postal_address="100 Demo Way, New York, NY",
    )
    with database.session() as session:
        session.add_all([company, contact, draft])
    return database, sender, draft, contact, company


def test_record_manual_send_is_idempotent_and_supports_unknown_message_id(tmp_path: Path) -> None:
    database, _sender, draft, contact, _company = make_fixture(tmp_path)

    first = record_manual_send(
        database,
        draft_id=draft.id,
        recipient=contact.email,
        subject="Actual manually sent subject",
        sent_at=SENT_AT,
        note="Sent from the private mailbox.",
    )
    second = record_manual_send(
        database,
        draft_id=draft.id,
        recipient=contact.email,
        subject="Actual manually sent subject",
        sent_at=SENT_AT,
    )

    assert first.status == "recorded"
    assert second.status == "already_recorded"
    with database.session() as session:
        rows = session.query(OutboxMessage).all()
        assert len(rows) == 1
        assert rows[0].state == "sent"
        assert rows[0].data_origin == "manual_send"
        assert rows[0].mail_provider == "manual_private_email"
        assert rows[0].message_id is None
        assert rows[0].rfc_message_id is None
        assert rows[0].manual_subject == "Actual manually sent subject"
        assert session.get(Draft, draft.id).status == "sent_manually"
        assert (
            session.query(AuditEvent).filter(AuditEvent.action == "manual_send_recorded").count()
            == 1
        )


def test_manual_record_reuses_pending_key_and_dispatch_never_calls_provider(tmp_path: Path) -> None:
    database, sender, draft, contact, _company = make_fixture(tmp_path)
    pending = create_outbox(
        database,
        draft,
        scheduled_for=SENT_AT,
        sender=sender,
        recipient=contact.email,
    )
    fake = FakeEmailProvider()
    result = record_manual_send(
        database,
        draft_id=draft.id,
        recipient=contact.email,
        sent_at=SENT_AT,
    )
    settings = Settings(
        sender=sender,
        providers={"permission_policy_acknowledged": True},
        live={"enabled": True},
    )
    dispatch_result = dispatch_pending(
        database,
        settings,
        provider=fake,
        now=SENT_AT,
    )

    assert result.outbox_id == pending.id
    assert dispatch_result == {"sent": 0, "blocked": "no_due_messages"}
    assert fake.sent == {}
    with database.session() as session:
        assert session.get(OutboxMessage, pending.id).state == "sent"


def test_record_only_cli_reports_zero_transmissions(tmp_path: Path, monkeypatch) -> None:
    database, _sender, draft, contact, _company = make_fixture(tmp_path)
    monkeypatch.setattr(
        cli,
        "_paths_db",
        lambda: (AppPaths(tmp_path / "state"), database),
    )
    result = CliRunner().invoke(
        cli.app,
        [
            "manual-send",
            "record",
            draft.id,
            "--recipient",
            contact.email,
            "--subject",
            "Actual CLI subject",
            "--yes",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "prospect_messages_sent: 0 (record-only; no email sent)" in result.output


def test_doctor_reports_current_schema_version_without_mailbox_access(
    tmp_path: Path, monkeypatch
) -> None:
    database = Database(tmp_path / "doctor.sqlite3")
    database.create()
    paths = AppPaths(tmp_path / "doctor-state")
    monkeypatch.setattr(cli, "_paths_db", lambda: (paths, database))
    monkeypatch.setattr(cli, "load_settings", lambda paths=None: Settings())
    monkeypatch.setattr(cli, "_mail_password_present", lambda settings: (False, "not configured"))
    monkeypatch.setattr(cli, "check_mx", lambda domain: (True, "mocked"))
    monkeypatch.setattr(
        cli,
        "advisory_dns_checks",
        lambda domain: {"spf": "mocked", "dmarc": "mocked"},
    )
    result = CliRunner().invoke(cli.app, ["doctor"])

    assert "PASS Schema migration: version 8" in result.output
    assert "SMTP authentication" in result.output
    assert "IMAP authentication / folders" in result.output


class NarrowSentProvider(FakeEmailProvider):
    def __init__(self, candidate: dict[str, str] | None) -> None:
        super().__init__()
        self.candidate = candidate
        self.calls: list[tuple[str, str]] = []

    def find_recent_sent(
        self,
        *,
        recipient: str,
        subject: str,
        sent_at: datetime,
        window_minutes: int = 180,
    ) -> dict[str, str] | None:
        self.calls.append((recipient, subject))
        return self.candidate


def test_reconcile_attaches_real_metadata_and_rejects_unrelated_mail(tmp_path: Path) -> None:
    database, _sender, draft, contact, _company = make_fixture(tmp_path)
    record_manual_send(
        database,
        draft_id=draft.id,
        recipient=contact.email,
        sent_at=SENT_AT,
    )
    unrelated = NarrowSentProvider(
        {
            "recipient": "other@example.com",
            "subject": "Unrelated",
            "rfc_message_id": "<unrelated@example.com>",
            "mailbox_uid": "8",
        }
    )
    assert reconcile_manual_sends(database, unrelated) == {
        "checked": 1,
        "reconciled": 0,
        "pending": 0,
        "ambiguous": 1,
    }
    with database.session() as session:
        assert session.get(OutboxMessage, "missing") is None
        row = session.query(OutboxMessage).one()
        assert row.rfc_message_id is None

    provider = NarrowSentProvider(
        {
            "recipient": contact.email,
            "subject": draft.subject,
            "rfc_message_id": "<real-manual@example.com>",
            "provider_thread_id": "real-thread",
            "mailbox_uid": "42",
        }
    )
    result = reconcile_manual_sends(database, provider)
    assert result == {"checked": 1, "reconciled": 1, "pending": 0, "ambiguous": 0}
    with database.session() as session:
        row = session.query(OutboxMessage).one()
        assert row.message_id == "<real-manual@example.com>"
        assert row.rfc_message_id == "<real-manual@example.com>"
        assert row.provider_thread_id == "real-thread"
        assert row.mailbox_uid == "42"
    assert reconcile_manual_sends(database, provider) == {
        "checked": 0,
        "reconciled": 0,
        "pending": 0,
        "ambiguous": 0,
    }
    assert provider.sent == {}


def test_reconciled_manual_thread_is_tracked_by_reply_sync(tmp_path: Path) -> None:
    database, _sender, draft, contact, company = make_fixture(tmp_path)
    record_manual_send(
        database,
        draft_id=draft.id,
        recipient=contact.email,
        sent_at=SENT_AT,
        provider_thread_id="manual-thread",
    )
    provider = FakeEmailProvider()
    provider.add_reply("manual-thread", "Thanks, please stop contacting us.", contact.email)
    result = sync_tracked_replies(database, provider, owner_email="owner@eliora.example")

    assert result["fetched"] == 1
    assert result["recorded"] == 1
    with database.session() as session:
        event = session.query(ThreadEvent).one()
        assert event.outbox_message_id is not None
        assert (
            session.get(OutboxMessage, event.outbox_message_id).provider_thread_id
            == "manual-thread"
        )
        assert session.get(Company, company.id) is not None


def test_manual_send_is_visible_in_metrics_history_draft_and_lead_detail(tmp_path: Path) -> None:
    database, _sender, draft, contact, company = make_fixture(tmp_path)
    score = LeadScore(
        id="manual-score",
        company_id=company.id,
        score_version="test",
        icp_score=80,
        intent_score=80,
        service_fit_score=80,
        evidence_quality_score=80,
        contact_quality_score=80,
        total_score=80,
        disposition="needs_review",
        explanation={},
    )
    with database.session() as session:
        session.add(score)
    record_manual_send(
        database,
        draft_id=draft.id,
        recipient=contact.email,
        sent_at=SENT_AT,
    )
    client = TestClient(create_app(Settings(), database))

    overview = client.get("/").text
    messages = client.get("/messages").text
    drafts = client.get("/drafts").text
    lead = client.get("/leads/manual-score").text
    assert "Prospect sent" in overview
    assert "Manual" in messages
    assert draft.subject in messages
    assert "Sent manually" in drafts
    assert "Last contacted" in lead
