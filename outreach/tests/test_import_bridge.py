from __future__ import annotations

import copy
import json
import socket
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

import eliora_outreach.cli as cli_module
from eliora_outreach.cli import app
from eliora_outreach.config import SenderSettings, Settings
from eliora_outreach.dashboard.app import create_app
from eliora_outreach.db import (
    AuditEvent,
    Company,
    Contact,
    Database,
    Draft,
    ImportRecord,
    LeadScore,
    OutboxMessage,
    Run,
    Source,
)
from eliora_outreach.paths import AppPaths
from eliora_outreach.research.crawler import CrawlerBudgetExceeded
from eliora_outreach.research.import_bridge import (
    ImportBridgeError,
    SourceVerification,
    import_bundle,
    reconcile_import_drafts,
    template_bundle,
    validate_bundle_file,
    verify_contact_source,
    verify_import_contacts,
)


def _real_bundle() -> dict:
    bundle = copy.deepcopy(template_bundle())
    bundle["generated_by"] = {"system": "ChatGPT", "method": "manual_web_research"}
    company = bundle["companies"][0]
    company["company_name"] = "<script>alert('escaped')</script> Health"
    company["official_domain"] = "acme-health.com"
    company["official_website"] = "https://acme-health.com"
    for evidence in company["evidence"]:
        evidence["source_url"] = evidence["source_url"].replace(
            "acme-health.example", "acme-health.com"
        )
    company["contact"]["email"] = "operations@acme-health.com"
    company["contact"]["source_url"] = company["contact"]["source_url"].replace(
        "acme-health.example", "acme-health.com"
    )
    return bundle


def _write_bundle(tmp_path: Path, bundle: dict) -> Path:
    path = tmp_path / "prospects.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")
    return path


def _test_settings() -> Settings:
    return Settings(sender=SenderSettings(postal_address="123 EliOra Way, New York, NY 10001"))


def _bundle_with_drafts(bodies: list[str], *, contacts: list[bool] | None = None) -> dict:
    contacts = contacts or [True] * len(bodies)
    bundle = copy.deepcopy(template_bundle())
    bundle["generated_by"] = {"system": "ChatGPT", "method": "manual_web_research"}
    companies: list[dict] = []
    for index, (body, include_contact) in enumerate(zip(bodies, contacts, strict=True)):
        company = copy.deepcopy(template_bundle()["companies"][0])
        domain = f"company-{index}.com"
        company["external_company_id"] = f"company-{index}"
        company["company_name"] = f"Company {index}"
        company["official_domain"] = domain
        company["official_website"] = f"https://{domain}"
        for evidence in company["evidence"]:
            evidence["source_url"] = evidence["source_url"].replace("acme-health.example", domain)
        if include_contact:
            company["contact"]["email"] = f"operations@{domain}"
            company["contact"]["source_url"] = company["contact"]["source_url"].replace(
                "acme-health.example", domain
            )
        else:
            company["contact"] = None
        company["draft"]["body"] = body
        companies.append(company)
    bundle["companies"] = companies
    return bundle


def test_schema_and_synthetic_template_validate_without_database_mutation(tmp_path: Path) -> None:
    path = _write_bundle(tmp_path, template_bundle())
    result = validate_bundle_file(path)
    assert result.bundle.schema_version == "1.0"
    assert result.preview["companies"] == 1
    assert not (tmp_path / "data").exists()
    schema_result = CliRunner().invoke(app, ["research", "schema"])
    assert schema_result.exit_code == 0
    assert '"eliora_external_research"' in schema_result.stdout


