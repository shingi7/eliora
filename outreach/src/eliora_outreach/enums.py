from __future__ import annotations

from enum import StrEnum


class RunType(StrEnum):
    DEMO = "demo"
    PRODUCTION_DRY_RUN = "production_dry_run"
    PRODUCTION_LIVE = "production_live"
    RESEARCH = "research"
    DISPATCH = "dispatch"
    REPLY_SYNC = "reply_sync"
    MANUAL = "manual"
    DRY_RUN = "dry_run"
    OWNER_TEST = "owner_test"
    RESEARCH_IMPORT = "research_import"


class RunStatus(StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    # ``success`` is the persisted value retained for backwards compatibility;
    # this alias makes the terminal state explicit to new callers.
    SUCCEEDED = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    BUDGET_EXHAUSTED = "budget_exhausted"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"
    SKIPPED = "skipped"


class Disposition(StrEnum):
    AUTO_SEND = "auto_send"
    NEEDS_REVIEW = "needs_review"
    NEEDS_CONTACT = "needs_contact"
    ARCHIVE = "archive"
    DISQUALIFIED = "disqualified"


class DraftStatus(StrEnum):
    GENERATED = "generated"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    SENT = "sent"
    SENT_MANUALLY = "sent_manually"


class OutboxState(StrEnum):
    PENDING = "pending"
    LEASED = "leased"
    SENDING = "sending"
    UNCERTAIN = "uncertain"
    SENT = "sent"
    RETRYABLE = "retryable"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SourceType(StrEnum):
    OFFICIAL = "official"
    OFFICIAL_JOB = "official_job"
    OFFICIAL_PRESS = "official_press"
    FILING = "filing"
    REPUTABLE_NEWS = "reputable_news"
    DIRECTORY_HINT = "directory_hint"


class SignalType(StrEnum):
    MANUAL_REPORTING = "manual_reporting"
    DATA_SILOS_AND_INTEGRATION = "data_silos_and_integration"
    DATA_QUALITY_AND_RECONCILIATION = "data_quality_and_reconciliation"
    CASH_FLOW_AND_FORECASTING = "cash_flow_and_forecasting"
    PIPELINE_AND_REVOPS = "pipeline_and_revops"
    SUPPORT_OPERATIONS = "support_operations"
    AI_READINESS_AND_OPERATIONALIZATION = "ai_readiness_and_operationalization"
    GOVERNANCE_COMPLIANCE_AND_AUDITABILITY = "governance_compliance_and_auditability"
    HEALTHCARE_ADMINISTRATION = "healthcare_administration"
    SPORTS_DECISION_INTELLIGENCE = "sports_decision_intelligence"


class EventClass(StrEnum):
    POSITIVE = "positive"
    QUESTION = "question"
    NEUTRAL = "neutral"
    NOT_INTERESTED = "not_interested"
    UNSUBSCRIBE = "unsubscribe"
    OUT_OF_OFFICE = "out_of_office"
    BOUNCE = "bounce"
    HUMAN_OWNER_REPLY = "human_owner_reply"
    AUTOMATED_SEND = "automated_send"
    AMBIGUOUS = "ambiguous"


class SuppressionScope(StrEnum):
    EMAIL = "email"
    DOMAIN = "domain"
    COMPANY = "company"


class SuppressionReason(StrEnum):
    OPT_OUT = "opt_out"
    NOT_INTERESTED = "not_interested"
    BOUNCE = "bounce"
    OWNER = "owner"
    COMPETITOR = "competitor"
    INAPPROPRIATE_CONTACT = "inappropriate_contact"
    LEGAL = "legal"
    DUPLICATE = "duplicate"
