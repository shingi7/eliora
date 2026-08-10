from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from eliora_outreach.commercial_scoring import CommercialLeadInputs, score_commercial_lead
from eliora_outreach.db import (
    Company,
    Database,
    LeadScore,
    OutboxMessage,
    PainHypothesis,
    SchemaVersion,
    Signal,
    Source,
)
from eliora_outreach.score_service import recompute_scores


def _inputs(
    *,
    signal_text: str = "The company announced a weekly pipeline and forecast reporting workflow after expansion.",
    signal_type: str = "pipeline_and_revops",
    service: str = "Pipeline and RevOps Workflow",
    freshness_days: int | None = 10,
    contact: object | None = None,
    vertical: str = "operational_business",
    employee_band: str = "50-99",
) -> CommercialLeadInputs:
    source = SimpleNamespace(
        url="https://acme.com/news/expansion",
        source_type="official_press",
        retrieved_at=datetime.now(timezone.utc),
        publication_date=None,
    )
    signal = SimpleNamespace(
        signal_type=signal_type,
        observed_signal=signal_text,
        freshness_days=freshness_days,
        confidence=0.9,
    )
    pain = SimpleNamespace(
        hypothesis="The change may create recurring pipeline reporting and forecast handoffs.",
        confidence=0.9,
        service_mapping=service,
    )
    return CommercialLeadInputs(
        company_name="Acme",
        company_domain="acme.com",
        vertical=vertical,
        employee_band=employee_band,
        sources=(source,),
        signals=(signal,),
        pain_hypotheses=(pain,),
        contact=contact,
        research_confidence=0.9,
    )


def _contact(
    *,
    email: str = "revops@acme.com",
    title: str = "Revenue Operations",
    category: str = "relevant_role",
    verification: str = "verified",
) -> SimpleNamespace:
    return SimpleNamespace(
        email=email,
        title=title,
        role=title,
        role_inbox_category=category,
        official_domain=True,
        source_url="https://acme.com/team",
        no_guessed_address=True,
        source_verification_status=verification,
        appropriateness_status="eligible",
    )


def test_fit_is_independent_of_contact_and_dispatch_inputs() -> None:
    no_contact = score_commercial_lead(_inputs(contact=None))
    verified = score_commercial_lead(_inputs(contact=_contact()))
    permission_context = score_commercial_lead(
        replace(
            _inputs(contact=None), permission_basis="owner_approved", provider_policy_eligible=True
        )
    )
    assert no_contact.opportunity_fit_score == verified.opportunity_fit_score
    assert no_contact.opportunity_fit_breakdown == verified.opportunity_fit_breakdown
    assert permission_context.opportunity_fit_score == no_contact.opportunity_fit_score
    assert permission_context.reachability_score == no_contact.reachability_score
    assert no_contact.reachability_score < verified.reachability_score
    assert no_contact.reachability_grade == "D"


def test_bounded_project_beats_vague_enterprise_transformation() -> None:
    bounded = score_commercial_lead(_inputs())
    broad = score_commercial_lead(
        _inputs(
            signal_text="The company is pursuing an organization-wide enterprise platform replacement and broad architecture transformation.",
            signal_type="data_silos_and_integration",
            service="Enterprise platform replacement",
        )
    )
    assert (
        bounded.opportunity_fit_breakdown["small_project_suitability"]["points"]
        > broad.opportunity_fit_breakdown["small_project_suitability"]["points"]
    )
    assert bounded.opportunity_fit_score > broad.opportunity_fit_score
    assert broad.project_scope_band == "enterprise_or_unclear"


def test_fresh_trigger_and_direct_service_match_are_rewarded() -> None:
    fresh = score_commercial_lead(_inputs(freshness_days=10))
    stale = score_commercial_lead(_inputs(freshness_days=240))
    weak = score_commercial_lead(
        _inputs(service="Unclear advisory opportunity", signal_type="manual_reporting")
    )
    assert (
        fresh.opportunity_fit_breakdown["trigger_strength"]["points"]
        > stale.opportunity_fit_breakdown["trigger_strength"]["points"]
    )
    assert (
        fresh.opportunity_fit_breakdown["service_match"]["points"]
        > weak.opportunity_fit_breakdown["service_match"]["points"]
    )