def test_strict_integrity_rules_reject_reserved_urls_missing_refs_and_state_fields(
    tmp_path: Path,
) -> None:
    reserved = template_bundle()
    reserved["generated_by"]["method"] = "manual_web_research"
    with pytest.raises(ImportBridgeError):
        validate_bundle_file(_write_bundle(tmp_path, reserved))

    missing_ref = _real_bundle()
    missing_ref["companies"][0]["observed_facts"][0]["evidence_ids"] = ["missing"]
    with pytest.raises(ImportBridgeError):
        validate_bundle_file(_write_bundle(tmp_path, missing_ref))

    forbidden = _real_bundle()
    forbidden["companies"][0]["auto_send"] = False
    with pytest.raises(ImportBridgeError):
        validate_bundle_file(_write_bundle(tmp_path, forbidden))

    invalid_service = _real_bundle()
    invalid_service["companies"][0]["service_match"]["service_key"] = "made_up_offer"
    with pytest.raises(ImportBridgeError):
        validate_bundle_file(_write_bundle(tmp_path, invalid_service))

    private_url = _real_bundle()
    private_url["companies"][0]["evidence"][0]["source_url"] = "http://127.0.0.1/private"
    with pytest.raises(ImportBridgeError):
        validate_bundle_file(_write_bundle(tmp_path, private_url))


def test_external_import_is_atomic_idempotent_and_never_queues_mail(tmp_path: Path) -> None:
    paths = AppPaths(tmp_path)
    database = Database(paths=paths)
    database.create()
    bundle_path = _write_bundle(tmp_path, _real_bundle())
    validation = validate_bundle_file(bundle_path)
    first = import_bundle(database, Settings(), validation)
    second = import_bundle(database, Settings(), validation)
    assert first["status"] == "imported"
    assert second["status"] == "already_imported"
    with database.session() as session:
        company = session.query(Company).one()
        assert company.data_origin == "external_research"
        assert company.permission_basis == "unknown"
        assert session.query(Source).count() == 1
        score = session.query(LeadScore).one()
        assert score.data_origin == "external_research"
        assert score.opportunity_fit_score is not None
        assert score.reachability_score is not None
        assert score.opportunity_fit_breakdown_json is not None
        assert score.reachability_breakdown_json is not None
        assert session.query(Draft).one().data_origin == "external_research"
        assert session.query(OutboxMessage).count() == 0
        assert session.query(ImportRecord).count() == 1
        run = session.query(Run).filter(Run.run_mode == "manual_import").one()
        assert run.research_provider == "chatgpt_manual"
        assert run.counters["prospect_messages_sent"] == 0
        assert run.counters["drafts_passing_validation"] == first["drafts_passing_validation"]
        assert session.query(Draft).one().quality_findings["passed"] is False


def test_fatal_import_rolls_back_all_rows(tmp_path: Path) -> None:
    paths = AppPaths(tmp_path)
    database = Database(paths=paths)
    database.create()
    bundle = _real_bundle()
    bundle["companies"][0]["contact"]["email"] = "operations@gmail.com"
    path = _write_bundle(tmp_path, bundle)
    with pytest.raises(ImportBridgeError):
        validate_bundle_file(path)
    with database.session() as session:
        assert session.query(Company).count() == 0
        assert session.query(ImportRecord).count() == 0

    bundle_path = _write_bundle(tmp_path, _real_bundle())
    validation = validate_bundle_file(bundle_path)
    with database.session() as session:
        session.add(
            Company(
                name="Existing synthetic fixture",
                registrable_domain="acme-health.com",
                official_website="https://acme-health.com",
                country="United States",
                vertical="healthcare",
                data_origin="synthetic",
            )
        )
    with pytest.raises(ImportBridgeError):
        import_bundle(database, Settings(), validation)
    with database.session() as session:
        assert session.query(Source).count() == 0
        assert session.query(ImportRecord).count() == 0
        assert session.query(Run).filter(Run.run_mode == "manual_import").count() == 0


def test_external_dashboard_filter_and_fields_are_escaped(tmp_path: Path) -> None:
    database = Database(paths=AppPaths(tmp_path))
    database.create()
    path = _write_bundle(tmp_path, _real_bundle())
    import_bundle(database, Settings(), validate_bundle_file(path))
    client = TestClient(create_app(Settings(), database))
    response = client.get("/leads?origin=external")
    assert response.status_code == 200
    assert "&lt;script&gt;alert(&#x27;escaped&#x27;)&lt;/script&gt;" in response.text
    assert "external_research" in response.text
    imports = client.get("/imports")
    assert imports.status_code == 200
    assert "Prospect sends" in imports.text


