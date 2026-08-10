from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml
from sqlalchemy import text
from sqlalchemy.schema import CreateTable

from eliora_outreach.config import load_settings
from eliora_outreach.db import (
    Company,
    Contact,
    Database,
    Draft,
    OutboxMessage,
    SchemaVersion,
    Suppression,
    ThreadEvent,
)
from eliora_outreach.email.outbox import create_outbox, lease_pending, send_leased
from eliora_outreach.email.sync import sync_tracked_replies
from eliora_outreach.manual_send import record_manual_send
from eliora_outreach.paths import AppPaths
from eliora_outreach.pipeline import dispatch_pending
from eliora_outreach.providers.base import MailTransportError
from eliora_outreach.providers.fake import FakeEmailProvider


def test_old_sqlite_schema_gets_provider_neutral_columns(tmp_path: Path) -> None:
    path = tmp_path / "old.sqlite3"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE schema_versions (version INTEGER PRIMARY KEY, applied_at DATETIME);
        CREATE TABLE companies (
            id VARCHAR(36) PRIMARY KEY, name VARCHAR(255), registrable_domain VARCHAR(255),
            official_website VARCHAR(500), vertical VARCHAR(80)
        );
        CREATE TABLE outbox_messages (
            id VARCHAR(36) PRIMARY KEY, draft_id VARCHAR(36), idempotency_key VARCHAR(255),
            message_id VARCHAR(500), scheduled_for DATETIME, state VARCHAR(30), attempt_count INTEGER,
            lease_owner VARCHAR(255), lease_expiry DATETIME, gmail_message_id VARCHAR(255),
            gmail_thread_id VARCHAR(255), api_request_id VARCHAR(255), sent_at DATETIME,
            last_error_category VARCHAR(80)
        );
        CREATE TABLE thread_events (
            id VARCHAR(36) PRIMARY KEY, outbox_message_id VARCHAR(36), gmail_message_id VARCHAR(255),
            direction VARCHAR(20), timestamp DATETIME, event_class VARCHAR(40)
        );
        INSERT INTO outbox_messages VALUES
            ('outbox-1', 'draft-1', 'key-1', '<old@example.com>', '2026-01-01', 'sent', 1,
             NULL, NULL, 'g-1', 't-1', NULL, NULL, NULL);
        INSERT INTO thread_events VALUES
            ('event-1', 'outbox-1', 'g-1', 'inbound', '2026-01-01', 'question');
        """
    )
    connection.commit()
    connection.close()

    database = Database(path=path)
    database.create()
    with database.engine.connect() as connection:
        columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(outbox_messages)")
        }
        assert {
            "rfc_message_id",
            "provider_message_id",
            "provider_thread_id",
            "mailbox_uid",
            "mail_provider",
            "manual_subject",
        } <= columns
        message_id_column = next(
            row
            for row in connection.exec_driver_sql("PRAGMA table_info(outbox_messages)")
            if row[1] == "message_id"
        )
        assert message_id_column[3] == 0
    with database.session() as session:
        row = session.get(OutboxMessage, "outbox-1")
        assert row is not None
        assert row.rfc_message_id == "<old@example.com>"
        assert row.mail_provider == "legacy_gmail"


def test_legacy_required_draft_contact_migrates_without_losing_rows(tmp_path: Path) -> None:
    path = tmp_path / "draft-migration.sqlite3"
    database = Database(path=path)
    database.create()
    with database.session() as session:
        session.add(
            Draft(
                id="legacy-draft",
                company_id="legacy-company",
                contact_id="legacy-contact",
                sequence_step=1,
                subject="Legacy draft",
                plain_text_body="Body",
                html_body="<p>Body</p>",
                source_facts_used=[],
                model="test",
                prompt_version="test",
                content_hash="legacy-content",
                quality_findings={},
                status="approved",
                data_origin="external_research",
            )
        )
    ddl = str(CreateTable(Draft.__table__).compile(database.engine))
    legacy_ddl = ddl.replace("contact_id VARCHAR(36),", "contact_id VARCHAR(36) NOT NULL,")
    with database.engine.begin() as connection:
        connection.execute(text("ALTER TABLE drafts RENAME TO drafts_nullable"))
        connection.execute(text(legacy_ddl))
        connection.execute(text("INSERT INTO drafts SELECT * FROM drafts_nullable"))
        connection.execute(text("DROP TABLE drafts_nullable"))
    Database(path=path).create()
    with database.engine.connect() as connection:
        contact_column = next(
            row
            for row in connection.execute(text("PRAGMA table_info(drafts)"))
            if row[1] == "contact_id"
        )
        assert contact_column[3] == 0
    with database.session() as session:
        row = session.get(Draft, "legacy-draft")
        assert row is not None
        assert row.contact_id == "legacy-contact"


def test_v6_database_migrates_to_current_schema_without_losing_manual_send(tmp_path: Path) -> None:
    path = tmp_path / "v6-manual-send.sqlite3"
    database = Database(path=path)
    database.create()
    with database.session() as session:
        company = Company(
            id="v6-company",
            name="V6 Customer",
            registrable_domain="v6-customer.com",
            official_website="https://v6-customer.com",
            country="United States",
            vertical="operational_business",
            permission_basis="existing_relationship",
        )
        contact = Contact(
            id="v6-contact",
            company_id=company.id,
            email="hello@v6-customer.com",
            source_id="v6-source",
            source_url="https://v6-customer.com/contact",
            extraction_method="mailto",
            official_domain=True,
            syntactic_valid=True,
            appropriateness_status="eligible",
        )
        draft = Draft(
            id="v6-draft",
            company_id=company.id,
            contact_id=contact.id,
            sequence_step=1,
            subject="Draft subject",
            plain_text_body="Hello",
            html_body="<p>Hello</p>",
            source_facts_used=[],
            model="test",
            prompt_version="test",
            content_hash="v6-content",
            status="approved",
        )
        session.add_all([company, contact, draft])
    record_manual_send(
        database,
        draft_id="v6-draft",
        recipient="hello@v6-customer.com",
        subject="Actual V6 subject",
        sent_at=datetime(2026, 8, 10, 15, 30, tzinfo=timezone.utc),
    )
    with database.engine.begin() as connection:
        connection.execute(text("DELETE FROM schema_versions WHERE version > 6"))

    Database(path=path).create()
    Database(path=path).create()
    from eliora_outreach.cli import _schema_migration_status

    with database.session() as session:
        schema_ok, detail = _schema_migration_status(session)
        row = (
            session.query(OutboxMessage).filter(OutboxMessage.draft_id == "v6-draft").one_or_none()
        )
        manual_rows = (
            session.query(OutboxMessage).filter(OutboxMessage.data_origin == "manual_send").all()
        )
        assert schema_ok is True
        assert detail == "version 8"
        assert row is not None
        assert row.idempotency_key.startswith("company:v6-company:")
        assert len(manual_rows) == 1
        assert manual_rows[0].manual_subject == "Actual V6 subject"
        assert manual_rows[0].state == "sent"
        assert session.query(SchemaVersion).count() == 8
        assert session.query(SchemaVersion).filter(SchemaVersion.version == 8).count() == 1


def test_gmail_config_migrates_without_converting_oauth_path(tmp_path: Path) -> None:
    config = tmp_path / "config.yml"
    config.write_text(
        yaml.safe_dump(
            {
                "config_version": 1,
                "sender": {"email": "owner@eliora.example"},
                "providers": {
                    "gmail_reply_sync": False,
                    "gmail_credentials_path": "/private/client_secret.json",
                },
            }
        ),
        encoding="utf-8",
    )
    settings = load_settings(path=config, paths=AppPaths(tmp_path / "state"))
    assert settings.providers.mail_provider == "namecheap_private_email"
    assert settings.providers.mail_reply_sync is False
    assert settings.providers.gmail_credentials_path is None
    assert "no credential was converted" in (settings.config_migration_notice or "")
    assert config.with_name("config.yml.gmail-backup.yml").exists()
    assert "gmail_credentials_path" not in config.read_text(encoding="utf-8")


def test_namecheap_permission_gate_blocks_unknown_basis_then_sends_allowed_basis(
    tmp_path: Path,
) -> None:
    database = Database(path=tmp_path / "outreach.sqlite3")
    database.create()
    from eliora_outreach.config import SenderSettings, Settings

    sender = SenderSettings(
        email="owner@eliora.example",
        reply_to="owner@eliora.example",
        owner_bcc="owner@eliora.example",
        postal_address="100 Demo Way, New York, NY",
    )
    settings = Settings(
        sender=sender,
        providers={"permission_policy_acknowledged": True},
        live={"enabled": True},
    )
    with database.session() as session:
        company = Company(
            id="company-1",
            name="Customer",
            registrable_domain="customer.example",
            official_website="https://customer.example",
            country="United States",
            vertical="healthcare",
        )
        contact = Contact(
            id="contact-1",
            company_id=company.id,
            email="prospect@customer.example",
            source_id="source-1",
            source_url="https://customer.example/team",
            extraction_method="mailto",
            official_domain=True,
            syntactic_valid=True,
            appropriateness_status="eligible",
        )
        draft = Draft(
            id="draft-1",
            company_id=company.id,
            contact_id=contact.id,
            sequence_step=1,
            subject="Test",
            plain_text_body="Hello",
            html_body="<p>Hello</p>",
            source_facts_used=[],
            model="test",
            prompt_version="test",
            content_hash="content-1",
            status="approved",
        )
        session.add_all([company, contact, draft])
    outbox = create_outbox(
        database,
        draft,
        scheduled_for=datetime(2026, 8, 10, 15, 0, tzinfo=timezone.utc),
        sender=sender,
        recipient=contact.email,
    )
    fake = FakeEmailProvider()
    blocked = dispatch_pending(
        database,
        settings,
        provider=fake,
        now=datetime(2026, 8, 10, 15, 0, tzinfo=timezone.utc),
    )
    assert blocked["blocked"] == "permission_basis_required"
    with database.session() as session:
        assert session.get(OutboxMessage, outbox.id).state == "pending"
        session.get(Company, company.id).permission_basis = "existing_relationship"
    sent = dispatch_pending(
        database,
        settings,
        provider=fake,
        now=datetime(2026, 8, 10, 15, 0, tzinfo=timezone.utc),
    )
    assert sent["sent"] == 1
    assert fake.sent
    value = next(iter(fake.sent.values()))
    assert value["envelope_recipients"] == ["prospect@customer.example", "owner@eliora.example"]
    assert b"Bcc:" not in value["raw"]


def test_reply_sync_records_opt_out_suppression_and_cancels_sequence(tmp_path: Path) -> None:
    database = Database(path=tmp_path / "sync.sqlite3")
    database.create()
    from eliora_outreach.config import SenderSettings

    sender = SenderSettings(
        email="owner@eliora.example",
        reply_to="owner@eliora.example",
        owner_bcc="owner@eliora.example",
        postal_address="100 Demo Way, New York, NY",
    )
    with database.session() as session:
        company = Company(
            id="sync-company",
            name="Customer",
            registrable_domain="customer.example",
            official_website="https://customer.example",
            country="United States",
            vertical="healthcare",
        )
        contact = Contact(
            id="sync-contact",
            company_id=company.id,
            email="prospect@customer.example",
            source_id="source-1",
            source_url="https://customer.example/team",
            extraction_method="mailto",
            official_domain=True,
            syntactic_valid=True,
            appropriateness_status="eligible",
        )
        draft = Draft(
            id="sync-draft",
            company_id=company.id,
            contact_id=contact.id,
            sequence_step=1,
            subject="Test",
            plain_text_body="Hello",
            html_body="<p>Hello</p>",
            source_facts_used=[],
            model="test",
            prompt_version="test",
            content_hash="sync-content",
            status="approved",
        )
        outbox = OutboxMessage(
            id="sync-outbox",
            draft_id=draft.id,
            idempotency_key=f"company:{company.id}:contact:{contact.id}:step:1:content:sync-content",
            message_id="<sync@eliora.example>",
            rfc_message_id="<sync@eliora.example>",
            provider_thread_id="thread-sync",
            scheduled_for=datetime.now(timezone.utc),
            state="sent",
        )
        followup = OutboxMessage(
            id="sync-followup",
            draft_id=draft.id,
            idempotency_key=f"company:{company.id}:contact:{contact.id}:step:2:content:sync-content",
            message_id="<sync-followup@eliora.example>",
            rfc_message_id="<sync-followup@eliora.example>",
            scheduled_for=datetime.now(timezone.utc),
            state="pending",
        )
        session.add_all([company, contact, draft, outbox, followup])

    fake = FakeEmailProvider()
    fake.events.append(
        {
            "thread_id": "thread-sync",
            "provider_message_id": "reply-sync",
            "headers": {
                "subject": "Re: Test",
                "from": "prospect@customer.example",
                "message-id": "<reply-sync@customer.example>",
            },
            "body": "No thanks, please remove me.",
        }
    )
    result = sync_tracked_replies(database, fake, owner_email=sender.email)
    assert result == {"fetched": 1, "recorded": 1, "suppressed": 1, "cancelled": 1}
    with database.session() as session:
        assert (
            session.query(ThreadEvent)
            .filter(ThreadEvent.provider_message_id == "reply-sync")
            .count()
            == 1
        )
        assert session.query(Suppression).count() == 1
        assert session.get(OutboxMessage, "sync-outbox").state == "sent"
        assert session.get(OutboxMessage, "sync-followup").state == "cancelled"


def test_uncertain_transport_state_is_committed_before_error_surfaces(tmp_path: Path) -> None:
    database = Database(path=tmp_path / "uncertain.sqlite3")
    database.create()
    from eliora_outreach.config import SenderSettings

    sender = SenderSettings(
        email="owner@eliora.example",
        reply_to="owner@eliora.example",
        owner_bcc="owner@eliora.example",
        postal_address="100 Demo Way, New York, NY",
    )
    with database.session() as session:
        company = Company(
            id="uncertain-company",
            name="Customer",
            registrable_domain="customer.example",
            official_website="https://customer.example",
            country="United States",
            vertical="healthcare",
            permission_basis="existing_relationship",
        )
        contact = Contact(
            id="uncertain-contact",
            company_id=company.id,
            email="prospect@customer.example",
            source_id="source-1",
            source_url="https://customer.example/team",
            extraction_method="mailto",
            official_domain=True,
            syntactic_valid=True,
            appropriateness_status="eligible",
        )
        draft = Draft(
            id="uncertain-draft",
            company_id=company.id,
            contact_id=contact.id,
            sequence_step=1,
            subject="Test",
            plain_text_body="Hello",
            html_body="<p>Hello</p>",
            source_facts_used=[],
            model="test",
            prompt_version="test",
            content_hash="uncertain-content",
            status="approved",
        )
        session.add_all([company, contact, draft])
    outbox = create_outbox(
        database,
        draft,
        scheduled_for=datetime.now(timezone.utc),
        sender=sender,
        recipient="prospect@customer.example",
    )
    leased = lease_pending(database, now=datetime.now(timezone.utc))
    assert leased is not None

    class UncertainProvider:
        def send(
            self,
            raw_message: bytes,
            *,
            idempotency_key: str,
            envelope_recipients: list[str],
        ):
            raise MailTransportError(
                "connection lost after DATA",
                category="uncertain_delivery",
                transient=True,
                uncertain=True,
            )

        def find_by_message_id(self, message_id: str):
            return None

    with pytest.raises(MailTransportError):
        send_leased(
            database,
            UncertainProvider(),
            leased.id,
            sender=sender,
            recipient="prospect@customer.example",
        )
    with database.session() as session:
        row = session.get(OutboxMessage, outbox.id)
        assert row.state == "uncertain"
        assert row.last_error_category == "uncertain_delivery"
