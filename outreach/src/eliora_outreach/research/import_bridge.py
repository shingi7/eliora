from __future__ import annotations

import hashlib
import html
import json
import re
import socket
import ssl
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import httpx
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    ValidationError,
)
from sqlalchemy import select

from ..compliance import evaluate_dispatch_eligibility
from ..config import Settings
from ..db import (
    AuditEvent,
    Company,
    Contact,
    Database,
    Draft,
    ImportRecord,
    LeadScore,
    Run,
    Signal,
    Source,
    Suppression,
)
from ..db import PainHypothesis as PainRow
from ..email.guardrails import check_draft
from ..enums import RunStatus, RunType, SignalType, SourceType
from ..models import ContactRecord, DraftContent, PainHypothesis, SourceEvidence
from ..research.canonicalize import (
    canonicalize_url,
    is_reserved_domain,
    registrable_domain,
    url_hash,
    validate_public_url,
)
from ..research.contacts import ContactValidation, validate_public_contact
from ..research.crawler import CrawlerBudgetExceeded, SafeCrawler
from ..score_service import apply_commercial_score, commercial_score_for_records
from ..scoring import LeadInputs, score_lead

SCHEMA_VERSION = "1.0"
BUNDLE_TYPE = "eliora_external_research"
MAX_BUNDLE_BYTES = 5_000_000
MAX_COMPANIES = 20
MAX_EVIDENCE_PER_COMPANY = 20
MAX_EXCERPT_CHARS = 1_000
MANUAL_VERIFICATION_MIN_REQUESTS = 5
MANUAL_VERIFICATION_MAX_REQUESTS = 10


class ImportVertical(StrEnum):
    HEALTHCARE = "healthcare"
    FINANCIAL_SERVICES = "financial_services"
    OPERATIONAL_BUSINESS = "operational_business"
    SPORTS = "sports"


class ImportConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ImportFreshness(StrEnum):
    STRONG = "strong"
    ACCEPTABLE = "acceptable"
    STALE = "stale"
    UNKNOWN = "unknown"


class ImportSourceTier(StrEnum):
    A = "A"
    B = "B"
    C = "C"


class ImportSourceType(StrEnum):
    OFFICIAL = "official"
    OFFICIAL_CAREERS = "official_careers"
    OFFICIAL_NEWS = "official_news"
    GOVERNMENT = "government"
    REGULATOR = "regulator"
    REPUTABLE_NEWS = "reputable_news"
    TRADE_NEWS = "trade_news"


class ImportSignalCategory(StrEnum):
    MANUAL_REPORTING = "manual_reporting"
    DATA_SILOS_AND_INTEGRATION = "data_silos_and_integration"
    DATA_QUALITY_AND_RECONCILIATION = "data_quality_and_reconciliation"
    CASH_FLOW_AND_FORECASTING = "cash_flow_and_forecasting"
    PIPELINE_AND_REVOPS = "pipeline_and_revops"
    SUPPORT_OPERATIONS = "support_operations"
    AI_READINESS_AND_OPERATIONALIZATION = "ai_readiness_and_operationalization"
    GOVERNANCE_COMPLIANCE_AND_AUDITABILITY = "governance_compliance_and_auditability"
    HEALTHCARE_ADMIN = "healthcare_admin"
    HEALTHCARE_ADMINISTRATION = "healthcare_administration"
    SPORTS_DECISION_INTELLIGENCE = "sports_decision_intelligence"


class ImportPermissionBasis(StrEnum):
    UNKNOWN = "unknown"
    OWNER_APPROVED = "owner_approved"
    EXISTING_RELATIONSHIP = "existing_relationship"
    EXPLICIT_INBOUND_REQUEST = "explicit_inbound_request"
    CONTRACTUAL_OR_TRANSACTIONAL = "contractual_or_transactional"


class ImportContactType(StrEnum):
    FUNCTIONAL_INBOX = "functional_inbox"
    NAMED_BUSINESS_CONTACT = "named_business_contact"
    GENERAL_BUSINESS_INBOX = "general_business_inbox"


