from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .config import TargetingSettings
from .enums import Disposition, SourceType
from .models import ContactRecord, PainHypothesis, ScoreResult, SourceEvidence


@dataclass
class LeadInputs:
    country: str | None
    employee_band: str | None
    sources: list[SourceEvidence]
    fresh_signal_count: int
    service_fit: int
    hypotheses: list[PainHypothesis]
    contact: ContactRecord | None
    active_suppression: bool = False
    inside_cooldown: bool = False
    competitor: bool = False
    ambiguous_identity: bool = False
    research_confidence: float = 0.0
    facts_source_complete: bool = True
    permission_basis: str = "unknown"
    provider_policy_eligible: bool = False
    official_domain_verified: bool = True
    contact_source_complete: bool = True
    data_origin: str = "production"


def score_lead(
    inputs: LeadInputs, policy: TargetingSettings, today: date | None = None
) -> ScoreResult:
    today = today or date.today()
    penalties: list[str] = []
    country_ok = (inputs.country or "").strip().lower() in {
        item.lower() for item in policy.allowed_countries
    }
    company_fit = 12 if inputs.employee_band else 8
    if inputs.employee_band and any(
        token in inputs.employee_band for token in ("20", "50", "100", "250", "500", "750")
    ):
        company_fit = 18
    intent = min(25, 10 + inputs.fresh_signal_count * 8)
    service_fit = max(0, min(25, inputs.service_fit))
    official_count = sum(
        source.source_type
        in {SourceType.OFFICIAL, SourceType.OFFICIAL_JOB, SourceType.OFFICIAL_PRESS}
        for source in inputs.sources
    )
    independent_count = len(
        {str(source.url).split("/", 3)[2] for source in inputs.sources if "/" in str(source.url)}
    )
    ages = [
        max(
            0,
            (today - (source.publication_date or source.retrieved_at.date())).days,
        )
        for source in inputs.sources
    ]
    freshness = min(ages, default=999)
    evidence_quality = min(
        15,
        official_count * 5
        + min(5, independent_count)
        + (3 if freshness <= policy.fresh_signal_days else 0),
    )
    contact_quality = inputs.contact.contact_quality if inputs.contact else 0
    hard_gates = {
        "us_only": country_ok,
        "official_source": official_count > 0,
        "two_sources": len(inputs.sources) >= 2,
        "eligible_contact": bool(
            inputs.contact and inputs.contact.contact_quality > 0 and inputs.contact.official_domain
        ),
        "fresh_signal": inputs.fresh_signal_count > 0,
        "pain_confidence": bool(
            inputs.hypotheses
            and max(item.confidence for item in inputs.hypotheses) >= policy.min_pain_confidence
        ),
        "research_confidence": inputs.research_confidence >= policy.min_research_confidence,
        "source_complete": inputs.facts_source_complete,
        "contact_provenance": inputs.contact_source_complete,
        "official_domain_verified": inputs.official_domain_verified,
        "permission_basis": inputs.permission_basis != "unknown",
        "provider_policy": inputs.provider_policy_eligible,
        "production_origin": inputs.data_origin == "production",
        "not_suppressed": not inputs.active_suppression,
        "cooldown_clear": not inputs.inside_cooldown,
        "not_competitor": not inputs.competitor,
        "identity_clear": not inputs.ambiguous_identity,
    }
    for label, passed in hard_gates.items():
        if not passed:
            penalties.append(label)
    quality_penalties = [
        item
        for item in penalties
        if item
        not in {
            "permission_basis",
            "provider_policy",
            "production_origin",
            "not_suppressed",
        }
    ]
    total = max(
        0,
        min(
            100,
            company_fit
            + intent
            + service_fit
            + evidence_quality
            + contact_quality
            - len(quality_penalties) * 4,
        ),
    )
    hard_disqualifier = (
        inputs.active_suppression or inputs.inside_cooldown or inputs.competitor or not country_ok
    )
    general_inbox = bool(
        inputs.contact and inputs.contact.email.split("@", 1)[0] in {"info", "hello", "contact"}
    )
    no_contact = not hard_gates["eligible_contact"] or not hard_gates["contact_provenance"]
    if hard_disqualifier:
        disposition = Disposition.DISQUALIFIED
    elif no_contact:
        disposition = Disposition.NEEDS_CONTACT
    elif not inputs.fresh_signal_count:
        disposition = Disposition.NEEDS_REVIEW
    elif general_inbox and total < policy.min_score_auto_send + 5:
        disposition = Disposition.NEEDS_REVIEW
    elif all(hard_gates.values()) and total >= policy.min_score_auto_send:
        disposition = Disposition.AUTO_SEND
    elif total >= 68:
        disposition = Disposition.NEEDS_REVIEW
    else:
        disposition = Disposition.ARCHIVE
    return ScoreResult(
        company_fit=company_fit,
        intent=intent,
        service_fit=service_fit,
        evidence_quality=evidence_quality,
        contact_quality=contact_quality,
        penalties=penalties,
        total=total,
        disposition=disposition,
        explanation={
            "score_version": "2026-08-01",
            "components": {
                "company_fit": company_fit,
                "intent": intent,
                "service_fit": service_fit,
                "evidence_quality": evidence_quality,
                "contact_quality": contact_quality,
            },
            "fresh_signal_count": inputs.fresh_signal_count,
            "official_source_count": official_count,
            "gates": hard_gates,
            "quality_penalties": quality_penalties,
            "send_eligibility": {
                "permission_basis": inputs.permission_basis,
                "provider_policy_eligible": inputs.provider_policy_eligible,
                "allowed": all(hard_gates.values()),
            },
        },
        hard_gates=hard_gates,
    )


# Public compatibility exports: legacy callers can keep importing from this
# module while the commercial model remains separately versioned.
from .commercial_scoring import CommercialLeadInputs, score_commercial_lead  # noqa: E402

__all__ = [
    "CommercialLeadInputs",
    "LeadInputs",
    "score_commercial_lead",
    "score_lead",
]
