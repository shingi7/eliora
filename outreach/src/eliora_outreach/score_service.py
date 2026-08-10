from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

from sqlalchemy import select

from .commercial_scoring import commercial_inputs_from_records, score_commercial_lead
from .db import (
    AuditEvent,
    Company,
    Contact,
    Database,
    LeadScore,
    PainHypothesis,
    Signal,
    Source,
)


def commercial_order_key(company: Company, row: LeadScore) -> tuple[int, int, int, str, str]:
    """Stable default order: fit, reachability, freshness, then company identity."""
    explanation = row.explanation if isinstance(row.explanation, dict) else {}
    fresh_signals = explanation.get("fresh_signal_count", 0)
    return (
        -(row.opportunity_fit_score if row.opportunity_fit_score is not None else -1),
        -(row.reachability_score if row.reachability_score is not None else -1),
        -(int(fresh_signals) if isinstance(fresh_signals, (int, float)) else 0),
        company.name.lower(),
        company.id,
    )


def apply_commercial_score(row: LeadScore, result: Any) -> None:
    """Copy the auditable commercial result without touching legacy score columns."""
    row.opportunity_fit_score = result.opportunity_fit_score
    row.opportunity_fit_grade = result.opportunity_fit_grade
    row.opportunity_fit_version = result.opportunity_fit_version
    row.opportunity_fit_breakdown_json = result.opportunity_fit_breakdown
    row.reachability_score = result.reachability_score
    row.reachability_grade = result.reachability_grade
    row.reachability_version = result.reachability_version
    row.reachability_breakdown_json = result.reachability_breakdown
    row.primary_buyer_persona = result.primary_buyer_persona
    row.primary_project_type = result.primary_project_type
    row.project_scope_band = result.project_scope_band
    row.procurement_friction_band = result.procurement_friction_band
    row.priority = result.priority


def commercial_score_for_records(
    company: Company,
    sources: list[Any],
    signals: list[Any],
    pains: list[Any],
    contact: Contact | None,
    *,
    today: date | None = None,
):
    confidence_values = [float(signal.confidence or 0) for signal in signals] + [
        float(pain.confidence or 0) for pain in pains
    ]
    inputs = commercial_inputs_from_records(
        company,
        sources,
        signals,
        pains,
        contact,
        research_confidence=max(confidence_values, default=0.0),
    )
    return score_commercial_lead(inputs, today=today)


def recompute_scores(
    database: Database,
    *,
    origin: str = "all",
    today: date | None = None,
) -> dict[str, Any]:
    """Recompute only commercial scores for existing companies.

    This updates the latest score snapshot per company and never creates drafts,
    outbox rows, queue state, or transport activity.
    """
    origin_map = {"external": "external_research", "production": "production"}
    if origin not in {"all", *origin_map}:
        raise ValueError("origin must be all, production, or external")
    database.create()
    updated = 0
    grades: Counter[str] = Counter()
    reach_grades: Counter[str] = Counter()
    before_after: list[dict[str, Any]] = []
    with database.session() as session:
        company_query = session.query(Company)
        if origin in origin_map:
            company_query = company_query.filter(Company.data_origin == origin_map[origin])
        companies = company_query.order_by(Company.name.asc(), Company.id.asc()).all()
        for company in companies:
            score_query = (
                session.query(LeadScore)
                .filter(LeadScore.company_id == company.id)
                .order_by(LeadScore.scored_at.desc(), LeadScore.id.desc())
            )
            if origin in origin_map:
                score_query = score_query.filter(LeadScore.data_origin == origin_map[origin])
            row = score_query.first()
            if row is None:
                continue
            sources = session.query(Source).filter(Source.company_id == company.id).all()
            signals = session.query(Signal).filter(Signal.company_id == company.id).all()
            pains = (
                session.query(PainHypothesis).filter(PainHypothesis.company_id == company.id).all()
            )
            contact = (
                session.query(Contact)
                .filter(Contact.company_id == company.id)
                .order_by(Contact.first_seen_at.asc(), Contact.id.asc())
                .first()
            )
            result = commercial_score_for_records(
                company, sources, signals, pains, contact, today=today
            )
            before_after.append(
                {
                    "company": company.name,
                    "legacy_score": row.total_score,
                    "opportunity_fit_before": row.opportunity_fit_score,
                    "opportunity_fit_after": result.opportunity_fit_score,
                    "reachability_after": result.reachability_score,
                }
            )
            apply_commercial_score(row, result)
            grades[result.opportunity_fit_grade] += 1
            reach_grades[result.reachability_grade] += 1
            updated += 1
        session.add(
            AuditEvent(
                actor="owner",
                action="commercial_scores_recomputed",
                entity_type="score_batch",
                entity_id=None,
                metadata_json={
                    "origin": origin,
                    "updated": updated,
                    "opportunity_fit_grades": dict(grades),
                    "reachability_grades": dict(reach_grades),
                    "outbox_rows_created": 0,
                    "prospect_messages_sent": 0,
                },
            )
        )
    return {
        "recomputed": updated,
        "opportunity_fit_grades": dict(grades),
        "reachability_grades": dict(reach_grades),
        "before_after": before_after,
        "outbox_rows_created": 0,
        "prospect_messages_sent": 0,
    }


def recompute_reachability_for_company(
    database: Database,
    company_id: str,
    *,
    today: date | None = None,
) -> dict[str, Any]:
    """Refresh one company's reachability fields without changing fit fields.

    Contact attachment is a reachability event.  The commercial scorer is still
    the single source of truth, but only its reachability result is persisted by
    this narrow path so an owner contact update cannot silently rewrite
    Opportunity Fit or permission state.
    """
    database.create()
    with database.session() as session:
        company = session.get(Company, company_id)
        if company is None:
            raise ValueError("Company not found")
        row = session.scalar(
            select(LeadScore)
            .where(LeadScore.company_id == company.id)
            .order_by(LeadScore.scored_at.desc(), LeadScore.id.desc())
        )
        if row is None:
            return {
                "updated": False,
                "company_id": company.id,
                "reachability_before": None,
                "reachability_after": None,
                "reachability_grade": None,
            }
        sources = session.query(Source).filter(Source.company_id == company.id).all()
        signals = session.query(Signal).filter(Signal.company_id == company.id).all()
        pains = session.query(PainHypothesis).filter(PainHypothesis.company_id == company.id).all()
        contact = session.scalar(
            select(Contact)
            .where(Contact.company_id == company.id)
            .order_by(Contact.first_seen_at.asc(), Contact.id.asc())
        )
        result = commercial_score_for_records(
            company, sources, signals, pains, contact, today=today
        )
        before = row.reachability_score
        row.reachability_score = result.reachability_score
        row.reachability_grade = result.reachability_grade
        row.reachability_version = result.reachability_version
        row.reachability_breakdown_json = result.reachability_breakdown
        return {
            "updated": True,
            "company_id": company.id,
            "reachability_before": before,
            "reachability_after": row.reachability_score,
            "reachability_grade": row.reachability_grade,
        }


def score_rows(database: Database, *, origin: str = "all") -> list[tuple[Company, LeadScore]]:
    origin_map = {"external": "external_research", "production": "production"}
    if origin not in {"all", *origin_map}:
        raise ValueError("origin must be all, production, or external")
    database.create()
    with database.session() as session:
        query = session.query(Company, LeadScore).join(
            LeadScore, Company.id == LeadScore.company_id
        )
        if origin in origin_map:
            query = query.filter(LeadScore.data_origin == origin_map[origin])
        rows = [(company, row) for company, row in query.all()]
        return sorted(rows, key=lambda item: commercial_order_key(*item))
