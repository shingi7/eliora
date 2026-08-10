from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from .enums import Disposition, SignalType, SourceType


class SourceEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    url: HttpUrl
    canonical_url: str | None = None
    title: str
    publisher: str
    source_type: SourceType
    retrieved_at: datetime
    publication_date: date | None = None
    excerpt: str = Field(min_length=1, max_length=1000)
    source_quality: float = Field(ge=0, le=1)
    robots_allowed: bool = True
    http_status: int | None = None
    source_tier: str = "C"
    freshness_category: str = "unknown"
    claim_type: str = "observed_fact"
    date_confidence: str = "unknown"
    originating_query: str | None = None
    run_id: str | None = None
    openai_request_id: str | None = None


class ObservedSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    company_id: str
    source_id: str
    signal_type: SignalType
    observed_signal: str = Field(min_length=1, max_length=600)
    signal_date: date | None = None
    freshness_days: int | None = Field(default=None, ge=0)
    confidence: float = Field(ge=0, le=1)


class PainHypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    company_id: str
    category: SignalType
    pain_hypothesis: str = Field(min_length=1, max_length=600)
    confidence: float = Field(ge=0, le=1)
    service_match: str
    supporting_signal_ids: list[str] = Field(min_length=1)

    @field_validator("pain_hypothesis")
    @classmethod
    def must_be_inference(cls, value: str) -> str:
        lowered = value.lower()
        if any(token in lowered for token in ("has a problem", "is struggling", "definitely has")):
            raise ValueError("Pain hypotheses must remain tentative inferences")
        return value


class CompanyRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    registrable_domain: str
    official_website: HttpUrl
    country: str | None = None
    state: str | None = None
    city: str | None = None
    timezone: str = "America/New_York"
    timezone_confidence: float = 0.0
    vertical: str
    employee_band: str | None = None
    lifecycle_status: str = "active"
    data_origin: str = "production"
    official_domain_confidence: float = Field(default=0, ge=0, le=1)
    domain_confidence_reason: str | None = None
    discovery_query: str | None = None


class ContactRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    company_id: str
    email: str
    source_id: str
    source_url: HttpUrl
    extraction_method: str
    display_name: str | None = None
    role: str | None = None
    official_domain: bool
    syntactic_valid: bool
    mx_valid: bool | None = None
    appropriateness_status: str
    appropriateness_reason: str
    contact_quality: int = Field(ge=0, le=15)
    source_title: str | None = None
    source_context: str | None = None
    no_guessed_address: bool = True
    role_inbox_category: str | None = None
    source_verification_status: str = "not_checked"


class ScoreResult(BaseModel):
    score_version: str = "2026-08-01"
    company_fit: int = Field(ge=0, le=20)
    intent: int = Field(ge=0, le=25)
    service_fit: int = Field(ge=0, le=25)
    evidence_quality: int = Field(ge=0, le=15)
    contact_quality: int = Field(ge=0, le=15)
    penalties: list[str] = []
    total: int = Field(ge=0, le=100)
    disposition: Disposition
    explanation: dict[str, Any]
    hard_gates: dict[str, bool]


class CommercialScoreResult(BaseModel):
    """The versioned, non-compliance commercial prioritization result."""

    opportunity_fit_version: str
    opportunity_fit_score: int = Field(ge=0, le=100)
    opportunity_fit_grade: str
    opportunity_fit_breakdown: dict[str, Any]
    reachability_version: str
    reachability_score: int = Field(ge=0, le=100)
    reachability_grade: str
    reachability_breakdown: dict[str, Any]
    primary_buyer_persona: str
    primary_project_type: str
    project_scope_band: str
    procurement_friction_band: str
    priority: str


class DraftContent(BaseModel):
    subject: str
    body: str
    html_body: str
    source_fact_ids: list[str]
    model: str = "deterministic"
    prompt_version: str = "2026-08-01"


class DiscoveredCandidate(BaseModel):
    company_name: str
    official_website_candidate: HttpUrl
    country: str | None = None
    vertical: str
    observed_signal: dict[str, Any]
    why_potential_fit: str
    recommended_research_pages: list[HttpUrl] = []
    confidence: float = Field(ge=0, le=1)


class ExtractionResult(BaseModel):
    company: dict[str, Any]
    signals: list[dict[str, Any]]
    pain_hypotheses: list[dict[str, Any]]
    recommended_buyer_roles: list[str]
    disqualifiers: list[str]
    overall_confidence: float = Field(ge=0, le=1)