def test_cli_template_and_prompt_commands() -> None:
    runner = CliRunner()
    template = runner.invoke(app, ["research", "template"])
    prompt = runner.invoke(app, ["research", "prompt", "--max-companies", "3"])
    assert template.exit_code == 0
    assert "synthetic_template" in template.stdout
    assert prompt.exit_code == 0
    assert "up to 3 real US companies" in prompt.stdout


def test_draft_validation_counts_passes_and_surfaces_exact_failure(tmp_path: Path) -> None:
    valid_body = " ".join(
        ["We noticed a public operations signal and wanted to share a workflow idea for your team."]
        * 5
    )
    path = _write_bundle(
        tmp_path,
        _bundle_with_drafts([valid_body, valid_body, "Too short."], contacts=[True, False, True]),
    )
    settings = _test_settings()
    result = validate_bundle_file(path, settings=settings)
    assert result.preview["drafts"] == 3
    assert result.preview["drafts_passing_validation"] == 2
    assert result.preview["drafts_needing_review"] == 1
    assert result.preview["drafts_send_ready"] == 0
    failing = result.draft_validation_by_company["company-2"]
    assert failing.passed is False
    assert any("fewer than 80" in error for error in failing.errors)
    passing_without_contact = result.draft_validation_by_company["company-1"]
    assert passing_without_contact.passed is True
    assert passing_without_contact.contact_dependent_issues == ["contact is missing"]
    assert "permission_basis=unknown" in passing_without_contact.dispatch_blocked_reasons

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(cli_module, "load_settings", lambda paths=None: settings)
    try:
        output = CliRunner().invoke(app, ["research", "validate", str(path)])
    finally:
        monkeypatch.undo()
    assert output.exit_code == 0
    assert "drafts_passing_validation: 2" in output.stdout
    assert "Company 2: REVIEW" in output.stdout
    assert "Body has fewer than 80 pre-footer words" in output.stdout
    assert "Company 1: PASS (content/evidence)" in output.stdout


def test_source_verification_state_has_one_branch_and_sanitized_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    valid_body = " ".join(
        ["We noticed a public operations signal and wanted to share a workflow idea for your team."]
        * 5
    )
    path = _write_bundle(tmp_path, _bundle_with_drafts([valid_body]))
    unchecked = validate_bundle_file(path, settings=_test_settings())
    assert any("not checked without --verify-sources" in warning for warning in unchecked.warnings)

    monkeypatch.setattr(
        "eliora_outreach.research.import_bridge.verify_contact_source",
        lambda contact, crawler=None: SourceVerification("source_unreachable", "HTTP 403"),
    )
    checked = validate_bundle_file(path, verify_sources=True, settings=_test_settings())
    assert checked.verified_contacts == 0
    assert checked.contact_verifications["company-0"].detail == "HTTP 403"
    assert not any(
        "not checked without --verify-sources" in warning for warning in checked.warnings
    )
    assert any("source_unreachable (HTTP 403)" in warning for warning in checked.warnings)
    assert checked.draft_validation_by_company["company-0"].passed is True
    assert (
        "contact source verification is source_unreachable: HTTP 403"
        in checked.draft_validation_by_company["company-0"].contact_dependent_issues
    )
    monkeypatch.setattr(cli_module, "load_settings", lambda paths=None: _test_settings())
    output = CliRunner().invoke(app, ["research", "validate", str(path), "--verify-sources"])
    assert output.exit_code == 0
    assert "source_unreachable — HTTP 403" in output.stdout
    assert "not checked without --verify-sources" not in output.stdout


def test_verified_contact_count_and_diagnostics_are_deterministic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle_with_drafts([" ".join(["A factual workflow note for review."] * 5)])
    path = _write_bundle(tmp_path, bundle)
    monkeypatch.setattr(
        "eliora_outreach.research.import_bridge.verify_contact_source",
        lambda contact, crawler=None: SourceVerification(
            "verified", "Email was visible on the fetched public source"
        ),
    )
    result = validate_bundle_file(path, verify_sources=True, settings=_test_settings())
    assert result.verified_contacts == 1
    assert result.contact_verifications["company-0"].status == "verified"

    contact = result.bundle.companies[0].contact
    assert contact is not None

    class FailingCrawler:
        def fetch(self, url: str):
            response = httpx.Response(403, request=httpx.Request("GET", url))
            raise httpx.HTTPStatusError(
                "private detail should not leak",
                request=response.request,
                response=response,
            )

    diagnostic = verify_contact_source(contact, crawler=FailingCrawler())
    assert diagnostic.status == "source_unreachable"
    assert diagnostic.detail == "HTTP 403"

    class TimeoutCrawler:
        def fetch(self, url: str):
            raise httpx.ReadTimeout("timeout details should not leak")

    timeout = verify_contact_source(contact, crawler=TimeoutCrawler())
    assert timeout.detail == "timeout"

    class DnsCrawler:
        def fetch(self, url: str):
            raise socket.gaierror("private DNS detail should not leak")

    dns = verify_contact_source(contact, crawler=DnsCrawler())
    assert dns.detail == "DNS resolution failure"


