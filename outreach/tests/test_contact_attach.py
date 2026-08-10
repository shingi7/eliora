from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

import eliora_outreach.cli as cli_module
from eliora_outreach.cli import app
from eliora_outreach.config import Settings
from eliora_outreach.contact_service import ContactAttachError, attach_contact
from eliora_outreach.dashboard.app import create_app
from eliora_outreach.db import Company, Contact, Database, Draft, LeadScore, OutboxMessage, Source
from eliora_outreach.manual_send import ManualSendError, record_manual_send
from eliora_outreach.paths import AppPaths

SOURCE_URL = "https://www.reuters.com/article/gigsafe-growth"
SENT_AT = datetime(2026, 8, 10, 15, 30, tzinfo=timezone.utc)


def _fixture(tmp_path: Path) -> tuple[Database, Company, Draft]:
    database = Database(tmp_path / "contact-attach.sqlite3")
    database.create()
    company = Company(
        id="gigsafe-company",
        name="GigSafe",
        registrable_domain="gigsafe.com",
        official_website="https://gigsafe.com",
        country="United States",
        vertical="operational_business",
        permission_basis="unknown",
        data_origin="production",
    )
    draft = Draft(
        id="f8152663-2a5d-4658-9550-2667cebf633f",
        company_id=company.id,
        contact_id=None,
        sequence_step=1,
        subject="A practical RevOps idea for GigSafe",
        plain_text_body="Hello",
        html_body="<p>Hello</p>",
        source_facts_used=[],
        model="test",
        prompt_version="test",
        content_hash="gigsafe-content",
        quality_findings={"passed": True},
        status="approved",
        data_origin="production",
    )
    score = LeadScore(
        id="gigsafe-score",
        company_id=company.id,
        score_version="legacy",
        icp_score=1,
        intent_score=1,
        service_fit_score=1,
        evidence_quality_score=1,
        contact_quality_score=0,
        penalties=[],
        total_score=4,
        disposition="needs_contact",
        explanation={},
        opportunity_fit_score=73,
        opportunity_fit_grade="B",
        opportunity_fit_version="fit-v1",
        opportunity_fit_breakdown_json={"preserved": True},
        reachability_score=0,
        reachability_grade="D",
        reachability_version="reach-v1",
        reachability_breakdown_json={"preserved": True},
        priority="preserved-priority",
    )
    with database.session() as session:
        session.add_all([company, draft, score])
    return database, company, draft


def _add(database: Database, company: Company, draft: Draft, **overrides: str):
    values = {
        "company_id": company.id,
        "email": "ian@gigsafe.com",
        "display_name": "Ian Lazarus",
        "title": "VP of GTM",
        "source_url": SOURCE_URL,
        "source_type": "reputable_news",
        "extraction_method": "visible_text",
        "draft_id": draft.id,
    }
    values.update(overrides)
    return attach_contact(database, **values)


def test_valid_public_contact_attaches_draft_recomputes_reachability_and_preserves_gates(
    tmp_path: Path,
) -> None:
    database, company, draft = _fixture(tmp_path)

    result = _add(database, company, draft)

    assert result.status == "added"
    assert result.draft_id == draft.id
    assert result.source_verification_status == "not_checked"
    with database.session() as session:
        stored_company = session.get(Company, company.id)
        stored_contact = session.get(Contact, result.contact_id)
        stored_draft = session.get(Draft, draft.id)
        score = session.get(LeadScore, "gigsafe-score")
        source = session.get(Source, stored_contact.source_id)
        assert stored_company.permission_basis == "unknown"
        assert stored_company.data_origin == "production"
        assert stored_contact.email == "ian@gigsafe.com"
        assert stored_contact.display_name == "Ian Lazarus"
        assert stored_contact.title == "VP of GTM"
        assert stored_contact.role_inbox_category == "relevant_role"
        assert stored_contact.official_domain is True
        assert stored_contact.no_guessed_address is True
        assert stored_contact.mx_valid is None
        assert stored_contact.source_verification_status == "not_checked"
        assert stored_contact.appropriateness_status == "review"
        assert stored_draft.contact_id == stored_contact.id
        assert source.source_type == "reputable_news"
        assert source.url == SOURCE_URL
        assert score.opportunity_fit_score == 73
        assert score.opportunity_fit_breakdown_json == {"preserved": True}
        assert score.priority == "preserved-priority"
        assert score.reachability_score == result.reachability_after
        assert score.reachability_score > 0
        assert session.query(OutboxMessage).count() == 0
    lead_detail = TestClient(create_app(Settings(), database)).get("/leads/gigsafe-score").text
    assert "Ian Lazarus" in lead_detail
    assert "VP of GTM" in lead_detail
    assert "ian@gigsafe.com" in lead_detail
    assert SOURCE_URL in lead_detail
    assert "not_checked" in lead_detail
    assert f"Reachability {result.reachability_after}" in lead_detail


