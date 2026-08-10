from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from urllib.parse import urlparse

from .models import CommercialScoreResult

OPPORTUNITY_FIT_VERSION = "2026-08-09-opportunity-fit-v1"
REACHABILITY_VERSION = "2026-08-09-reachability-v1"


@dataclass(frozen=True)
class CommercialLeadInputs:
    company_name: str
    company_domain: str
    vertical: str
    employee_band: str | None
    sources: tuple[Any, ...]
    signals: tuple[Any, ...]
    pain_hypotheses: tuple[Any, ...]
    contact: Any | None = None
    research_confidence: float = 0.0
    # Accepted for callers that already carry compliance context, but deliberately
    # excluded from both commercial scores.
    permission_basis: str = "unknown"
    provider_policy_eligible: bool = False


_KNOWN_PROJECT_TERMS = {
    "report",
    "reporting",
    "dashboard",
    "workflow",
    "reconciliation",
    "forecast",
    "forecasting",
    "pipeline",
    "integration",
    "exception",
    "automation",
    "handoff",
    "hand-off",
    "operations",
}
_TRIGGER_TERMS = {
    "announce",
    "announced",
    "launch",
    "launched",
    "expansion",
    "expanding",
    "funding",
    "acquisition",
    "acquired",
    "rollout",
    "created",
    "hiring",
    "growth",
    "new location",
    "new market",
    "new product",
    "new system",
    "currently lists",
    "first",
    "department-of-one",
    "first seat",
}
_BROAD_SCOPE_TERMS = {
    "enterprise platform",
    "platform replacement",
    "architecture transformation",
    "organization-wide",
    "organizational data strategy",
    "multi-year",
    "core engineering",
    "digital transformation",
    "replace all",
}
_COMPLEX_SCOPE_TERMS = {
    "migration",
    "interface",
    "data exchange",
    "participant onboarding",
    "statewide",
    "hie",
    "clinical",
    "network",
    "enterprise adoption",
}
_INAPPROPRIATE_CONTACT_TERMS = {
    "media",
    "press",
    "legal",
    "privacy",
    "security",
    "support",
    "careers",
    "career",
    "abuse",
    "investor",
    "ir@",
}
_RELEVANT_CONTACT_TERMS = {
    "revenue",
    "revops",
    "sales operations",
    "sales ops",
    "finance",
    "fp&a",
    "operations",
    "chief operating",
    "data",
    "analytics",
    "reporting",
    "forecast",
    "business intelligence",
}