def test_import_preview_audit_and_dashboard_use_draft_validation_state(tmp_path: Path) -> None:
    valid_body = " ".join(
        ["We noticed a public operations signal and wanted to share a workflow idea for your team."]
        * 5
    )
    settings = _test_settings()
    path = _write_bundle(tmp_path, _bundle_with_drafts([valid_body]))
    database = Database(paths=AppPaths(tmp_path))
    database.create()
    validation = validate_bundle_file(path, settings=settings)
    imported = import_bundle(database, settings, validation)
    assert imported["drafts_passing_validation"] == validation.preview["drafts_passing_validation"]
    assert imported["drafts_needing_review"] == validation.preview["drafts_needing_review"]
    with database.session() as session:
        record = session.query(ImportRecord).one()
        score_id = session.query(LeadScore).one().id
        assert record.drafts_ready == 1
        audit = (
            session.query(AuditEvent)
            .filter_by(entity_id=record.id, action="external_research_imported")
            .one()
        )
        assert audit.metadata_json["draft_validation"][0]["status"] == "pass"
    client = TestClient(create_app(settings, database))
    assert "pass" in client.get("/drafts?origin=external").text
    assert "Company 0: pass" in client.get("/imports").text
    lead_detail = client.get(f"/leads/{score_id}")
    assert "Dispatch eligibility" in lead_detail.text
    assert "send_eligibility" not in lead_detail.text
    assert "Score breakdown" in lead_detail.text
    assert "components&#x27;" not in lead_detail.text


def test_contactless_draft_persists_but_remains_send_blocked(tmp_path: Path) -> None:
    valid_body = " ".join(
        ["We noticed a public operations signal and wanted to share a workflow idea for your team."]
        * 5
    )
    settings = _test_settings()
    path = _write_bundle(tmp_path, _bundle_with_drafts([valid_body], contacts=[False]))
    database = Database(paths=AppPaths(tmp_path))
    result = import_bundle(database, settings, validate_bundle_file(path, settings=settings))
    assert result["drafts_passing_validation"] == 1
    assert result["drafts_persisted"] == 1
    assert result["drafts_send_ready"] == 0
    with database.session() as session:
        draft = session.query(Draft).one()
        assert draft.contact_id is None
        assert draft.status == "approved"
        assert session.query(OutboxMessage).count() == 0
    dashboard = TestClient(create_app(settings, database)).get("/drafts?origin=external")
    assert "Company 0" in dashboard.text
    assert "needs_contact" in dashboard.text
    assert "BLOCKED" in dashboard.text