def test_duplicate_same_company_email_and_source_is_idempotent(tmp_path: Path) -> None:
    database, company, draft = _fixture(tmp_path)

    first = _add(database, company, draft)
    second = _add(database, company, draft)

    assert first.status == "added"
    assert second.status == "already_exists"
    with database.session() as session:
        assert session.query(Contact).count() == 1
        assert session.query(Source).count() == 1
        assert session.get(Draft, draft.id).contact_id == first.contact_id


def test_missing_or_invalid_provenance_and_contact_values_are_rejected(tmp_path: Path) -> None:
    database, company, draft = _fixture(tmp_path)
    common = {
        "company_id": company.id,
        "display_name": "Ian Lazarus",
        "title": "VP of GTM",
        "source_type": "reputable_news",
        "extraction_method": "visible_text",
        "draft_id": draft.id,
    }
    cases = [
        {"email": "ian@gigsafe.com", "source_url": ""},
        {"email": "ian@gmail.com", "source_url": SOURCE_URL},
        {"email": "ian@other.com", "source_url": SOURCE_URL},
        {"email": "ian", "source_url": SOURCE_URL},
        {"email": "support@gigsafe.com", "source_url": SOURCE_URL},
    ]
    for case in cases:
        with pytest.raises(ContactAttachError):
            attach_contact(database, **common, **case)
    with database.session() as session:
        assert session.query(Contact).count() == 0
        assert session.query(OutboxMessage).count() == 0


def test_conflicting_provenance_or_different_draft_contact_is_not_overwritten(
    tmp_path: Path,
) -> None:
    database, company, draft = _fixture(tmp_path)
    first = _add(database, company, draft)

    with pytest.raises(ContactAttachError, match="different provenance"):
        _add(database, company, draft, source_url="https://www.nytimes.com/2026/gigsafe")
    with pytest.raises(ContactAttachError, match="different persisted contact"):
        _add(
            database,
            company,
            draft,
            email="alex@gigsafe.com",
            display_name="Alex Example",
            title="Revenue Operations",
        )
    with database.session() as session:
        contacts = session.query(Contact).all()
        assert [contact.email for contact in contacts] == ["ian@gigsafe.com"]
        assert session.get(Draft, draft.id).contact_id == first.contact_id


def test_attached_contact_can_be_recorded_but_arbitrary_manual_recipient_stays_blocked(
    tmp_path: Path,
) -> None:
    database, company, draft = _fixture(tmp_path)
    _add(database, company, draft)

    result = record_manual_send(
        database,
        draft_id=draft.id,
        recipient="ian@gigsafe.com",
        subject="A practical RevOps idea for GigSafe",
        sent_at=SENT_AT,
    )
    assert result.status == "recorded"
    with pytest.raises(ManualSendError, match="must match the persisted contact"):
        record_manual_send(
            database,
            draft_id=draft.id,
            recipient="other@gigsafe.com",
            subject="A practical RevOps idea for GigSafe",
            sent_at=SENT_AT,
        )
    with database.session() as session:
        assert session.query(OutboxMessage).count() == 1
        assert session.query(OutboxMessage).one().data_origin == "manual_send"


def test_cli_add_contact_is_local_record_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database, company, draft = _fixture(tmp_path)
    monkeypatch.setattr(cli_module, "_paths_db", lambda: (AppPaths(tmp_path / "paths"), database))

    result = CliRunner().invoke(
        app,
        [
            "lead",
            "add-contact",
            company.id,
            "--email",
            "ian@gigsafe.com",
            "--name",
            "Ian Lazarus",
            "--title",
            "VP of GTM",
            "--source-url",
            SOURCE_URL,
            "--source-type",
            "reputable_news",
            "--draft-id",
            draft.id,
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "outbox_rows_created: 0" in result.stdout
    assert "verification=not_checked" in result.stdout
    with database.session() as session:
        assert session.query(OutboxMessage).count() == 0