class GeneratedBy(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    system: str = Field(min_length=1, max_length=80)
    method: Literal["manual_web_research", "synthetic_template"]
    notes: str | None = Field(default=None, max_length=500)


class ResearchScope(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    geography: str = Field(min_length=1, max_length=80)
    target_company_profile: str | None = Field(default=None, max_length=300)
    verticals: list[ImportVertical] = Field(default_factory=list, max_length=10)
    max_companies: int | None = Field(default=None, ge=1, le=MAX_COMPANIES)


class Location(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=80)
    country: str | None = Field(default=None, max_length=80)


class EmployeeEstimate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    value: int | None = Field(default=None, ge=1, le=10_000_000)
    confidence: ImportConfidence
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)


class Discovery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    why_selected: str = Field(min_length=1, max_length=1_000)
    signal_category: ImportSignalCategory
    signal_date: date | None = None
    signal_freshness: ImportFreshness
    discovery_query: str | None = Field(default=None, max_length=500)


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    evidence_id: str = Field(min_length=1, max_length=80)
    source_url: HttpUrl
    source_title: str = Field(min_length=1, max_length=500)
    publisher: str = Field(min_length=1, max_length=255)
    source_type: ImportSourceType
    source_tier: ImportSourceTier
    published_at: date | None = None
    retrieved_at: datetime
    excerpt: str = Field(min_length=1, max_length=MAX_EXCERPT_CHARS)
    claims_supported: list[str] = Field(default_factory=list, max_length=40)


class ObservedFact(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    fact_id: str = Field(min_length=1, max_length=80)
    statement: str = Field(min_length=1, max_length=1_000)
    evidence_ids: list[str] = Field(min_length=1, max_length=20)
    confidence: ImportConfidence


class PainHypothesisImport(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    hypothesis_id: str = Field(min_length=1, max_length=80)
    statement: str = Field(min_length=1, max_length=1_000)
    confidence: ImportConfidence
    based_on_fact_ids: list[str] = Field(min_length=1, max_length=20)
    reason: str = Field(min_length=1, max_length=800)


class ServiceMatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    service_key: str = Field(min_length=1, max_length=80)
    service_name: str | None = Field(default=None, max_length=255)
    public_url: HttpUrl | None = None
    why_fit: str = Field(min_length=1, max_length=800)
    based_on_fact_ids: list[str] = Field(default_factory=list, max_length=20)
    based_on_hypothesis_ids: list[str] = Field(default_factory=list, max_length=20)


class ContactImport(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    email: str = Field(min_length=3, max_length=320)
    name: str | None = Field(default=None, max_length=255)
    role: str | None = Field(default=None, max_length=255)
    contact_type: ImportContactType
    source_url: HttpUrl
    source_title: str = Field(min_length=1, max_length=500)
    context: str = Field(min_length=1, max_length=1_000)
    retrieved_at: datetime
    permission_basis: ImportPermissionBasis = ImportPermissionBasis.UNKNOWN


class DraftImport(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    subject: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1, max_length=20_000)
    evidence_fact_ids: list[str] = Field(min_length=1, max_length=20)
    pain_hypothesis_ids: list[str] = Field(default_factory=list, max_length=20)
    service_key: str = Field(min_length=1, max_length=80)
    cta_type: Literal["reply", "meeting", "none"] = "reply"
    meeting_link_used: bool = False


class ResearcherAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    suggested_priority: Literal["high", "medium", "low"] | None = None
    notes: str | None = Field(default=None, max_length=800)


class ExternalCompany(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    external_company_id: str = Field(min_length=1, max_length=120)
    company_name: str = Field(min_length=1, max_length=255)
    official_domain: str = Field(min_length=3, max_length=255)
    official_website: HttpUrl
    industry: str | None = Field(default=None, max_length=120)
    vertical: ImportVertical
    location: Location
    employee_estimate: EmployeeEstimate | None = None
    discovery: Discovery
    evidence: list[Evidence] = Field(min_length=1, max_length=MAX_EVIDENCE_PER_COMPANY)
    observed_facts: list[ObservedFact] = Field(default_factory=list, max_length=40)
    pain_hypotheses: list[PainHypothesisImport] = Field(default_factory=list, max_length=40)
    service_match: ServiceMatch | None = None
    contact: ContactImport | None = None
    draft: DraftImport | None = None
    researcher_assessment: ResearcherAssessment | None = None


class ExternalResearchBundle(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    schema_version: Literal["1.0"]
    bundle_type: Literal["eliora_external_research"]
    generated_at: datetime
    generated_by: GeneratedBy
    research_scope: ResearchScope
    companies: list[ExternalCompany] = Field(min_length=1, max_length=MAX_COMPANIES)


@dataclass(frozen=True)
class SourceVerification:
    status: str
    detail: str


@dataclass(frozen=True)
class DraftValidationResult:
    external_company_id: str
    company_name: str
    passed: bool
    findings: list[dict[str, str]]
    warnings: list[str]
    errors: list[str]
    evidence_linkage: dict[str, Any]
    contact_dependent_issues: list[str]
    send_ready: bool
    dispatch_blocked_reasons: list[str]

    @property
    def status(self) -> str:
        return "pass" if self.passed else "review"

    def as_dict(self) -> dict[str, Any]:
        return {
            "external_company_id": self.external_company_id,
            "company_name": self.company_name,
            "status": self.status,
            "passed": self.passed,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "findings": list(self.findings),
            "evidence_linkage": dict(self.evidence_linkage),
            "contact_dependent_issues": list(self.contact_dependent_issues),
            "send_ready": self.send_ready,
            "dispatch_blocked_reasons": list(self.dispatch_blocked_reasons),
        }

    def quality_findings(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "findings": list(self.findings),
            "external_research_validation": self.as_dict(),
        }


@dataclass
class ValidationResult:
    bundle: ExternalResearchBundle
    bundle_hash: str
    filename: str
    warnings: list[str] = field(default_factory=list)
    verified_contacts: int = 0
    verification_requested: bool = False
    contact_verifications: dict[str, SourceVerification] = field(default_factory=dict)
    draft_validations: list[DraftValidationResult] = field(default_factory=list)

    @property
    def draft_validation_by_company(self) -> dict[str, DraftValidationResult]:
        return {item.external_company_id: item for item in self.draft_validations}

    @property
    def preview(self) -> dict[str, int]:
        passing = sum(item.passed for item in self.draft_validations)
        needing_review = len(self.draft_validations) - passing
        send_ready = sum(item.send_ready for item in self.draft_validations)
        return {
            "companies": len(self.bundle.companies),
            "evidence": sum(len(item.evidence) for item in self.bundle.companies),
            "contacts": sum(item.contact is not None for item in self.bundle.companies),
            "verified_contacts": self.verified_contacts,
            "drafts": sum(item.draft is not None for item in self.bundle.companies),
            "drafts_passing_validation": passing,
            "drafts_needing_review": needing_review,
            "drafts_send_ready": send_ready,
            "warnings": len(self.warnings),
        }


class ImportBridgeError(ValueError):
    def __init__(self, message: str, *, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors = errors or [message]


SERVICE_REGISTRY: dict[str, tuple[str, str]] = {
    "reporting_automation": (
        "Reporting Automation Sprint",
        "https://elioratechsolutions.com",
    ),
    "data_silos_and_integration": (
        "Connected Data and Integration Workflow",
        "https://elioratechsolutions.com",
    ),
    "data_quality_and_reconciliation": (
        "Data Quality and Reconciliation Workflow",
        "https://elioratechsolutions.com",
    ),
    "cash_flow_and_forecasting": (
        "Cash Flow and Forecasting Workflow",
        "https://elioratechsolutions.com",
    ),
    "pipeline_and_revops": (
        "Pipeline and RevOps Workflow",
        "https://elioratechsolutions.com",
    ),
    "support_operations": (
        "Support Operations Intelligence Workflow",
        "https://elioratechsolutions.com",
    ),
    "ai_readiness_and_operationalization": (
        "Applied AI Readiness Workflow",
        "https://elioratechsolutions.com",
    ),
    "governance_compliance_and_auditability": (
        "Governed Reporting and Decision Workflow",
        "https://elioratechsolutions.com",
    ),
    "healthcare_administration": (
        "Healthcare Administration Workflow",
        "https://elioratechsolutions.com",
    ),
    "sports_decision_intelligence": (
        "Sports Decision Intelligence Prototype",
        "https://elioratechsolutions.com",
    ),
}

_SOURCE_MAP = {
    ImportSourceType.OFFICIAL: SourceType.OFFICIAL,
    ImportSourceType.OFFICIAL_CAREERS: SourceType.OFFICIAL_JOB,
    ImportSourceType.OFFICIAL_NEWS: SourceType.OFFICIAL_PRESS,
    ImportSourceType.GOVERNMENT: SourceType.FILING,
    ImportSourceType.REGULATOR: SourceType.FILING,
    ImportSourceType.REPUTABLE_NEWS: SourceType.REPUTABLE_NEWS,
    ImportSourceType.TRADE_NEWS: SourceType.REPUTABLE_NEWS,
}
_SIGNAL_MAP = {
    ImportSignalCategory.HEALTHCARE_ADMIN: SignalType.HEALTHCARE_ADMINISTRATION,
    ImportSignalCategory.HEALTHCARE_ADMINISTRATION: SignalType.HEALTHCARE_ADMINISTRATION,
}
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_URL_SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "ow.ly", "goo.gl"}


def _json_hash(data: object) -> str:
    encoded = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _confidence(value: ImportConfidence) -> float:
    return {ImportConfidence.HIGH: 0.9, ImportConfidence.MEDIUM: 0.65, ImportConfidence.LOW: 0.35}[
        value
    ]


def _signal_type(value: ImportSignalCategory) -> SignalType:
    mapped = _SIGNAL_MAP.get(value)
    return mapped if mapped is not None else SignalType(value.value)


def _canonical_public_url(value: str, *, synthetic: bool) -> str:
    canonical = canonicalize_url(value)
    if synthetic and is_reserved_domain(canonical):
        return canonical
    return validate_public_url(canonical, resolve=False)


def _domain_url(domain: str) -> str:
    return f"https://{domain.strip().lower().rstrip('.')}/"


def _validate_timestamp(value: datetime, label: str, errors: list[str]) -> None:
    if value.tzinfo is None:
        errors.append(f"{label} must include a timezone offset")


def _scan_strings(value: object, path: str, errors: list[str]) -> None:
    if isinstance(value, str):
        if _CONTROL_CHARS.search(value):
            errors.append(f"{path} contains disallowed control characters")
        return
    if isinstance(value, dict):
        for key, child in value.items():
            _scan_strings(child, f"{path}.{key}", errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_strings(child, f"{path}[{index}]", errors)


def _validate_bundle(bundle: ExternalResearchBundle, raw: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    warnings: list[str] = []
    synthetic = bundle.generated_by.method == "synthetic_template"
    _validate_timestamp(bundle.generated_at, "generated_at", errors)
    if bundle.research_scope.geography.lower() not in {"us", "usa", "united states"}:
        errors.append("research_scope.geography must be US/USA/United States")
    company_ids: set[str] = set()
    for company in bundle.companies:
        prefix = f"companies[{company.external_company_id}]"
        if company.external_company_id in company_ids:
            errors.append(f"{prefix}.external_company_id is duplicated")
        company_ids.add(company.external_company_id)
        if company.location.country and company.location.country.lower() not in {
            "us",
            "usa",
            "united states",
        }:
            errors.append(f"{prefix}.location.country must be US for this import")
        try:
            website = _canonical_public_url(str(company.official_website), synthetic=synthetic)
            domain = registrable_domain(company.official_domain)
            if domain != registrable_domain(website):
                errors.append(f"{prefix}.official_domain does not match official_website")
            if not synthetic:
                _canonical_public_url(_domain_url(company.official_domain), synthetic=False)
        except ValueError as exc:
            errors.append(f"{prefix}.official website/domain: {exc}")
            domain = company.official_domain.lower()
        evidence_by_id: dict[str, Evidence] = {}
        for evidence in company.evidence:
            if evidence.evidence_id in evidence_by_id:
                errors.append(f"{prefix}.evidence ID {evidence.evidence_id} is duplicated")
            evidence_by_id[evidence.evidence_id] = evidence
            _validate_timestamp(
                evidence.retrieved_at, f"{prefix}.{evidence.evidence_id}.retrieved_at", errors
            )
            try:
                evidence_url = _canonical_public_url(str(evidence.source_url), synthetic=synthetic)
                if not synthetic and urlparse(evidence_url).hostname in _URL_SHORTENERS:
                    errors.append(f"{prefix}.{evidence.evidence_id} uses a URL shortener")
                if (
                    evidence.source_tier == ImportSourceTier.A
                    and registrable_domain(evidence_url) != domain
                    and evidence.source_type
                    in {
                        ImportSourceType.OFFICIAL,
                        ImportSourceType.OFFICIAL_CAREERS,
                        ImportSourceType.OFFICIAL_NEWS,
                    }
                ):
                    errors.append(
                        f"{prefix}.{evidence.evidence_id} Tier A official source is off-domain"
                    )
            except ValueError as exc:
                errors.append(f"{prefix}.{evidence.evidence_id}.source_url: {exc}")
        fact_by_id: dict[str, ObservedFact] = {}
        for fact in company.observed_facts:
            if fact.fact_id in fact_by_id:
                errors.append(f"{prefix}.fact ID {fact.fact_id} is duplicated")
            fact_by_id[fact.fact_id] = fact
            for evidence_id in fact.evidence_ids:
                if evidence_id not in evidence_by_id:
                    errors.append(
                        f"{prefix}.{fact.fact_id} references missing evidence {evidence_id}"
                    )
        for evidence in company.evidence:
            for fact_id in evidence.claims_supported:
                if fact_id not in fact_by_id:
                    errors.append(
                        f"{prefix}.{evidence.evidence_id} references missing fact {fact_id}"
                    )
        pain_by_id: dict[str, PainHypothesisImport] = {}
        for pain in company.pain_hypotheses:
            if pain.hypothesis_id in pain_by_id:
                errors.append(f"{prefix}.hypothesis ID {pain.hypothesis_id} is duplicated")
            pain_by_id[pain.hypothesis_id] = pain
            lowered = pain.statement.lower()
            if any(
                phrase in lowered
                for phrase in (
                    "you are struggling with",
                    "your team wastes",
                    "your systems are broken",
                )
            ):
                warnings.append(f"{prefix}.{pain.hypothesis_id} uses definitive-risk language")
            for fact_id in pain.based_on_fact_ids:
                if fact_id not in fact_by_id:
                    errors.append(
                        f"{prefix}.{pain.hypothesis_id} references missing fact {fact_id}"
                    )
        if company.employee_estimate:
            for evidence_id in company.employee_estimate.evidence_ids:
                if evidence_id not in evidence_by_id:
                    errors.append(
                        f"{prefix}.employee_estimate references missing evidence {evidence_id}"
                    )
        if company.service_match:
            service = SERVICE_REGISTRY.get(company.service_match.service_key)
            if service is None:
                errors.append(f"{prefix}.service_match has an unknown service_key")
            else:
                if (
                    company.service_match.service_name
                    and company.service_match.service_name != service[0]
                ):
                    errors.append(f"{prefix}.service_match.service_name is not canonical")
                if company.service_match.public_url and canonicalize_url(
                    str(company.service_match.public_url)
                ) != canonicalize_url(service[1]):
                    errors.append(f"{prefix}.service_match.public_url is not canonical")
                for fact_id in company.service_match.based_on_fact_ids:
                    if fact_id not in fact_by_id:
                        errors.append(f"{prefix}.service_match references missing fact {fact_id}")
                for pain_id in company.service_match.based_on_hypothesis_ids:
                    if pain_id not in pain_by_id:
                        errors.append(
                            f"{prefix}.service_match references missing hypothesis {pain_id}"
                        )
        if company.contact:
            contact = company.contact
            _validate_timestamp(contact.retrieved_at, f"{prefix}.contact.retrieved_at", errors)
            if contact.permission_basis != ImportPermissionBasis.UNKNOWN:
                errors.append(
                    f"{prefix}.contact.permission_basis must remain unknown in an external import"
                )
            try:
                source_url = _canonical_public_url(str(contact.source_url), synthetic=synthetic)
                matching = [
                    item
                    for item in company.evidence
                    if _canonical_public_url(str(item.source_url), synthetic=synthetic)
                    == source_url
                ]
                if not matching:
                    errors.append(
                        f"{prefix}.contact.source_url must resolve to same-company evidence"
                    )
                validation = validate_public_contact(
                    contact.email,
                    domain,
                    source_url=source_url,
                    extraction_method="mailto"
                    if "mailto" in contact.context.lower()
                    else "visible_text",
                    role=contact.role,
                )
                if not validation.valid:
                    errors.append(f"{prefix}.contact rejected: {validation.reason}")
            except ValueError as exc:
                errors.append(f"{prefix}.contact.source_url: {exc}")
        if company.draft:
            draft = company.draft
            if draft.service_key not in SERVICE_REGISTRY:
                errors.append(f"{prefix}.draft.service_key is not canonical")
            for fact_id in draft.evidence_fact_ids:
                if fact_id not in fact_by_id:
                    errors.append(f"{prefix}.draft references missing fact {fact_id}")
            for pain_id in draft.pain_hypothesis_ids:
                if pain_id not in pain_by_id:
                    errors.append(f"{prefix}.draft references missing hypothesis {pain_id}")
            if any(
                urlparse(url).hostname in _URL_SHORTENERS
                for url in re.findall(r"https?://[^\s<>]+", draft.body)
            ):
                warnings.append(f"{prefix}.draft contains a URL shortener")
        official_sources = [
            item
            for item in company.evidence
            if registrable_domain(str(item.source_url)) == domain
            and item.source_type
            in {
                ImportSourceType.OFFICIAL,
                ImportSourceType.OFFICIAL_CAREERS,
                ImportSourceType.OFFICIAL_NEWS,
            }
        ]
        if not official_sources:
            errors.append(f"{prefix} requires at least one official-domain source")
    if errors:
        raise ImportBridgeError("Research bundle validation failed", errors=errors + warnings)
    return warnings


def _build_draft_validation(
    company: ExternalCompany,
    settings: Settings,
    verification: SourceVerification,
) -> DraftValidationResult | None:
    if company.draft is None:
        return None
    draft = company.draft
    evidence_fact_ids = {fact.fact_id for fact in company.observed_facts}
    linked_fact_ids = [
        fact_id for fact_id in draft.evidence_fact_ids if fact_id in evidence_fact_ids
    ]
    missing_fact_ids = [
        fact_id for fact_id in draft.evidence_fact_ids if fact_id not in evidence_fact_ids
    ]
    evidence_linkage = {
        "referenced_fact_ids": list(draft.evidence_fact_ids),
        "linked_fact_ids": linked_fact_ids,
        "missing_fact_ids": missing_fact_ids,
        "all_linked": not missing_fact_ids and bool(draft.evidence_fact_ids),
    }
    body = draft.body.strip() + "\n\n" + _private_footer(settings)
    content = DraftContent(
        subject=draft.subject,
        body=body,
        html_body=_html_email(body),
        source_fact_ids=list(draft.evidence_fact_ids),
        model="chatgpt_manual",
        prompt_version=f"external-research-{SCHEMA_VERSION}",
    )
    report = check_draft(
        content,
        settings.sender,
        approved_fact_ids=evidence_fact_ids,
        allowed_domains={"elioratechsolutions.com"},
    )
    findings = [
        {"code": item.code, "message": item.message, "severity": item.severity}
        for item in report.findings
    ]
    errors = [item["message"] for item in findings if item["severity"] == "error"]
    warning_findings = [item["message"] for item in findings if item["severity"] == "warning"]
    if missing_fact_ids:
        errors.append(f"Draft references missing fact IDs: {', '.join(missing_fact_ids)}")
    passed = report.passed and bool(evidence_linkage["all_linked"])
    contact_dependent_issues: list[str] = []
    if company.contact is None:
        contact_dependent_issues.append("contact is missing")
    elif verification.status != "verified":
        contact_dependent_issues.append(
            f"contact source verification is {verification.status}: {verification.detail}"
        )
    dispatch_blocked_reasons = [
        "permission_basis=unknown",
        "provider_policy_eligible=false",
    ]
    if company.contact is None:
        dispatch_blocked_reasons.append("contact is missing")
    elif verification.status != "verified":
        dispatch_blocked_reasons.append(f"contact_source_verification={verification.status}")
    return DraftValidationResult(
        external_company_id=company.external_company_id,
        company_name=company.company_name,
        passed=passed,
        findings=findings,
        warnings=warning_findings,
        errors=errors,
        evidence_linkage=evidence_linkage,
        contact_dependent_issues=contact_dependent_issues,
        send_ready=False,
        dispatch_blocked_reasons=dispatch_blocked_reasons,
    )


def _verification_warning(external_company_id: str, verification: SourceVerification) -> str:
    if verification.status == "not_checked":
        return (
            f"companies[{external_company_id}].contact source verification is not checked "
            "without --verify-sources"
        )
    return (
        f"{external_company_id}: contact {verification.status} ({verification.detail}); "
        "kept for review only"
    )


def validate_bundle_file(
    path: Path,
    *,
    verify_sources: bool = False,
    settings: Settings | None = None,
) -> ValidationResult:
    if not path.is_file():
        raise ImportBridgeError(f"Research bundle does not exist: {path}")
    if path.stat().st_size > MAX_BUNDLE_BYTES:
        raise ImportBridgeError(
            f"Research bundle exceeds the {MAX_BUNDLE_BYTES // 1_000_000} MB limit"
        )
    try:
        raw_bytes = path.read_bytes()
        raw = json.loads(raw_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ImportBridgeError(f"Research bundle is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ImportBridgeError("Research bundle top level must be a JSON object")
    _scan_errors: list[str] = []
    _scan_strings(raw, "$", _scan_errors)
    if _scan_errors:
        raise ImportBridgeError("Research bundle contains unsafe text", errors=_scan_errors)
    version = raw.get("schema_version")
    if isinstance(version, str) and version.split(".", 1)[0] != SCHEMA_VERSION.split(".", 1)[0]:
        raise ImportBridgeError(f"Unsupported external research schema major version: {version}")
    try:
        bundle = ExternalResearchBundle.model_validate(raw)
    except ValidationError as exc:
        raise ImportBridgeError(
            "Research bundle has invalid structure", errors=[str(error) for error in exc.errors()]
        ) from exc
    warnings = _validate_bundle(bundle, raw)
    effective_settings = settings or Settings()
    verified_contacts = 0
    contact_verifications: dict[str, SourceVerification] = {}
    crawler: SafeCrawler | None = None
    if verify_sources:
        contact_count = sum(company.contact is not None for company in bundle.companies)
        crawler = SafeCrawler(
            user_agent="EliOra-Outreach-Research/1.0",
            max_requests=min(
                MANUAL_VERIFICATION_MAX_REQUESTS,
                max(MANUAL_VERIFICATION_MIN_REQUESTS, contact_count * 5),
            ),
            max_pages_per_domain=max(1, len(bundle.companies)),
        )
        for company in bundle.companies:
            if company.contact:
                verification = verify_contact_source(company.contact, crawler=crawler)
                contact_verifications[company.external_company_id] = verification
                if verification.status == "verified":
                    verified_contacts += 1
                else:
                    warnings.append(
                        _verification_warning(company.external_company_id, verification)
                    )
    else:
        for company in bundle.companies:
            if company.contact:
                verification = SourceVerification("not_checked", "Verification was not requested")
                contact_verifications[company.external_company_id] = verification
                warnings.append(_verification_warning(company.external_company_id, verification))
    draft_validations = [
        draft_validation
        for company in bundle.companies
        if (
            draft_validation := _build_draft_validation(
                company,
                effective_settings,
                contact_verifications.get(
                    company.external_company_id,
                    SourceVerification("not_checked", "Verification was not requested"),
                ),
            )
        )
        is not None
    ]
    return ValidationResult(
        bundle=bundle,
        bundle_hash=_json_hash(raw),
        filename=path.name,
        warnings=warnings,
        verified_contacts=verified_contacts,
        verification_requested=verify_sources,
        contact_verifications=contact_verifications,
        draft_validations=draft_validations,
    )


def template_bundle() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "bundle_type": BUNDLE_TYPE,
        "generated_at": "2026-08-09T18:00:00-04:00",
        "generated_by": {
            "system": "EliOra educational template",
            "method": "synthetic_template",
            "notes": "Synthetic example only. Do not import as a real prospect bundle.",
        },
        "research_scope": {
            "geography": "US",
            "target_company_profile": "Synthetic educational example",
            "verticals": ["healthcare"],
            "max_companies": 1,
        },
        "companies": [
            {
                "external_company_id": "acme-health-demo",
                "company_name": "Acme Health Demo",
                "official_domain": "acme-health.example",
                "official_website": "https://acme-health.example",
                "industry": "Healthcare",
                "vertical": "healthcare",
                "location": {"city": "Phoenix", "state": "AZ", "country": "US"},
                "employee_estimate": {
                    "value": 180,
                    "confidence": "medium",
                    "evidence_ids": ["ev-1"],
                },
                "discovery": {
                    "why_selected": "Synthetic example for validation and dashboard testing.",
                    "signal_category": "healthcare_admin",
                    "signal_date": "2026-07-20T00:00:00-04:00",
                    "signal_freshness": "strong",
                },
                "evidence": [
                    {
                        "evidence_id": "ev-1",
                        "source_url": "https://acme-health.example/careers",
                        "source_title": "Synthetic careers page",
                        "publisher": "Acme Health Demo",
                        "source_type": "official_careers",
                        "source_tier": "A",
                        "published_at": None,
                        "retrieved_at": "2026-08-09T17:30:00-04:00",
                        "excerpt": "Synthetic source excerpt only.",
                        "claims_supported": ["fact-1"],
                    }
                ],
                "observed_facts": [
                    {
                        "fact_id": "fact-1",
                        "statement": "Acme Health Demo lists a synthetic operations role.",
                        "evidence_ids": ["ev-1"],
                        "confidence": "high",
                    }
                ],
                "pain_hypotheses": [
                    {
                        "hypothesis_id": "pain-1",
                        "statement": "The role may indicate recurring reporting coordination work.",
                        "confidence": "medium",
                        "based_on_fact_ids": ["fact-1"],
                        "reason": "Synthetic rationale for education.",
                    }
                ],
                "service_match": {
                    "service_key": "healthcare_administration",
                    "service_name": "Healthcare Administration Workflow",
                    "public_url": "https://elioratechsolutions.com",
                    "why_fit": "Synthetic service mapping.",
                    "based_on_fact_ids": ["fact-1"],
                    "based_on_hypothesis_ids": ["pain-1"],
                },
                "contact": {
                    "email": "operations@acme-health.example",
                    "name": None,
                    "role": "Operations",
                    "contact_type": "functional_inbox",
                    "source_url": "https://acme-health.example/careers",
                    "source_title": "Synthetic careers page",
                    "context": "Synthetic operations contact; educational only.",
                    "retrieved_at": "2026-08-09T17:40:00-04:00",
                    "permission_basis": "unknown",
                },
                "draft": {
                    "subject": "A synthetic research draft",
                    "body": "This is an educational draft for local validation only.",
                    "evidence_fact_ids": ["fact-1"],
                    "pain_hypothesis_ids": ["pain-1"],
                    "service_key": "healthcare_administration",
                    "cta_type": "reply",
                    "meeting_link_used": False,
                },
            }
        ],
    }


def generation_prompt(max_companies: int = 5) -> str:
    service_keys = ", ".join(sorted(SERVICE_REGISTRY))
    return f"""You are preparing an EliOra external research bundle for downstream local validation.

Research up to {max_companies} real US companies relevant to EliOra's canonical services. Use current public web research, prioritizing official company, careers, government, regulator, and reputable trade/news sources. Output JSON only matching schema_version {SCHEMA_VERSION} and bundle_type {BUNDLE_TYPE}.

Rules:
- Preserve evidence URLs and short excerpts; every observed fact must reference evidence IDs.
- Keep pain hypotheses tentative and separately linked to facts; do not include hidden chain-of-thought.
- Find only explicitly published official-domain business contacts. Never guess an email, scrape LinkedIn, use brokers, probe SMTP, or use personal mailboxes.
- Set contact.permission_basis to "unknown". Never include auto_send, dispatch_eligible, provider_allowed, suppression, or final score fields.
- Do not fabricate dates, employee counts, metrics, company facts, or publication dates. Use null where unknown.
- Use only these canonical service keys: {service_keys}. Use the exact service name/public URL from the schema guidance.
- Output JSON only; no markdown fences and no commentary.

Generate a strict {BUNDLE_TYPE} object with all required provenance and timestamps carrying timezone offsets."""


def _verification_exception_detail(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int):
        return f"HTTP {status_code}"
    if isinstance(exc, httpx.TooManyRedirects):
        return "redirect blocked (too many redirects)"
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, (ssl.SSLError,)):
        return "TLS failure"
    chain: list[BaseException] = []
    current: BaseException | None = exc
    while current is not None and len(chain) < 4:
        chain.append(current)
        current = current.__cause__ or current.__context__
    chain_types = {type(item) for item in chain}
    if socket.gaierror in chain_types:
        return "DNS resolution failure"
    text = " ".join(str(item).lower() for item in chain)
    if any(token in text for token in ("certificate", "ssl", "tls")):
        return "TLS failure"
    if any(
        token in text
        for token in ("name or service not known", "nodename nor servname", "getaddrinfo")
    ):
        return "DNS resolution failure"
    if isinstance(exc, httpx.NetworkError):
        return "connection error"
    if isinstance(exc, ValueError) and "redirect" in str(exc).lower():
        return "redirect blocked"
    if isinstance(exc, RuntimeError) and "request budget" in str(exc).lower():
        return "request budget exhausted"
    return type(exc).__name__


def verify_contact_source(
    contact: ContactImport, *, crawler: SafeCrawler | None = None
) -> SourceVerification:
    crawler = crawler or SafeCrawler(
        user_agent="EliOra-Outreach-Research/1.0", max_requests=1, max_pages_per_domain=1
    )
    try:
        page = crawler.fetch(str(contact.source_url))
    except CrawlerBudgetExceeded:
        return SourceVerification(
            "verification_budget_exhausted",
            "bounded verification HTTP request budget exhausted",
        )
    except PermissionError as exc:
        detail = "robots restriction"
        if "redirect" in str(exc).lower():
            detail = "redirect blocked by robots policy"
        return SourceVerification("robots_blocked", detail)
    except Exception as exc:
        detail = _verification_exception_detail(exc)
        status = (
            "redirect_blocked" if detail.startswith("redirect blocked") else "source_unreachable"
        )
        return SourceVerification(status, detail)
    haystack = f"{page.raw_html} {page.text}".lower()
    if contact.email.lower() not in haystack:
        return SourceVerification(
            "not_found_on_source", "Email was not visible on the fetched source"
        )
    return SourceVerification("verified", "Email was visible on the fetched public source")


def verify_import_contacts(database: Database, import_id: str) -> dict[str, Any]:
    """Recheck only contacts belonging to one persisted external import.

    This operation changes verification metadata and audit events only. It never
    changes permission basis or creates an outbox row.
    """
    now = datetime.now(timezone.utc)
    database.create()
    with database.session() as session:
        record = session.get(ImportRecord, import_id)
        if record is None:
            raise ImportBridgeError(f"Import record not found: {import_id}")
        contacts = (
            session.query(Contact)
            .join(Source, Contact.source_id == Source.id)
            .filter(Source.originating_run_id == record.run_id)
            .order_by(Contact.email)
            .all()
        )
        crawler = SafeCrawler(
            user_agent="EliOra-Outreach-Research/1.0",
            max_requests=min(
                MANUAL_VERIFICATION_MAX_REQUESTS,
                max(MANUAL_VERIFICATION_MIN_REQUESTS, len(contacts) * 5),
            ),
            max_pages_per_domain=max(1, len(contacts)),
        )
        results: list[dict[str, str]] = []
        for contact in contacts:
            contact_import = ContactImport.model_validate(
                {
                    "email": contact.email,
                    "name": contact.display_name,
                    "role": contact.title,
                    "contact_type": ImportContactType.GENERAL_BUSINESS_INBOX,
                    "source_url": contact.source_url,
                    "source_title": contact.source_title or "Imported public contact source",
                    "context": contact.source_context or "Imported public contact source",
                    "retrieved_at": contact.first_seen_at,
                    "permission_basis": ImportPermissionBasis.UNKNOWN,
                }
            )
            verification = verify_contact_source(contact_import, crawler=crawler)
            contact.source_verification_status = verification.status
            contact.source_verification_checked_at = now
            contact.source_verification_reason = verification.detail
            contact.last_verified_at = now if verification.status == "verified" else None
            # Verification is provenance, not permission or recipient approval.
            contact.appropriateness_status = "review"
            contact.appropriateness_reason = (
                f"Public-source verification={verification.status}; {verification.detail}"
            )
            result = {
                "email": contact.email,
                "status": verification.status,
                "reason": verification.detail,
                "checked_at": now.isoformat(),
            }
            results.append(result)
            session.add(
                AuditEvent(
                    actor="owner",
                    action="external_research_contact_verification_checked",
                    entity_type="contact",
                    entity_id=contact.id,
                    metadata_json={"import_id": import_id, **result},
                )
            )
        verified = sum(item["status"] == "verified" for item in results)
        record.contacts_verified = verified
        record.contacts_unverified = len(results) - verified
        session.add(
            AuditEvent(
                actor="owner",
                action="external_research_contacts_verified",
                entity_type="research_import",
                entity_id=import_id,
                metadata_json={
                    "import_id": import_id,
                    "checked_at": now.isoformat(),
                    "contacts_checked": len(results),
                    "contacts_verified": verified,
                    "contacts_unverified": len(results) - verified,
                    "results": results,
                    "outbox_rows_created": 0,
                },
            )
        )
        return {
            "status": "completed",
            "import_id": import_id,
            "contacts_checked": len(results),
            "contacts_verified": verified,
            "contacts_unverified": len(results) - verified,
            "results": results,
            "outbox_rows_created": 0,
        }


def _private_footer(settings: Settings) -> str:
    return (
        f"{settings.sender.disclosure}\n{settings.sender.postal_address}\n{settings.sender.opt_out}"
    )


def _html_email(body: str) -> str:
    return "".join(
        f"<p>{html.escape(part).replace(chr(10), '<br>')}</p>" for part in body.split("\n\n")
    )


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()


def _source_quality(tier: ImportSourceTier, official: bool) -> float:
    base = {ImportSourceTier.A: 0.95, ImportSourceTier.B: 0.8, ImportSourceTier.C: 0.6}[tier]
    return min(1.0, base + (0.05 if official else 0.0))


def _active_suppressed(session: Any, company: Company, email: str | None) -> bool:
    values = {company.registrable_domain.lower()}
    if email:
        values.add(email.lower())
    return bool(
        session.scalar(
            select(Suppression.id).where(
                Suppression.removed_at.is_(None), Suppression.normalized_value.in_(values)
            )
        )
    )


def _existing_or_new_source(
    session: Any,
    company: Company,
    item: Evidence,
    canonical_url: str,
    run_id: str,
    now: datetime,
    freshness: ImportFreshness,
) -> Source:
    source = session.scalar(
        select(Source).where(
            Source.company_id == company.id, Source.canonical_url_hash == url_hash(canonical_url)
        )
    )
    if source:
        return source
    official = registrable_domain(canonical_url) == company.registrable_domain
    source_type = _SOURCE_MAP[item.source_type]
    source = Source(
        company_id=company.id,
        url=canonical_url,
        canonical_url_hash=url_hash(canonical_url),
        source_type=source_type.value,
        title=item.source_title,
        publisher=item.publisher,
        publication_date=(
            datetime.combine(item.published_at, time.min, tzinfo=timezone.utc)
            if item.published_at
            else None
        ),
        retrieved_at=item.retrieved_at,
        content_hash=_fingerprint(item.excerpt),
        excerpt=item.excerpt,
        source_quality=_source_quality(item.source_tier, official),
        robots_result="not_checked",
        http_status=None,
        retention_until=None,
        data_origin="external_research",
        originating_run_id=run_id,
        originating_query=company.discovery_query,
        source_tier=item.source_tier.value,
        freshness_category=freshness.value,
        claim_type="observed_fact",
        date_confidence="known" if item.published_at else "unknown",
    )
    session.add(source)
    session.flush()
    return source


def import_bundle(
    database: Database,
    settings: Settings,
    validation: ValidationResult,
    *,
    confirmation_at: datetime | None = None,
    verify_sources: bool = False,
) -> dict[str, Any]:
    bundle = validation.bundle
    if bundle.generated_by.method == "synthetic_template":
        raise ImportBridgeError(
            "Synthetic educational templates cannot be imported as real external research"
        )
    if verify_sources and not validation.verification_requested:
        contact_count = sum(company.contact is not None for company in bundle.companies)
        crawler = SafeCrawler(
            user_agent="EliOra-Outreach-Research/1.0",
            max_requests=min(
                MANUAL_VERIFICATION_MAX_REQUESTS,
                max(MANUAL_VERIFICATION_MIN_REQUESTS, contact_count * 5),
            ),
            max_pages_per_domain=max(1, len(bundle.companies)),
        )
        refreshed_warnings = [
            warning
            for warning in validation.warnings
            if "source verification is not checked without --verify-sources" not in warning
        ]
        contact_verifications: dict[str, SourceVerification] = {}
        verified_contacts = 0
        for external_company in bundle.companies:
            if external_company.contact:
                verification = verify_contact_source(external_company.contact, crawler=crawler)
                contact_verifications[external_company.external_company_id] = verification
                if verification.status == "verified":
                    verified_contacts += 1
                else:
                    refreshed_warnings.append(
                        _verification_warning(external_company.external_company_id, verification)
                    )
        validation.verification_requested = True
        validation.contact_verifications = contact_verifications
        validation.verified_contacts = verified_contacts
        validation.warnings = refreshed_warnings
        validation.draft_validations = [
            draft_validation
            for company in bundle.companies
            if (
                draft_validation := _build_draft_validation(
                    company,
                    settings,
                    contact_verifications.get(
                        company.external_company_id,
                        SourceVerification("not_checked", "Verification was not requested"),
                    ),
                )
            )
            is not None
        ]
    now = datetime.now(timezone.utc)
    database.create()
    with database.session() as session:
        existing_import = session.scalar(
            select(ImportRecord).where(ImportRecord.bundle_hash == validation.bundle_hash)
        )
        if existing_import:
            return {
                "status": "already_imported",
                "import_id": existing_import.id,
                "bundle_hash": validation.bundle_hash,
                "prospect_messages_sent": 0,
            }
        run_id = str(uuid.uuid4())
        run = Run(
            id=run_id,
            run_key=f"import:{validation.bundle_hash}",
            logical_run_key=f"import:{validation.bundle_hash}",
            attempt_number=1,
            run_type=RunType.RESEARCH_IMPORT.value,
            run_mode="manual_import",
            data_origin="external_research",
            research_provider="chatgpt_manual",
            status=RunStatus.SUCCESS.value,
            started_at=now,
            finished_at=now,
            counters={
                "companies": 0,
                "evidence": 0,
                "contacts": 0,
                "drafts": 0,
                "prospect_messages_sent": 0,
            },
        )
        session.add(run)
        session.flush()
        warnings = list(validation.warnings)
        contacts_verified = contacts_unverified = 0
        drafts_ready = validation.preview["drafts_passing_validation"]
        drafts_review = validation.preview["drafts_needing_review"]
        drafts_persisted = 0
        evidence_count = 0
        accepted = 0
        for external in bundle.companies:
            draft_validation = validation.draft_validation_by_company.get(
                external.external_company_id
            )
            domain = registrable_domain(external.official_domain)
            company = session.scalar(select(Company).where(Company.registrable_domain == domain))
            if company and company.data_origin == "synthetic":
                raise ImportBridgeError(
                    f"Cannot convert synthetic company to external research: {domain}"
                )
            official_url = _canonical_public_url(str(external.official_website), synthetic=False)
            if company is None:
                company = Company(
                    name=external.company_name,
                    registrable_domain=domain,
                    official_website=official_url,
                    country=external.location.country or "United States",
                    state=external.location.state,
                    city=external.location.city,
                    vertical=external.vertical.value,
                    employee_band=str(external.employee_estimate.value)
                    if external.employee_estimate and external.employee_estimate.value
                    else None,
                    permission_basis="unknown",
                    data_origin="external_research",
                    official_domain_confidence=0.8,
                    domain_confidence_reason="External bundle supplied matching official-domain evidence; no live DNS claim was made.",
                    verified_at=None,
                    discovery_query=external.discovery.discovery_query,
                )
                session.add(company)
                session.flush()
            else:
                company.data_origin = "external_research"
                company.last_researched_at = now
                company.permission_basis = "unknown"
                company.discovery_query = external.discovery.discovery_query
            company.last_researched_at = now
            evidence_map: dict[str, Source] = {}
            for item in external.evidence:
                canonical = _canonical_public_url(str(item.source_url), synthetic=False)
                evidence_map[item.evidence_id] = _existing_or_new_source(
                    session,
                    company,
                    item,
                    canonical,
                    run_id,
                    now,
                    external.discovery.signal_freshness,
                )
                evidence_count += 1
            fact_signal_map: dict[str, Signal] = {}
            for fact in external.observed_facts:
                source = evidence_map[fact.evidence_ids[0]]
                signal = session.scalar(
                    select(Signal).where(
                        Signal.company_id == company.id, Signal.observed_signal == fact.statement
                    )
                )
                if signal is None:
                    signal = Signal(
                        company_id=company.id,
                        source_id=source.id,
                        signal_type=_signal_type(external.discovery.signal_category).value,
                        observed_signal=fact.statement,
                        signal_date=(
                            datetime.combine(
                                external.discovery.signal_date, time.min, tzinfo=timezone.utc
                            )
                            if external.discovery.signal_date
                            else None
                        ),
                        freshness_days=(now.date() - external.discovery.signal_date).days
                        if external.discovery.signal_date
                        else None,
                        confidence=_confidence(fact.confidence),
                        extracted_at=now,
                        data_origin="external_research",
                        originating_run_id=run_id,
                    )
                    session.add(signal)
                    session.flush()
                fact_signal_map[fact.fact_id] = signal
            pain_models: list[PainHypothesis] = []
            for pain in external.pain_hypotheses:
                supporting_ids = [fact_signal_map[fact_id].id for fact_id in pain.based_on_fact_ids]
                pain_row = session.scalar(
                    select(PainRow).where(
                        PainRow.company_id == company.id, PainRow.hypothesis == pain.statement
                    )
                )
                service_name = (
                    SERVICE_REGISTRY[external.service_match.service_key][0]
                    if external.service_match
                    else "Reporting Automation Sprint"
                )
                if pain_row is None:
                    pain_row = PainRow(
                        company_id=company.id,
                        category=_signal_type(external.discovery.signal_category).value,
                        hypothesis=pain.statement,
                        confidence=_confidence(pain.confidence),
                        service_mapping=service_name,
                        supporting_signal_ids=supporting_ids,
                        created_at=now,
                        data_origin="external_research",
                        originating_run_id=run_id,
                    )
                    session.add(pain_row)
                    session.flush()
                pain_models.append(
                    PainHypothesis(
                        id=pain_row.id,
                        company_id=company.id,
                        category=_signal_type(external.discovery.signal_category),
                        pain_hypothesis=pain_row.hypothesis,
                        confidence=pain_row.confidence,
                        service_match=pain_row.service_mapping,
                        supporting_signal_ids=supporting_ids,
                    )
                )
            contact_model: ContactRecord | None = None
            contact: Contact | None = None
            if external.contact:
                imported_contact = external.contact
                canonical_contact_url = _canonical_public_url(
                    str(imported_contact.source_url), synthetic=False
                )
                contact_source: Source | None = next(
                    (item for item in evidence_map.values() if item.url == canonical_contact_url),
                    None,
                )
                if contact_source is None:
                    raise ImportBridgeError(
                        f"Contact source was not persisted for {external.external_company_id}"
                    )
                validation_result: ContactValidation = validate_public_contact(
                    imported_contact.email,
                    domain,
                    source_url=canonical_contact_url,
                    extraction_method="mailto"
                    if "mailto" in imported_contact.context.lower()
                    else "visible_text",
                    role=imported_contact.role,
                )
                if not validation_result.valid:
                    raise ImportBridgeError(
                        f"Contact rejected for {domain}: {validation_result.reason}"
                    )
                verification = validation.contact_verifications.get(
                    external.external_company_id,
                    SourceVerification("not_checked", "Verification was not requested"),
                )
                if verification.status == "verified":
                    contacts_verified += 1
                else:
                    contacts_unverified += 1
                contact = session.scalar(
                    select(Contact).where(Contact.email == validation_result.email)
                )
                if contact and contact.company_id != company.id:
                    raise ImportBridgeError(
                        f"Contact email already belongs to another company: {validation_result.email}"
                    )
                if contact is None:
                    contact = Contact(
                        company_id=company.id,
                        email=validation_result.email,
                        display_name=imported_contact.name,
                        title=imported_contact.role,
                        source_id=contact_source.id,
                        source_url=canonical_contact_url,
                        extraction_method="mailto"
                        if "mailto" in imported_contact.context.lower()
                        else "visible_text",
                        official_domain=True,
                        role_inbox_category=validation_result.category,
                        syntactic_valid=True,
                        mx_valid=None,
                        mx_result="not_checked",
                        appropriateness_status="review",
                        appropriateness_reason=f"{validation_result.reason}; source verification={verification.status}",
                        first_seen_at=now,
                        last_verified_at=now if verification.status == "verified" else None,
                        data_origin="external_research",
                        source_title=imported_contact.source_title,
                        source_context=imported_contact.context,
                        no_guessed_address=True,
                        source_verification_status=verification.status,
                        source_verification_checked_at=now
                        if verification.status != "not_checked"
                        else None,
                        source_verification_reason=verification.detail,
                    )
                    session.add(contact)
                    session.flush()
                else:
                    contact.source_verification_status = verification.status
                    contact.source_verification_checked_at = (
                        now if verification.status != "not_checked" else None
                    )
                    contact.source_verification_reason = verification.detail
                    contact.last_verified_at = now if verification.status == "verified" else None
                    contact.appropriateness_status = "review"
                    contact.appropriateness_reason = (
                        f"{validation_result.reason}; source verification={verification.status}"
                    )
                contact_model = ContactRecord.model_validate(
                    {
                        "id": contact.id,
                        "company_id": company.id,
                        "email": contact.email,
                        "source_id": contact.source_id,
                        "source_url": contact.source_url,
                        "extraction_method": contact.extraction_method,
                        "display_name": contact.display_name,
                        "role": contact.title,
                        "official_domain": contact.official_domain,
                        "syntactic_valid": contact.syntactic_valid,
                        "mx_valid": contact.mx_valid,
                        "appropriateness_status": contact.appropriateness_status,
                        "appropriateness_reason": contact.appropriateness_reason,
                        "contact_quality": validation_result.quality,
                    }
                )
            imported_sources = [
                SourceEvidence.model_validate(
                    {
                        "id": source.id,
                        "url": source.url,
                        "title": source.title,
                        "publisher": source.publisher,
                        "source_type": SourceType(source.source_type),
                        "retrieved_at": source.retrieved_at,
                        "publication_date": source.publication_date.date()
                        if source.publication_date
                        else None,
                        "excerpt": source.excerpt,
                        "source_quality": source.source_quality,
                        "source_tier": source.source_tier,
                        "freshness_category": source.freshness_category,
                        "claim_type": source.claim_type,
                        "date_confidence": source.date_confidence,
                        "run_id": run_id,
                    }
                )
                for source in evidence_map.values()
            ]
            score = score_lead(
                LeadInputs(
                    country=company.country,
                    employee_band=company.employee_band,
                    sources=imported_sources,
                    fresh_signal_count=sum(
                        1
                        for fact in external.observed_facts
                        if external.discovery.signal_date
                        and (now.date() - external.discovery.signal_date).days
                        <= settings.targeting.fresh_signal_days
                    ),
                    service_fit=20 if external.service_match else 0,
                    hypotheses=pain_models,
                    contact=contact_model,
                    active_suppression=_active_suppressed(
                        session, company, external.contact.email if external.contact else None
                    ),
                    research_confidence=max(
                        (_confidence(fact.confidence) for fact in external.observed_facts),
                        default=0,
                    ),
                    permission_basis="unknown",
                    provider_policy_eligible=False,
                    official_domain_verified=True,
                    contact_source_complete=bool(contact_model and contact_model.source_url),
                    data_origin="external_research",
                ),
                settings.targeting,
                today=now.date(),
            )
            commercial_score = commercial_score_for_records(
                company,
                list(evidence_map.values()),
                list(fact_signal_map.values()),
                pain_models,
                contact,
                today=now.date(),
            )
            active_suppression = _active_suppressed(
                session, company, external.contact.email if external.contact else None
            )
            eligibility = evaluate_dispatch_eligibility(
                settings,
                permission_basis="unknown",
                provider_policy_eligible=False,
                contact_valid=bool(
                    contact_model
                    and contact_model.syntactic_valid
                    and contact_model.appropriateness_status == "eligible"
                ),
                official_domain=bool(contact_model and contact_model.official_domain),
                no_guessed_address=True,
                draft_status=(
                    "approved"
                    if draft_validation and draft_validation.passed
                    else "needs_review"
                    if external.draft
                    else "missing"
                ),
                active_suppression=active_suppression,
                data_origin="external_research",
            )
            score_explanation = {
                **score.explanation,
                "centralized_eligibility": {
                    "allowed": eligibility.allowed,
                    "reason": eligibility.reason,
                    "provider_policy_eligible": eligibility.provider_policy_eligible,
                },
            }
            lead_score = LeadScore(
                company_id=company.id,
                score_version=score.score_version,
                icp_score=score.company_fit,
                intent_score=score.intent,
                service_fit_score=score.service_fit,
                evidence_quality_score=score.evidence_quality,
                contact_quality_score=score.contact_quality,
                penalties=score.penalties,
                total_score=score.total,
                disposition=score.disposition.value,
                explanation={
                    **score_explanation,
                    "external_research": {"bundle_hash": validation.bundle_hash},
                },
                scored_at=now,
                data_origin="external_research",
            )
            apply_commercial_score(lead_score, commercial_score)
            session.add(lead_score)
            if external.draft:
                draft_source_ids = [
                    fact_signal_map[fact_id].id for fact_id in external.draft.evidence_fact_ids
                ]
                body = external.draft.body.strip() + "\n\n" + _private_footer(settings)
                content = DraftContent(
                    subject=external.draft.subject,
                    body=body,
                    html_body=_html_email(body),
                    source_fact_ids=draft_source_ids,
                    model="chatgpt_manual",
                    prompt_version=f"external-research-{SCHEMA_VERSION}",
                )
                if draft_validation is None:
                    raise ImportBridgeError(
                        f"Missing deterministic draft validation for {external.external_company_id}"
                    )
                status = "approved" if draft_validation.passed else "needs_review"
                drafts_persisted += 1
                session.add(
                    Draft(
                        company_id=company.id,
                        contact_id=contact_model.id if contact_model else None,
                        sequence_step=1,
                        subject=content.subject,
                        plain_text_body=content.body,
                        html_body=content.html_body,
                        source_facts_used=draft_source_ids,
                        model=content.model,
                        prompt_version=content.prompt_version,
                        content_hash=hashlib.sha256(content.body.encode()).hexdigest(),
                        quality_findings=draft_validation.quality_findings(),
                        status=status,
                        created_at=now,
                        updated_at=now,
                        data_origin="external_research",
                        run_id=run_id,
                    )
                )
            session.add(
                AuditEvent(
                    actor="owner",
                    action="external_research_company_imported",
                    entity_type="company",
                    entity_id=company.id,
                    metadata_json={
                        "import_id": run_id,
                        "bundle_hash": validation.bundle_hash,
                        "external_company_id": external.external_company_id,
                        "draft_validation": (
                            draft_validation.as_dict() if draft_validation else None
                        ),
                    },
                )
            )
            accepted += 1
        record = ImportRecord(
            id=str(uuid.uuid4()),
            run_id=run.id,
            bundle_hash=validation.bundle_hash,
            schema_version=bundle.schema_version,
            generated_at=bundle.generated_at,
            imported_at=now,
            source_system=bundle.generated_by.system,
            source_method=bundle.generated_by.method,
            filename=validation.filename,
            company_count=len(bundle.companies),
            accepted_count=accepted,
            rejected_count=0,
            warning_count=len(warnings),
            warnings=warnings,
            evidence_count=evidence_count,
            contacts_verified=contacts_verified,
            contacts_unverified=contacts_unverified,
            drafts_ready=drafts_ready,
            drafts_needs_review=drafts_review,
            prospect_messages_sent=0,
            confirmation_at=confirmation_at,
            status="success",
        )
        session.add(record)
        run.counters = {
            "companies": accepted,
            "evidence": evidence_count,
            "contacts_verified": contacts_verified,
            "contacts_unverified": contacts_unverified,
            "drafts_ready": drafts_ready,
            "drafts_needs_review": drafts_review,
            "drafts_passing_validation": drafts_ready,
            "drafts_send_ready": validation.preview["drafts_send_ready"],
            "drafts_persisted": drafts_persisted,
            "prospect_messages_sent": 0,
        }
        session.add(
            AuditEvent(
                actor="owner",
                action="external_research_imported",
                entity_type="research_import",
                entity_id=record.id,
                metadata_json={
                    "bundle_hash": validation.bundle_hash,
                    "companies": accepted,
                    "drafts_passing_validation": drafts_ready,
                    "drafts_needing_review": drafts_review,
                    "drafts_send_ready": validation.preview["drafts_send_ready"],
                    "drafts_persisted": drafts_persisted,
                    "draft_validation": [item.as_dict() for item in validation.draft_validations],
                    "prospect_messages_sent": 0,
                },
            )
        )
        return {
            "status": "imported",
            "import_id": record.id,
            "run_id": run.id,
            "bundle_hash": validation.bundle_hash,
            "companies": accepted,
            "evidence": evidence_count,
            "contacts_verified": contacts_verified,
            "contacts_unverified": contacts_unverified,
            "drafts_ready": drafts_ready,
            "drafts_needs_review": drafts_review,
            "drafts_passing_validation": drafts_ready,
            "drafts_needing_review": drafts_review,
            "drafts_send_ready": validation.preview["drafts_send_ready"],
            "drafts_persisted": drafts_persisted,
            "warnings": len(warnings),
            "prospect_messages_sent": 0,
        }


def reconcile_import_drafts(
    database: Database,
    settings: Settings,
    import_id: str,
    validation: ValidationResult,
) -> dict[str, Any]:
    """Materialize missing drafts for an existing import without re-importing it."""
    if validation.bundle.generated_by.method == "synthetic_template":
        raise ImportBridgeError("Synthetic educational templates cannot reconcile a real import")
    database.create()
    now = datetime.now(timezone.utc)
    with database.session() as session:
        record = session.get(ImportRecord, import_id)
        if record is None:
            raise ImportBridgeError(f"Import record not found: {import_id}")
        if record.bundle_hash != validation.bundle_hash:
            raise ImportBridgeError(
                "Reconciliation bundle hash does not match the existing import record"
            )
        if record.run_id is None:
            raise ImportBridgeError("Existing import has no associated run")
        added: list[str] = []
        for external in validation.bundle.companies:
            domain = registrable_domain(external.official_domain)
            company = session.scalar(select(Company).where(Company.registrable_domain == domain))
            if company is None or external.draft is None:
                continue
            draft_validation = validation.draft_validation_by_company.get(
                external.external_company_id
            )
            if draft_validation is None:
                raise ImportBridgeError(
                    f"Missing deterministic draft validation for {external.external_company_id}"
                )
            signals = session.query(Signal).filter(Signal.company_id == company.id).all()
            signal_by_statement = {signal.observed_signal: signal for signal in signals}
            try:
                draft_source_ids = [
                    signal_by_statement[fact.statement].id
                    for fact in external.observed_facts
                    if fact.fact_id in external.draft.evidence_fact_ids
                ]
            except KeyError as exc:
                raise ImportBridgeError(
                    f"Existing normalized evidence is incomplete for {external.external_company_id}"
                ) from exc
            if not draft_source_ids:
                raise ImportBridgeError(
                    f"No normalized source facts found for {external.external_company_id}"
                )
            body = external.draft.body.strip() + "\n\n" + _private_footer(settings)
            content_hash = hashlib.sha256(body.encode()).hexdigest()
            existing = session.scalar(
                select(Draft).where(
                    Draft.company_id == company.id, Draft.content_hash == content_hash
                )
            )
            if existing:
                continue
            contact = session.scalar(select(Contact).where(Contact.company_id == company.id))
            session.add(
                Draft(
                    company_id=company.id,
                    contact_id=contact.id if contact else None,
                    sequence_step=1,
                    subject=external.draft.subject,
                    plain_text_body=body,
                    html_body=_html_email(body),
                    source_facts_used=draft_source_ids,
                    model="chatgpt_manual",
                    prompt_version=f"external-research-{SCHEMA_VERSION}",
                    content_hash=content_hash,
                    quality_findings=draft_validation.quality_findings(),
                    status="approved" if draft_validation.passed else "needs_review",
                    created_at=now,
                    updated_at=now,
                    data_origin="external_research",
                    run_id=record.run_id,
                )
            )
            added.append(external.external_company_id)
        session.flush()
        persisted = session.query(Draft).filter(Draft.run_id == record.run_id).count()
        record.drafts_ready = validation.preview["drafts_passing_validation"]
        record.drafts_needs_review = validation.preview["drafts_needing_review"]
        run = session.get(Run, record.run_id)
        if run:
            counters = dict(run.counters or {})
            counters.update(
                {
                    "drafts_ready": record.drafts_ready,
                    "drafts_needs_review": record.drafts_needs_review,
                    "drafts_passing_validation": record.drafts_ready,
                    "drafts_send_ready": validation.preview["drafts_send_ready"],
                    "drafts_persisted": persisted,
                    "prospect_messages_sent": 0,
                }
            )
            run.counters = counters
        session.add(
            AuditEvent(
                actor="owner",
                action="external_research_import_reconciled",
                entity_type="research_import",
                entity_id=import_id,
                metadata_json={
                    "import_id": import_id,
                    "bundle_hash": validation.bundle_hash,
                    "drafts_added": added,
                    "drafts_added_count": len(added),
                    "drafts_passing_validation": validation.preview["drafts_passing_validation"],
                    "drafts_needing_review": validation.preview["drafts_needing_review"],
                    "drafts_persisted": persisted,
                    "drafts_send_ready": validation.preview["drafts_send_ready"],
                    "draft_validation": [item.as_dict() for item in validation.draft_validations],
                    "prospect_messages_sent": 0,
                },
            )
        )
        return {
            "status": "reconciled" if added else "already_reconciled",
            "import_id": import_id,
            "bundle_hash": validation.bundle_hash,
            "drafts_added": len(added),
            "drafts_persisted": persisted,
            "drafts_passing_validation": validation.preview["drafts_passing_validation"],
            "drafts_send_ready": validation.preview["drafts_send_ready"],
            "prospect_messages_sent": 0,
        }