def test_five_valid_drafts_persist_and_reconciliation_is_idempotent(tmp_path: Path) -> None:
    valid_body = " ".join(
        ["We noticed a public operations signal and wanted to share a workflow idea for your team."]
        * 5
    )
    settings = _test_settings()
    bundle = _bundle_with_drafts([valid_body] * 5, contacts=[False, True, True, False, False])
    path = _write_bundle(tmp_path, bundle)
    database = Database(paths=AppPaths(tmp_path))
    validation = validate_bundle_file(path, settings=settings)
    imported = import_bundle(database, settings, validation)
    assert imported["drafts_persisted"] == 5
    with database.session() as session:
        drafts = session.query(Draft).all()
        assert len(drafts) == 5
        assert sum(draft.contact_id is None for draft in drafts) == 3
        for draft in drafts[:2]:
            session.delete(draft)
    first = reconcile_import_drafts(database, settings, imported["import_id"], validation)
    second = reconcile_import_drafts(database, settings, imported["import_id"], validation)
    assert first["status"] == "reconciled"
    assert first["drafts_added"] == 2
    assert second["status"] == "already_reconciled"
    assert second["drafts_added"] == 0
    with database.session() as session:
        assert session.query(Draft).count() == 5
        assert session.query(ImportRecord).count() == 1
        assert session.query(OutboxMessage).count() == 0
        audit = (
            session.query(AuditEvent)
            .filter(
                AuditEvent.entity_id == imported["import_id"],
                AuditEvent.action.in_(
                    [
                        "external_research_imported",
                        "external_research_import_reconciled",
                    ]
                ),
            )
            .order_by(AuditEvent.timestamp.desc())
            .first()
        )
        assert audit is not None
        assert audit.metadata_json["drafts_persisted"] == 5
    overview = TestClient(create_app(settings, database)).get("/?origin=external")
    assert "Companies researched" in overview.text
    assert "Drafts content-ready" in overview.text
    assert "Needs contact" in overview.text
    assert "Permission blocked" in overview.text


def test_post_import_verification_updates_only_contact_metadata(
    tmp_path: Path, monkeypatch
) -> None:
    valid_body = " ".join(
        ["We noticed a public operations signal and wanted to share a workflow idea for your team."]
        * 5
    )
    settings = _test_settings()
    path = _write_bundle(tmp_path, _bundle_with_drafts([valid_body], contacts=[True]))
    database = Database(paths=AppPaths(tmp_path))
    validation = validate_bundle_file(path, settings=settings)
    imported = import_bundle(database, settings, validation)
    with database.session() as session:
        company = session.query(Company).one()
        assert company.permission_basis == "unknown"

    monkeypatch.setattr(
        "eliora_outreach.research.import_bridge.verify_contact_source",
        lambda contact, crawler=None: SourceVerification("verified", "Email was visible"),
    )
    result = verify_import_contacts(database, imported["import_id"])
    assert result["contacts_verified"] == 1
    with database.session() as session:
        contact = session.query(Contact).one()
        company = session.query(Company).one()
        assert contact.source_verification_status == "verified"
        assert contact.source_verification_checked_at is not None
        assert contact.source_verification_reason == "Email was visible"
        assert contact.appropriateness_status == "review"
        assert company.permission_basis == "unknown"
        assert session.query(OutboxMessage).count() == 0


def test_verification_budget_is_distinct_from_network_failures() -> None:
    from eliora_outreach.research.import_bridge import ContactImport

    contact = ContactImport.model_validate(
        {
            "email": "operations@company-0.com",
            "role": "Operations",
            "contact_type": "general_business_inbox",
            "source_url": "https://company-0.com/careers",
            "source_title": "Careers",
            "context": "Published business contact.",
            "retrieved_at": "2026-08-09T12:00:00-04:00",
            "permission_basis": "unknown",
        }
    )

    class BudgetCrawler:
        def fetch(self, url: str):
            raise CrawlerBudgetExceeded("request budget")

    result = verify_contact_source(contact, crawler=BudgetCrawler())
    assert result.status == "verification_budget_exhausted"
    assert "bounded" in result.detail


def test_two_contact_manual_verification_gets_bounded_budget(tmp_path: Path, monkeypatch) -> None:
    valid_body = " ".join(
        ["We noticed a public operations signal and wanted to share a workflow idea for your team."]
        * 5
    )
    path = _write_bundle(
        tmp_path,
        _bundle_with_drafts([valid_body, valid_body], contacts=[True, True]),
    )
    observed: dict[str, int] = {}

    class RecordingCrawler:
        def __init__(self, **kwargs):
            observed["max_requests"] = kwargs["max_requests"]

    monkeypatch.setattr("eliora_outreach.research.import_bridge.SafeCrawler", RecordingCrawler)
    monkeypatch.setattr(
        "eliora_outreach.research.import_bridge.verify_contact_source",
        lambda contact, crawler=None: SourceVerification("verified", "mocked"),
    )
    result = validate_bundle_file(path, verify_sources=True, settings=_test_settings())
    assert result.verified_contacts == 2
    assert observed["max_requests"] == 10