def test_reachability_rewards_verified_relevant_channel_and_rejects_inappropriate_mailbox() -> None:
    verified = score_commercial_lead(_inputs(contact=_contact()))
    unverified = score_commercial_lead(_inputs(contact=_contact(verification="unreachable")))
    inappropriate = score_commercial_lead(
        _inputs(
            contact=_contact(email="support@acme.com", title="Customer Support", category="support")
        )
    )
    general = score_commercial_lead(
        _inputs(contact=_contact(email="hello@acme.com", title="", category="general_business"))
    )
    assert verified.reachability_score > unverified.reachability_score
    assert inappropriate.reachability_breakdown["appropriate_business_contact"]["points"] == 0
    assert general.reachability_score < verified.reachability_score
    assert verified.primary_buyer_persona == "revenue_operations"


def test_recompute_preserves_legacy_score_and_creates_no_outbox_rows(tmp_path: Path) -> None:
    database = Database(path=tmp_path / "scores.sqlite3")
    database.create()
    with database.session() as session:
        assert session.get(SchemaVersion, 7) is not None
    with database.engine.connect() as connection:
        columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(lead_scores)")}
    assert {
        "opportunity_fit_score",
        "opportunity_fit_grade",
        "opportunity_fit_breakdown_json",
        "reachability_score",
        "reachability_grade",
        "reachability_breakdown_json",
        "primary_buyer_persona",
        "primary_project_type",
        "project_scope_band",
        "procurement_friction_band",
    } <= columns
    with database.session() as session:
        company = Company(
            id="score-company",
            name="Acme",
            registrable_domain="acme.com",
            official_website="https://acme.com",
            country="United States",
            vertical="operational_business",
            employee_band="50-99",
            data_origin="external_research",
        )
        source = Source(
            id="score-source",
            company_id=company.id,
            url="https://acme.com/news",
            canonical_url_hash="source-hash",
            source_type="official_press",
            title="Expansion",
            publisher="acme.com",
            excerpt="Acme announced a weekly pipeline reporting workflow.",
            source_quality=1.0,
            data_origin="external_research",
        )
        signal = Signal(
            id="score-signal",
            company_id=company.id,
            source_id=source.id,
            signal_type="pipeline_and_revops",
            observed_signal="Acme announced a weekly pipeline reporting workflow.",
            freshness_days=10,
            confidence=0.9,
            data_origin="external_research",
        )
        pain = PainHypothesis(
            id="score-pain",
            company_id=company.id,
            category="pipeline_and_revops",
            hypothesis="The change may create recurring pipeline reporting work.",
            confidence=0.9,
            service_mapping="Pipeline and RevOps Workflow",
            supporting_signal_ids=[signal.id],
            data_origin="external_research",
        )
        legacy = LeadScore(
            id="score-row",
            company_id=company.id,
            score_version="legacy",
            icp_score=8,
            intent_score=10,
            service_fit_score=12,
            evidence_quality_score=7,
            contact_quality_score=0,
            penalties=["contact_provenance"],
            total_score=37,
            disposition="needs_contact",
            explanation={"legacy": "unchanged"},
            data_origin="external_research",
        )
        session.add_all([company, source, signal, pain, legacy])
    first = recompute_scores(database, origin="external")
    second = recompute_scores(database, origin="external")
    assert first["recomputed"] == second["recomputed"] == 1
    with database.session() as session:
        row = session.get(LeadScore, "score-row")
        assert row is not None
        assert row.total_score == 37
        assert row.explanation == {"legacy": "unchanged"}
        assert row.opportunity_fit_score is not None
        assert row.reachability_score is not None
        assert session.query(OutboxMessage).count() == 0