def _value(item: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        value = getattr(item, name, default)
        if value is not None:
            return value
    return default


def _text(items: Iterable[Any], *names: str) -> str:
    return " ".join(str(_value(item, *names, default="") or "") for item in items).lower()


def _source_domain(value: Any) -> str:
    raw = str(value or "")
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    return (parsed.hostname or "").lower().removeprefix("www.")


def _company_domain(value: str) -> str:
    return _source_domain(value)


def _same_company_domain(source_domain: str, company_domain: str) -> bool:
    return (
        bool(source_domain)
        and bool(company_domain)
        and (source_domain == company_domain or source_domain.endswith(f".{company_domain}"))
    )


def _grade(score: int) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 50:
        return "C"
    return "D"


def _entry(points: int, maximum: int, reason: str, *source_fields: str) -> dict[str, Any]:
    return {
        "points": max(0, min(maximum, points)),
        "max_points": maximum,
        "reason": reason,
        "source_fields": list(source_fields),
    }


def _freshness_days(signal: Any, today: date) -> int | None:
    value = _value(signal, "freshness_days")
    if isinstance(value, int):
        return max(0, value)
    signal_date = _value(signal, "signal_date")
    if isinstance(signal_date, datetime):
        signal_date = signal_date.date()
    if isinstance(signal_date, date):
        return max(0, (today - signal_date).days)
    return None


def _signal_and_pain_text(inputs: CommercialLeadInputs) -> str:
    return " ".join(
        [
            _text(inputs.signals, "observed_signal", "signal_type"),
            _text(inputs.pain_hypotheses, "hypothesis", "pain_hypothesis", "service_mapping"),
        ]
    ).lower()


def _derive_buyer_persona(inputs: CommercialLeadInputs) -> tuple[str, str, int]:
    text = _signal_and_pain_text(inputs)
    signal_types = {
        str(_value(signal, "signal_type", default="")).lower() for signal in inputs.signals
    }
    mappings: tuple[tuple[str, tuple[str, ...], str], ...] = (
        (
            "revenue_operations",
            ("pipeline_and_revops", "revenue", "pipeline", "revops", "sales operations"),
            "Research describes a pipeline, revenue, or sales-operations workflow.",
        ),
        (
            "finance_fp_and_a",
            ("cash_flow_and_forecasting", "cash flow", "forecast", "fp&a", "finance"),
            "Research describes forecasting, cash-flow, or finance reporting work.",
        ),
        (
            "healthcare_data_operations",
            ("healthcare_administration", "healthcare_admin", "healthcare", "clinical data"),
            "Research describes healthcare administration or healthcare-data operations.",
        ),
        (
            "support_operations",
            ("support_operations", "support operations", "customer support"),
            "Research describes a support-operations workflow.",
        ),
        (
            "data_analytics",
            (
                "data_silos_and_integration",
                "data_quality_and_reconciliation",
                "ai_readiness_and_operationalization",
                "governance_compliance_and_auditability",
                "analytics",
                "data quality",
                "integration",
            ),
            "Research describes a data, analytics, integration, or governance workflow.",
        ),
        (
            "operations",
            ("manual_reporting", "operations", "reporting", "workflow"),
            "Research describes a recurring operating workflow without a narrower buyer signal.",
        ),
    )
    for persona, needles, reason in mappings:
        if any(needle in signal_types or needle in text for needle in needles):
            return persona, reason, 24
    employee_number = _employee_number(inputs.employee_band)
    if employee_number is not None and employee_number <= 20:
        return (
            "founder_or_executive",
            "Small-company context suggests an owner/operator may own the workflow; no narrower persona was evidenced.",
            16,
        )
    return (
        "unknown",
        "No defensible functional buyer persona was derived from normalized research.",
        0,
    )


def _derive_project(inputs: CommercialLeadInputs) -> tuple[str, str, str]:
    text = _signal_and_pain_text(inputs)
    signal_types = {
        str(_value(signal, "signal_type", default="")).lower() for signal in inputs.signals
    }
    if "pipeline_and_revops" in signal_types or any(
        token in text for token in ("pipeline", "revops", "revenue operations", "sales operations")
    ):
        project = "Pipeline and forecast reporting sprint"
    elif "cash_flow_and_forecasting" in signal_types or any(
        token in text for token in ("cash flow", "forecast", "forecasting")
    ):
        project = "Cash-flow and forecasting workflow"
    elif "data_quality_and_reconciliation" in signal_types or any(
        token in text for token in ("reconciliation", "data quality", "exception process")
    ):
        project = "Data-quality and reconciliation workflow"
    elif "data_silos_and_integration" in signal_types or "integration" in text:
        project = "Defined integration and exception workflow"
    elif "support_operations" in signal_types or "support operations" in text:
        project = "Support-operations reporting sprint"
    elif "healthcare_administration" in signal_types or "healthcare_admin" in signal_types:
        project = "Healthcare administration reporting workflow"
    elif "governance_compliance_and_auditability" in signal_types:
        project = "Governed reporting and audit workflow"
    elif "ai_readiness_and_operationalization" in signal_types:
        project = "Applied AI operationalization pilot"
    elif "sports_decision_intelligence" in signal_types:
        project = "Sports decision-intelligence prototype"
    elif any(token in text for token in ("dashboard", "report", "reporting")):
        project = "Recurring reporting and dashboard sprint"
    else:
        project = "Operational workflow assessment"

    broad = any(term in text for term in _BROAD_SCOPE_TERMS)
    concrete = bool(set(re.findall(r"[a-z][a-z-]+", text)) & _KNOWN_PROJECT_TERMS)
    explicit_bounded = any(
        token in text
        for token in (
            "one ",
            "single ",
            "weekly",
            "monthly",
            "recurring",
            "bounded",
            "sprint",
        )
    )
    complex_scope = any(term in text for term in _COMPLEX_SCOPE_TERMS)
    if broad:
        scope = "enterprise_or_unclear"
    elif complex_scope and not explicit_bounded:
        scope = "medium_1_2_months"
    elif concrete and any(
        token in text
        for token in (
            "one ",
            "single ",
            "weekly",
            "monthly",
            "recurring",
            "sprint",
            "workflow",
            "dashboard",
            "report",
        )
    ):
        scope = "bounded_2_4_weeks"
    elif concrete:
        scope = "small_1_2_weeks"
    else:
        scope = "enterprise_or_unclear"
    if scope == "enterprise_or_unclear" and not broad and inputs.pain_hypotheses:
        scope = "medium_1_2_months"
    return project, scope, text


def _employee_number(value: str | None) -> int | None:
    if not value:
        return None
    numbers = [int(item) for item in re.findall(r"\d+", value)]
    return min(numbers) if numbers else None


def _procurement_friction(
    inputs: CommercialLeadInputs, scope: str, text: str
) -> tuple[str, int, str]:
    employee_number = _employee_number(inputs.employee_band)
    regulated = inputs.vertical.lower() in {"healthcare", "financial_services"} or any(
        token in text for token in ("regulated", "hipaa", "phi", "patient", "clinical", "banking")
    )
    enterprise = employee_number is not None and employee_number >= 1000
    sophisticated = any(
        token in text
        for token in (
            "platform replacement",
            "internal engineering",
            "security review",
            "enterprise",
        )
    )
    public_sector = any(token in text for token in ("government", "public sector", "municipal"))
    if public_sector or enterprise or sophisticated:
        return (
            "high",
            4,
            "Public-sector, enterprise, or sophisticated internal-review proxies suggest higher procurement friction; this is a heuristic.",
        )
    if regulated:
        return (
            "high",
            5,
            "Healthcare/financial or regulated-workflow proxies suggest additional procurement and security review; this is a heuristic.",
        )
    if scope in {"small_1_2_weeks", "bounded_2_4_weeks"} and (
        employee_number is None or employee_number <= 500
    ):
        return (
            "low",
            12,
            "A bounded project in a small or mid-size operating context is a lower-friction purchase proxy; this is a heuristic.",
        )
    if inputs.vertical or employee_number is not None:
        return (
            "medium",
            9,
            "The operating context is known, but the available evidence does not establish a low-friction purchase; this is a heuristic.",
        )
    return (
        "unknown",
        7,
        "Procurement friction is not defensibly inferable from the available public research; this is a heuristic.",
    )


def _opportunity_score(
    inputs: CommercialLeadInputs, today: date
) -> tuple[int, str, dict[str, Any], str, str, str, str]:
    text = _signal_and_pain_text(inputs)
    project, scope, _project_text = _derive_project(inputs)
    persona, persona_reason, _ = _derive_buyer_persona(inputs)
    max_pain_confidence = max(
        (float(_value(item, "confidence", default=0) or 0) for item in inputs.pain_hypotheses),
        default=0,
    )
    concrete = bool(set(re.findall(r"[a-z][a-z-]+", text)) & _KNOWN_PROJECT_TERMS)
    pain_points = (
        (10 if inputs.pain_hypotheses else 0)
        + (6 if concrete else 0)
        + (2 if max_pain_confidence >= 0.8 else 0)
        + (2 if len(inputs.pain_hypotheses) >= 2 else 0)
    )
    pain_reason = f"{len(inputs.pain_hypotheses)} normalized hypothesis/hypotheses" + (
        " describe a concrete operational artifact or workflow."
        if concrete
        else " do not yet describe a concrete operational artifact."
    )
    service_text = _text(inputs.pain_hypotheses, "service_mapping", "service_match")
    direct_service = any(
        token in service_text
        for token in (
            "report",
            "dashboard",
            "automation",
            "integration",
            "reconciliation",
            "forecast",
            "pipeline",
            "revops",
            "support operations",
            "healthcare administration",
            "governed",
        )
    )
    recognized_signal = any(
        str(_value(signal, "signal_type", default="")).lower()
        in {
            "manual_reporting",
            "data_silos_and_integration",
            "data_quality_and_reconciliation",
            "cash_flow_and_forecasting",
            "pipeline_and_revops",
            "support_operations",
            "ai_readiness_and_operationalization",
            "governance_compliance_and_auditability",
            "healthcare_administration",
            "sports_decision_intelligence",
        }
        for signal in inputs.signals
    )
    service_points = (
        20 if direct_service else 16 if recognized_signal else 8 if inputs.pain_hypotheses else 0
    )
    service_reason = (
        "A canonical service mapping directly matches the researched workflow."
        if direct_service
        else "A recognized workflow signal exists, but the service mapping is partial or ambiguous."
        if recognized_signal
        else "A pain hypothesis exists without a defensible direct service match."
        if service_points
        else "No defensible service mapping was persisted."
    )

    freshness = [_freshness_days(signal, today) for signal in inputs.signals]
    usable_freshness = [value for value in freshness if value is not None]
    newest = min(usable_freshness, default=None)
    trigger_bonus = 3 if any(term in text for term in _TRIGGER_TERMS) else 0
    if newest is None:
        trigger_points = 4 + trigger_bonus
        trigger_reason = (
            "A signal exists but its date is unknown; trigger strength is kept conservative."
        )
    elif newest <= 30:
        trigger_points = 12 + trigger_bonus
        trigger_reason = (
            f"The strongest normalized signal is {newest} days old and includes a current change trigger."
            if trigger_bonus
            else f"The strongest normalized signal is {newest} days old."
        )
    elif newest <= 90:
        trigger_points = 10 + trigger_bonus
        trigger_reason = f"The strongest normalized signal is {newest} days old."
    elif newest <= 180:
        trigger_points = 7 + trigger_bonus
        trigger_reason = (
            f"The strongest normalized signal is {newest} days old; urgency is moderate."
        )
    else:
        trigger_points = 3 + trigger_bonus
        trigger_reason = f"The strongest normalized signal is {newest} days old; freshness is weak."
    trigger_points = min(15, trigger_points)

    if scope == "small_1_2_weeks":
        project_points = 20
        project_reason = f"Research supports a small bounded project: {project}."
    elif scope == "bounded_2_4_weeks":
        project_points = 18
        project_reason = f"Research supports a bounded 2–4 week workflow: {project}."
    elif scope == "medium_1_2_months":
        project_points = 11
        project_reason = (
            f"The workflow is plausible but its scope is broader than a first sprint: {project}."
        )
    else:
        project_points = 4 if any(term in text for term in _BROAD_SCOPE_TERMS) else 7
        project_reason = "The research does not establish a bounded first engagement; broad or unclear scope is discounted."

    friction, buyability_points, friction_reason = _procurement_friction(inputs, scope, text)
    if inputs.vertical.lower() in {"operational_business", "sports"}:
        buyability_points += 2
        friction_reason += " Operating-business context is a positive contained-project proxy; this is a heuristic."
    buyability_points = min(15, buyability_points)

    official = sum(
        _source_domain(_value(source, "url", default="")) == _company_domain(inputs.company_domain)
        and str(_value(source, "source_type", default="")).lower()
        in {"official", "official_job", "official_press", "official_careers", "official_news"}
        for source in inputs.sources
    )
    same_domain = sum(
        _same_company_domain(
            _source_domain(_value(source, "url", default="")),
            _company_domain(inputs.company_domain),
        )
        for source in inputs.sources
    )
    evidence_points = min(
        10,
        (4 if official else 0)
        + (2 if len(inputs.sources) >= 2 else 0)
        + (2 if same_domain >= 2 else 0)
        + (2 if inputs.research_confidence >= 0.8 else 0),
    )
    evidence_reason = f"{official} canonical same-domain official source(s), {len(inputs.sources)} total source(s), research confidence {inputs.research_confidence:.2f}; evidence is capped at 10."
    breakdown = {
        "pain_specificity": _entry(
            pain_points, 20, pain_reason, "pain_hypotheses", "signal.observed_signal"
        ),
        "service_match": _entry(
            service_points,
            20,
            service_reason,
            "pain_hypotheses.service_mapping",
            "signal.signal_type",
        ),
        "trigger_strength": _entry(
            trigger_points,
            15,
            trigger_reason,
            "signal.signal_date",
            "signal.freshness_days",
            "signal.observed_signal",
        ),
        "small_project_suitability": _entry(
            project_points,
            20,
            project_reason,
            "signal.observed_signal",
            "pain_hypotheses.hypothesis",
        ),
        "commercial_buyability": _entry(
            buyability_points,
            15,
            friction_reason,
            "company.vertical",
            "company.employee_band",
            "project_scope_band",
        ),
        "evidence_confidence": _entry(
            evidence_points,
            10,
            evidence_reason,
            "sources.source_type",
            "sources.url",
            "research_confidence",
        ),
    }
    score = sum(int(item["points"]) for item in breakdown.values())
    return score, _grade(score), breakdown, persona, project, scope, friction


def _contact_role(contact: Any) -> tuple[str, str]:
    email = str(_value(contact, "email", default="")).lower()
    role = " ".join(
        str(_value(contact, name, default="") or "").lower()
        for name in ("title", "role", "role_inbox_category", "appropriateness_reason")
    )
    local = email.split("@", 1)[0] if "@" in email else email
    if any(term in role or term in email for term in _INAPPROPRIATE_CONTACT_TERMS):
        return "inappropriate", role
    if local in {"info", "hello", "contact", "office", "admin"} or "general_business" in role:
        return "general", role
    if any(term in role for term in _RELEVANT_CONTACT_TERMS) or "relevant_role" in role:
        return "relevant", role
    if "functional" in role or "business" in role:
        return "functional", role
    return "named", role if role else local


def _reachability_score(
    inputs: CommercialLeadInputs, persona: str, persona_reason: str
) -> tuple[int, str, dict[str, Any]]:
    contact = inputs.contact
    if persona != "unknown":
        persona_points = (
            24 if contact is None or not _value(contact, "title", "display_name") else 30
        )
        persona_text = persona_reason
    else:
        persona_points = 0
        persona_text = persona_reason
    channel, role_text = _contact_role(contact) if contact is not None else ("missing", "")
    if channel == "relevant":
        contact_points, contact_reason = (
            30,
            "A relevant named business role or role-based business channel is available.",
        )
    elif channel == "functional":
        contact_points, contact_reason = (
            25,
            "A functional business channel is available, but its fit is broader than the inferred persona.",
        )
    elif channel == "general":
        contact_points, contact_reason = (
            15,
            "A general business inbox is available; it is usable but less targeted.",
        )
    elif channel == "inappropriate":
        contact_points, contact_reason = (
            0,
            "The available mailbox is a media, legal, privacy, security, support, careers, abuse, or investor channel and is not an appropriate buyer path.",
        )
    elif channel == "named":
        contact_points, contact_reason = (
            22,
            "A named business contact is available, but the public role does not establish a close workflow match.",
        )
    else:
        contact_points, contact_reason = (
            0,
            "No appropriate business contact or channel is available.",
        )
    official = bool(_value(contact, "official_domain", default=False)) if contact else False
    source_url = str(_value(contact, "source_url", default="") or "") if contact else ""
    source_matches = _same_company_domain(
        _source_domain(source_url), _company_domain(inputs.company_domain)
    )
    email_domain = (
        _source_domain(str(_value(contact, "email", default="")).split("@", 1)[-1])
        if contact
        else ""
    )
    email_matches = _same_company_domain(email_domain, _company_domain(inputs.company_domain))
    status = (
        str(_value(contact, "source_verification_status", default="not_checked") or "not_checked")
        if contact
        else "not_checked"
    )
    if not contact:
        provenance_points, provenance_reason = 0, "No contact source exists to verify."
    elif official and source_matches and email_matches and status == "verified":
        provenance_points, provenance_reason = (
            25,
            "The contact is visibly tied to the official same-company domain and source verification is verified.",
        )
    elif official and source_matches and email_matches:
        provenance_points, provenance_reason = (
            18,
            f"The contact is tied to the official same-company domain but source verification is {status}.",
        )
    elif official and email_matches:
        provenance_points, provenance_reason = (
            13,
            "The contact uses the company domain, but the source URL provenance is incomplete or off-domain.",
        )
    else:
        provenance_points, provenance_reason = (
            5,
            "Contact provenance or company-domain alignment is incomplete; no guessing or SMTP probing is rewarded.",
        )
    if channel == "inappropriate":
        relevance_points, relevance_reason = (
            0,
            "The channel is not relevant to the inferred buyer workflow.",
        )
    elif channel == "relevant":
        relevance_points, relevance_reason = (
            15,
            "The discovered channel is relevant to the inferred buyer workflow.",
        )
    elif channel == "functional":
        relevance_points, relevance_reason = (
            12,
            "The channel is business-relevant but not specifically matched to the inferred persona.",
        )
    elif channel == "general":
        relevance_points, relevance_reason = (
            7,
            "A general business inbox may route the inquiry, but it is less relevant than a functional channel.",
        )
    elif channel == "named":
        relevance_points, relevance_reason = (
            10,
            "A named business path is usable, although the role-to-workflow match is not explicit.",
        )
    else:
        relevance_points, relevance_reason = 0, "No channel is available."
    breakdown = {
        "buyer_persona_clarity": _entry(
            persona_points,
            30,
            persona_text,
            "signal.signal_type",
            "signal.observed_signal",
            "pain_hypotheses.hypothesis",
        ),
        "appropriate_business_contact": _entry(
            contact_points,
            30,
            contact_reason,
            "contact.email",
            "contact.title",
            "contact.role_inbox_category",
        ),
        "contact_provenance_verification": _entry(
            provenance_points,
            25,
            provenance_reason,
            "contact.source_url",
            "contact.official_domain",
            "contact.source_verification_status",
        ),
        "channel_relevance": _entry(
            relevance_points,
            15,
            relevance_reason,
            "contact.email",
            "contact.title",
            "contact.role_inbox_category",
        ),
    }
    score = sum(int(item["points"]) for item in breakdown.values())
    return score, _grade(score), breakdown


def score_commercial_lead(
    inputs: CommercialLeadInputs, today: date | None = None
) -> CommercialScoreResult:
    today = today or date.today()
    score, grade, fit_breakdown, persona, project, scope, friction = _opportunity_score(
        inputs, today
    )
    _, persona_reason, _ = _derive_buyer_persona(inputs)
    reach_score, reach_grade, reach_breakdown = _reachability_score(inputs, persona, persona_reason)
    priority = (
        "Priority 1 — pursue now"
        if grade in {"A", "B"} and reach_grade in {"A", "B"}
        else "Priority 2 — solve contact path"
        if grade in {"A", "B"}
        else "Priority 3 — nurture/research"
        if grade == "C"
        else "Priority 4 — low priority"
    )
    return CommercialScoreResult(
        opportunity_fit_version=OPPORTUNITY_FIT_VERSION,
        opportunity_fit_score=score,
        opportunity_fit_grade=grade,
        opportunity_fit_breakdown=fit_breakdown,
        reachability_version=REACHABILITY_VERSION,
        reachability_score=reach_score,
        reachability_grade=reach_grade,
        reachability_breakdown=reach_breakdown,
        primary_buyer_persona=persona,
        primary_project_type=project,
        project_scope_band=scope,
        procurement_friction_band=friction,
        priority=priority,
    )


def commercial_inputs_from_records(
    company: Any,
    sources: Iterable[Any],
    signals: Iterable[Any],
    pain_hypotheses: Iterable[Any],
    contact: Any | None,
    *,
    research_confidence: float = 0.0,
) -> CommercialLeadInputs:
    return CommercialLeadInputs(
        company_name=str(_value(company, "name", default="")),
        company_domain=str(_value(company, "registrable_domain", default="")),
        vertical=str(_value(company, "vertical", default="")),
        employee_band=(
            str(_value(company, "employee_band", default=""))
            if _value(company, "employee_band", default=None)
            else None
        ),
        sources=tuple(sources),
        signals=tuple(signals),
        pain_hypotheses=tuple(pain_hypotheses),
        contact=contact,
        research_confidence=max(0.0, min(1.0, float(research_confidence))),
    )
