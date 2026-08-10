from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, create_engine, event, text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .paths import AppPaths, default_paths

CURRENT_SCHEMA_VERSION = 8


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class SchemaVersion(Base):
    __tablename__ = "schema_versions"
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    # ``run_key`` remains the unique physical attempt key for compatibility.
    # ``logical_run_key`` groups attempts for daily idempotency.
    logical_run_key: Mapped[str | None] = mapped_column(String(120), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    run_type: Mapped[str] = mapped_column(String(30), index=True)
    run_mode: Mapped[str] = mapped_column(String(30), default="unknown", index=True)
    data_origin: Mapped[str] = mapped_column(String(30), default="production", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="running")
    host: Mapped[str | None] = mapped_column(String(255))
    app_version: Mapped[str | None] = mapped_column(String(80))
    counters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error_summary: Mapped[str | None] = mapped_column(Text)
    error_category: Mapped[str | None] = mapped_column(String(80), index=True)
    retryable: Mapped[bool] = mapped_column(Boolean, default=False)
    retry_not_before: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_request_id: Mapped[str | None] = mapped_column(String(255))
    research_provider: Mapped[str | None] = mapped_column(String(80), index=True)


class Company(Base):
    __tablename__ = "companies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), index=True)
    registrable_domain: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    official_website: Mapped[str] = mapped_column(String(500))
    country: Mapped[str | None] = mapped_column(String(80))
    state: Mapped[str | None] = mapped_column(String(80))
    city: Mapped[str | None] = mapped_column(String(120))
    timezone: Mapped[str] = mapped_column(String(64), default="America/New_York")
    timezone_confidence: Mapped[float] = mapped_column(Float, default=0)
    vertical: Mapped[str] = mapped_column(String(80), index=True)
    employee_band: Mapped[str | None] = mapped_column(String(80))
    lifecycle_status: Mapped[str] = mapped_column(String(30), default="active")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_researched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disqualification_reason: Mapped[str | None] = mapped_column(Text)
    permission_basis: Mapped[str] = mapped_column(String(50), default="unknown", index=True)
    permission_basis_source: Mapped[str | None] = mapped_column(String(1000))
    data_origin: Mapped[str] = mapped_column(String(30), default="production", index=True)
    official_domain_confidence: Mapped[float] = mapped_column(Float, default=0)
    domain_confidence_reason: Mapped[str | None] = mapped_column(String(1000))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discovery_query: Mapped[str | None] = mapped_column(String(1000))


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), index=True)
    url: Mapped[str] = mapped_column(String(1000))
    canonical_url_hash: Mapped[str] = mapped_column(String(64), index=True)
    source_type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(500))
    publisher: Mapped[str] = mapped_column(String(255))
    publication_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    excerpt: Mapped[str] = mapped_column(Text)
    source_quality: Mapped[float] = mapped_column(Float, default=0)
    robots_result: Mapped[str | None] = mapped_column(String(30))
    http_status: Mapped[int | None] = mapped_column(Integer)
    cached_text_path: Mapped[str | None] = mapped_column(String(1000))
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data_origin: Mapped[str] = mapped_column(String(30), default="production", index=True)
    originating_run_id: Mapped[str | None] = mapped_column(String(36), index=True)
    originating_query: Mapped[str | None] = mapped_column(String(1000))
    source_tier: Mapped[str] = mapped_column(String(10), default="C")
    freshness_category: Mapped[str] = mapped_column(String(20), default="unknown")
    claim_type: Mapped[str] = mapped_column(String(30), default="observed_fact")
    date_confidence: Mapped[str] = mapped_column(String(20), default="unknown")
    openai_request_id: Mapped[str | None] = mapped_column(String(255))


class Signal(Base):
    __tablename__ = "signals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), index=True)
    source_id: Mapped[str] = mapped_column(String(36), index=True)
    signal_type: Mapped[str] = mapped_column(String(80), index=True)
    observed_signal: Mapped[str] = mapped_column(Text)
    signal_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    freshness_days: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float] = mapped_column(Float)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    data_origin: Mapped[str] = mapped_column(String(30), default="production", index=True)
    originating_run_id: Mapped[str | None] = mapped_column(String(36), index=True)


class PainHypothesis(Base):
    __tablename__ = "pain_hypotheses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), index=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    hypothesis: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    service_mapping: Mapped[str] = mapped_column(String(255))
    supporting_signal_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    data_origin: Mapped[str] = mapped_column(String(30), default="production", index=True)
    originating_run_id: Mapped[str | None] = mapped_column(String(36), index=True)


class Contact(Base):
    __tablename__ = "contacts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str | None] = mapped_column(String(255))
    source_id: Mapped[str] = mapped_column(String(36), index=True)
    source_url: Mapped[str] = mapped_column(String(1000))
    extraction_method: Mapped[str] = mapped_column(String(30))
    official_domain: Mapped[bool] = mapped_column(Boolean, default=False)
    role_inbox_category: Mapped[str | None] = mapped_column(String(50))
    syntactic_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    mx_valid: Mapped[bool | None] = mapped_column(Boolean)
    mx_result: Mapped[str | None] = mapped_column(String(255))
    appropriateness_status: Mapped[str] = mapped_column(String(30), default="review")
    appropriateness_reason: Mapped[str] = mapped_column(Text, default="")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data_origin: Mapped[str] = mapped_column(String(30), default="production", index=True)
    source_title: Mapped[str | None] = mapped_column(String(500))
    source_context: Mapped[str | None] = mapped_column(String(1000))
    no_guessed_address: Mapped[bool] = mapped_column(Boolean, default=True)
    source_verification_status: Mapped[str] = mapped_column(
        String(30), default="not_checked", index=True
    )
    source_verification_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_verification_reason: Mapped[str | None] = mapped_column(String(255))


class LeadScore(Base):
    __tablename__ = "lead_scores"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), index=True)
    score_version: Mapped[str] = mapped_column(String(40))
    icp_score: Mapped[int] = mapped_column(Integer)
    intent_score: Mapped[int] = mapped_column(Integer)
    service_fit_score: Mapped[int] = mapped_column(Integer)
    evidence_quality_score: Mapped[int] = mapped_column(Integer)
    contact_quality_score: Mapped[int] = mapped_column(Integer)
    penalties: Mapped[list[str]] = mapped_column(JSON, default=list)
    total_score: Mapped[int] = mapped_column(Integer, index=True)
    disposition: Mapped[str] = mapped_column(String(30), index=True)
    explanation: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    data_origin: Mapped[str] = mapped_column(String(30), default="production", index=True)
    opportunity_fit_score: Mapped[int | None] = mapped_column(Integer, index=True)
    opportunity_fit_grade: Mapped[str | None] = mapped_column(String(1), index=True)
    opportunity_fit_version: Mapped[str | None] = mapped_column(String(60))
    opportunity_fit_breakdown_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    reachability_score: Mapped[int | None] = mapped_column(Integer, index=True)
    reachability_grade: Mapped[str | None] = mapped_column(String(1), index=True)
    reachability_version: Mapped[str | None] = mapped_column(String(60))
    reachability_breakdown_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    primary_buyer_persona: Mapped[str | None] = mapped_column(String(80))
    primary_project_type: Mapped[str | None] = mapped_column(String(255))
    project_scope_band: Mapped[str | None] = mapped_column(String(40))
    procurement_friction_band: Mapped[str | None] = mapped_column(String(20))
    priority: Mapped[str | None] = mapped_column(String(80), index=True)


class Draft(Base):
    __tablename__ = "drafts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), index=True)
    contact_id: Mapped[str | None] = mapped_column(String(36), index=True)
    sequence_step: Mapped[int] = mapped_column(Integer)
    subject: Mapped[str] = mapped_column(String(255))
    plain_text_body: Mapped[str] = mapped_column(Text)
    html_body: Mapped[str] = mapped_column(Text)
    source_facts_used: Mapped[list[str]] = mapped_column(JSON, default=list)
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(50))
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    quality_findings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), index=True, default="generated")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    data_origin: Mapped[str] = mapped_column(String(30), default="production", index=True)
    run_id: Mapped[str | None] = mapped_column(String(36), index=True)


class OutboxMessage(Base):
    __tablename__ = "outbox_messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    draft_id: Mapped[str] = mapped_column(String(36), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    # Manual sends may have been recorded before the owner can retrieve the
    # original RFC Message-ID.  Automated rows still receive a deterministic
    # value before transport; NULL is intentionally supported for manual rows.
    message_id: Mapped[str | None] = mapped_column(String(500), unique=True)
    manual_subject: Mapped[str | None] = mapped_column(String(255))
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    state: Mapped[str] = mapped_column(String(30), index=True, default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    lease_owner: Mapped[str | None] = mapped_column(String(255))
    lease_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gmail_message_id: Mapped[str | None] = mapped_column(String(255))
    gmail_thread_id: Mapped[str | None] = mapped_column(String(255))
    api_request_id: Mapped[str | None] = mapped_column(String(255))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_category: Mapped[str | None] = mapped_column(String(80))
    rfc_message_id: Mapped[str | None] = mapped_column(String(500), index=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), index=True)
    provider_thread_id: Mapped[str | None] = mapped_column(String(255), index=True)
    mailbox_uid: Mapped[str | None] = mapped_column(String(100))
    mail_provider: Mapped[str] = mapped_column(String(60), default="namecheap_private_email")
    data_origin: Mapped[str] = mapped_column(String(30), default="production", index=True)


class ThreadEvent(Base):
    __tablename__ = "thread_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    outbox_message_id: Mapped[str | None] = mapped_column(String(36), index=True)
    gmail_message_id: Mapped[str] = mapped_column(String(255), unique=True)
    direction: Mapped[str] = mapped_column(String(20))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    event_class: Mapped[str] = mapped_column(String(40), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=1)
    redacted_summary: Mapped[str] = mapped_column(String(500), default="")
    action_taken: Mapped[str] = mapped_column(String(255), default="")
    provider_message_id: Mapped[str | None] = mapped_column(String(255), index=True)
    mailbox_uid: Mapped[str | None] = mapped_column(String(100))
    mail_provider: Mapped[str] = mapped_column(String(60), default="namecheap_private_email")


class MailboxCheckpoint(Base):
    __tablename__ = "mailbox_checkpoints"
    mail_provider: Mapped[str] = mapped_column(String(60), primary_key=True)
    folder: Mapped[str] = mapped_column(String(255), primary_key=True)
    uid: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Suppression(Base):
    __tablename__ = "suppressions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scope: Mapped[str] = mapped_column(String(20), index=True)
    normalized_value: Mapped[str] = mapped_column(String(500), index=True)
    reason: Mapped[str] = mapped_column(String(80))
    source_event_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removal_reason: Mapped[str | None] = mapped_column(Text)
    data_origin: Mapped[str] = mapped_column(String(30), default="production", index=True)


class DailyUsage(Base):
    __tablename__ = "daily_usage"
    date: Mapped[str] = mapped_column(String(10), primary_key=True)
    timezone: Mapped[str] = mapped_column(String(64), primary_key=True)
    openai_requests: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    web_search_calls: Mapped[int] = mapped_column(Integer, default=0)
    pages_fetched: Mapped[int] = mapped_column(Integer, default=0)
    companies_researched: Mapped[int] = mapped_column(Integer, default=0)
    drafts_generated: Mapped[int] = mapped_column(Integer, default=0)
    initial_messages_sent: Mapped[int] = mapped_column(Integer, default=0)
    followups_sent: Mapped[int] = mapped_column(Integer, default=0)
    total_recipients: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    bounces: Mapped[int] = mapped_column(Integer, default=0)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    actor: Mapped[str] = mapped_column(String(30))
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str | None] = mapped_column(String(36))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ImportRecord(Base):
    __tablename__ = "research_imports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str | None] = mapped_column(String(36), index=True)
    bundle_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    schema_version: Mapped[str] = mapped_column(String(20))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    source_system: Mapped[str] = mapped_column(String(80))
    source_method: Mapped[str] = mapped_column(String(80))
    filename: Mapped[str] = mapped_column(String(255))
    company_count: Mapped[int] = mapped_column(Integer, default=0)
    accepted_count: Mapped[int] = mapped_column(Integer, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, default=0)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    contacts_verified: Mapped[int] = mapped_column(Integer, default=0)
    contacts_unverified: Mapped[int] = mapped_column(Integer, default=0)
    drafts_ready: Mapped[int] = mapped_column(Integer, default=0)
    drafts_needs_review: Mapped[int] = mapped_column(Integer, default=0)
    prospect_messages_sent: Mapped[int] = mapped_column(Integer, default=0)
    confirmation_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="success", index=True)


TABLES = [
    SchemaVersion,
    Run,
    Company,
    Source,
    Signal,
    PainHypothesis,
    Contact,
    LeadScore,
    Draft,
    OutboxMessage,
    ThreadEvent,
    MailboxCheckpoint,
    Suppression,
    DailyUsage,
    AuditEvent,
    ImportRecord,
]


class Database:
    def __init__(self, path: Path | None = None, paths: AppPaths | None = None) -> None:
        self.paths = paths or default_paths()
        self.path = path or self.paths.db
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{self.path}", future=True)
        event.listen(self.engine, "connect", _sqlite_pragmas)
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False)

    def create(self) -> None:
        Base.metadata.create_all(self.engine)
        self._migrate_sqlite_schema()
        with self.session_factory.begin() as session:
            for version in range(1, CURRENT_SCHEMA_VERSION + 1):
                if session.get(SchemaVersion, version) is None:
                    session.add(SchemaVersion(version=version))

    def _migrate_sqlite_schema(self) -> None:
        """Idempotently add provider-neutral columns to databases from version 1."""
        additions: dict[str, dict[str, str]] = {
            "companies": {
                "permission_basis": "VARCHAR(50) NOT NULL DEFAULT 'unknown'",
                "permission_basis_source": "VARCHAR(1000)",
                "data_origin": "VARCHAR(30) NOT NULL DEFAULT 'production'",
                "official_domain_confidence": "FLOAT NOT NULL DEFAULT 0",
                "domain_confidence_reason": "VARCHAR(1000)",
                "verified_at": "DATETIME",
                "discovery_query": "VARCHAR(1000)",
            },
            "runs": {
                "run_mode": "VARCHAR(30) NOT NULL DEFAULT 'unknown'",
                "data_origin": "VARCHAR(30) NOT NULL DEFAULT 'production'",
                "logical_run_key": "VARCHAR(120)",
                "attempt_number": "INTEGER NOT NULL DEFAULT 1",
                "error_category": "VARCHAR(80)",
                "retryable": "BOOLEAN NOT NULL DEFAULT 0",
                "retry_not_before": "DATETIME",
                "provider_request_id": "VARCHAR(255)",
                "research_provider": "VARCHAR(80)",
            },
            "sources": {
                "data_origin": "VARCHAR(30) NOT NULL DEFAULT 'production'",
                "originating_run_id": "VARCHAR(36)",
                "originating_query": "VARCHAR(1000)",
                "source_tier": "VARCHAR(10) NOT NULL DEFAULT 'C'",
                "freshness_category": "VARCHAR(20) NOT NULL DEFAULT 'unknown'",
                "claim_type": "VARCHAR(30) NOT NULL DEFAULT 'observed_fact'",
                "date_confidence": "VARCHAR(20) NOT NULL DEFAULT 'unknown'",
                "openai_request_id": "VARCHAR(255)",
            },
            "signals": {
                "data_origin": "VARCHAR(30) NOT NULL DEFAULT 'production'",
                "originating_run_id": "VARCHAR(36)",
            },
            "pain_hypotheses": {
                "data_origin": "VARCHAR(30) NOT NULL DEFAULT 'production'",
                "originating_run_id": "VARCHAR(36)",
            },
            "contacts": {
                "data_origin": "VARCHAR(30) NOT NULL DEFAULT 'production'",
                "source_title": "VARCHAR(500)",
                "source_context": "VARCHAR(1000)",
                "no_guessed_address": "BOOLEAN NOT NULL DEFAULT 1",
                "source_verification_status": "VARCHAR(30) NOT NULL DEFAULT 'not_checked'",
                "source_verification_checked_at": "DATETIME",
                "source_verification_reason": "VARCHAR(255)",
            },
            "lead_scores": {
                "data_origin": "VARCHAR(30) NOT NULL DEFAULT 'production'",
                "opportunity_fit_score": "INTEGER",
                "opportunity_fit_grade": "VARCHAR(1)",
                "opportunity_fit_version": "VARCHAR(60)",
                "opportunity_fit_breakdown_json": "JSON",
                "reachability_score": "INTEGER",
                "reachability_grade": "VARCHAR(1)",
                "reachability_version": "VARCHAR(60)",
                "reachability_breakdown_json": "JSON",
                "primary_buyer_persona": "VARCHAR(80)",
                "primary_project_type": "VARCHAR(255)",
                "project_scope_band": "VARCHAR(40)",
                "procurement_friction_band": "VARCHAR(20)",
                "priority": "VARCHAR(80)",
            },
            "drafts": {
                "data_origin": "VARCHAR(30) NOT NULL DEFAULT 'production'",
                "run_id": "VARCHAR(36)",
            },
            "outbox_messages": {
                "rfc_message_id": "VARCHAR(500)",
                "manual_subject": "VARCHAR(255)",
                "provider_message_id": "VARCHAR(255)",
                "provider_thread_id": "VARCHAR(255)",
                "mailbox_uid": "VARCHAR(100)",
                "mail_provider": "VARCHAR(60) NOT NULL DEFAULT 'namecheap_private_email'",
                "data_origin": "VARCHAR(30) NOT NULL DEFAULT 'production'",
            },
            "thread_events": {
                "provider_message_id": "VARCHAR(255)",
                "mailbox_uid": "VARCHAR(100)",
                "mail_provider": "VARCHAR(60) NOT NULL DEFAULT 'namecheap_private_email'",
            },
            "suppressions": {
                "data_origin": "VARCHAR(30) NOT NULL DEFAULT 'production'",
            },
        }
        with self.engine.begin() as connection:
            for table, columns in additions.items():
                existing = {
                    row[1] for row in connection.execute(text(f"PRAGMA table_info({table})"))
                }
                for column, declaration in columns.items():
                    if column not in existing:
                        connection.execute(
                            text(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")
                        )
            connection.execute(
                text(
                    "UPDATE outbox_messages SET rfc_message_id = message_id WHERE rfc_message_id IS NULL"
                )
            )
            connection.execute(
                text(
                    "UPDATE outbox_messages SET mail_provider = 'legacy_gmail' "
                    "WHERE mail_provider = 'namecheap_private_email' "
                    "AND gmail_message_id IS NOT NULL AND provider_message_id IS NULL"
                )
            )
            connection.execute(
                text(
                    "UPDATE thread_events SET provider_message_id = gmail_message_id WHERE provider_message_id IS NULL"
                )
            )
            connection.execute(
                text(
                    "UPDATE thread_events SET mail_provider = 'legacy_gmail' "
                    "WHERE mail_provider = 'namecheap_private_email' AND gmail_message_id IS NOT NULL"
                )
            )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_outbox_rfc_message_id ON outbox_messages(rfc_message_id)"
                )
            )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_thread_provider_message_id ON thread_events(provider_message_id)"
                )
            )
            # Quarantine only deterministic fixtures and old demo runs. Real-looking
            # legacy rows remain production-origin by default for owner review.
            connection.execute(
                text(
                    "UPDATE companies SET data_origin = 'synthetic' "
                    "WHERE lower(registrable_domain) LIKE '%.example' "
                    "OR lower(registrable_domain) LIKE '%.invalid' "
                    "OR lower(registrable_domain) LIKE '%.test'"
                )
            )
            connection.execute(
                text(
                    "UPDATE runs SET data_origin = 'synthetic', run_mode = 'demo' "
                    "WHERE run_key LIKE 'demo:%' OR run_type = 'demo'"
                )
            )
            # Backfill the logical key for every historical physical run. The
            # original production row remains intact as attempt 1; only its
            # state metadata is made precise enough for safe retries.
            connection.execute(
                text("UPDATE runs SET logical_run_key = run_key WHERE logical_run_key IS NULL")
            )
            connection.execute(
                text("UPDATE runs SET attempt_number = 1 WHERE attempt_number IS NULL")
            )
            connection.execute(
                text(
                    "UPDATE runs SET status = 'rate_limited', "
                    "error_category = 'rate_limit_exceeded', retryable = 1, "
                    "retry_not_before = '1970-01-01 00:00:00' "
                    "WHERE status = 'failed' AND run_type IN ('production_dry_run', 'production_live') "
                    "AND (lower(COALESCE(error_summary, '')) LIKE '%rate limit%' "
                    "OR lower(COALESCE(error_summary, '')) LIKE '%rate_limit%' "
                    "OR lower(COALESCE(error_summary, '')) LIKE '%429%')"
                )
            )
            connection.execute(
                text(
                    "UPDATE runs SET error_category = 'research_failed' "
                    "WHERE status = 'failed' AND error_category IS NULL"
                )
            )
            for table in (
                "sources",
                "signals",
                "pain_hypotheses",
                "contacts",
                "lead_scores",
                "drafts",
            ):
                connection.execute(
                    text(
                        f"UPDATE {table} SET data_origin = 'synthetic' "
                        f"WHERE company_id IN (SELECT id FROM companies WHERE data_origin = 'synthetic')"
                    )
                )
            connection.execute(
                text(
                    "UPDATE outbox_messages SET data_origin = 'synthetic' "
                    "WHERE draft_id IN (SELECT id FROM drafts WHERE data_origin = 'synthetic')"
                )
            )
            connection.execute(
                text(
                    "UPDATE suppressions SET data_origin = 'synthetic' "
                    "WHERE lower(normalized_value) LIKE '%.example' "
                    "OR lower(normalized_value) LIKE '%@%.example' "
                    "OR lower(normalized_value) LIKE '%.invalid' "
                    "OR lower(normalized_value) LIKE '%.test'"
                )
            )
            connection.execute(
                text(
                    "UPDATE lead_scores SET disposition = 'needs_review' "
                    "WHERE disposition = 'auto_send' AND company_id IN "
                    "(SELECT id FROM companies WHERE COALESCE(permission_basis, 'unknown') "
                    "NOT IN ('owner_approved', 'existing_relationship', 'explicit_inbound_request', "
                    "'contractual_or_transactional', 'synthetic_test'))"
                )
            )
            self._make_draft_contact_optional(connection)
            self._make_outbox_message_id_optional(connection)

    @staticmethod
    def _make_draft_contact_optional(connection: Any) -> None:
        """Preserve draft rows while allowing research drafts without contacts.

        SQLite cannot alter a column's NOT NULL constraint in place. Rebuild only
        this table, copying every existing row and retaining all draft IDs used by
        the outbox. This migration intentionally does not change schema version 7.
        """
        table_info = list(connection.execute(text("PRAGMA table_info(drafts)")))
        contact_column = next((row for row in table_info if row[1] == "contact_id"), None)
        if contact_column is None or not contact_column[3]:
            return
        legacy_table = "drafts_contact_required_legacy"
        connection.execute(text(f"ALTER TABLE drafts RENAME TO {legacy_table}"))
        legacy_indexes = list(connection.execute(text(f"PRAGMA index_list({legacy_table})")))
        for row in legacy_indexes:
            index_name = str(row[1])
            if index_name.startswith("sqlite_autoindex"):
                continue
            safe_index_name = index_name.replace('"', '""')
            connection.execute(text(f'DROP INDEX "{safe_index_name}"'))
        draft_table: Any = Draft.__table__
        draft_table.create(connection, checkfirst=False)
        new_columns = {column.name for column in draft_table.columns}
        old_columns = {str(row[1]) for row in table_info}
        copy_columns = [column for column in new_columns if column in old_columns]
        missing_expressions = {
            "data_origin": "'production'",
            "run_id": "NULL",
        }
        target_columns = list(copy_columns)
        select_expressions = [f'"{column}"' for column in copy_columns]
        for column, expression in missing_expressions.items():
            if column in new_columns and column not in old_columns:
                target_columns.append(column)
                select_expressions.append(expression)
        quoted_targets = ", ".join(f'"{column}"' for column in target_columns)
        selects = ", ".join(select_expressions)
        connection.execute(
            text(f"INSERT INTO drafts ({quoted_targets}) SELECT {selects} FROM {legacy_table}")
        )
        connection.execute(text(f"DROP TABLE {legacy_table}"))
        for index in draft_table.indexes:
            index.create(connection, checkfirst=True)

    @staticmethod
    def _make_outbox_message_id_optional(connection: Any) -> None:
        """Allow a manual-send row to await RFC Message-ID reconciliation.

        SQLite cannot alter a column's NOT NULL constraint in place.  Rebuild
        only when migrating an older database whose outbox ``message_id`` was
        required; all existing rows and their identifiers are copied intact.
        """
        table_info = list(connection.execute(text("PRAGMA table_info(outbox_messages)")))
        message_column = next((row for row in table_info if row[1] == "message_id"), None)
        if message_column is None or not message_column[3]:
            return
        legacy_table = "outbox_messages_message_id_required_legacy"
        connection.execute(text(f"ALTER TABLE outbox_messages RENAME TO {legacy_table}"))
        legacy_indexes = list(connection.execute(text(f"PRAGMA index_list({legacy_table})")))
        for row in legacy_indexes:
            index_name = str(row[1])
            if index_name.startswith("sqlite_autoindex"):
                continue
            safe_index_name = index_name.replace('"', '""')
            connection.execute(text(f'DROP INDEX "{safe_index_name}"'))
        outbox_table: Any = OutboxMessage.__table__
        outbox_table.create(connection, checkfirst=False)
        new_columns = {column.name for column in outbox_table.columns}
        old_columns = {str(row[1]) for row in table_info}
        copy_columns = [column for column in new_columns if column in old_columns]
        missing_expressions = {
            "rfc_message_id": "NULL",
            "manual_subject": "NULL",
            "provider_message_id": "NULL",
            "provider_thread_id": "NULL",
            "mailbox_uid": "NULL",
            "mail_provider": "'namecheap_private_email'",
            "data_origin": "'production'",
        }
        target_columns = list(copy_columns)
        select_expressions = [f'"{column}"' for column in copy_columns]
        for column, expression in missing_expressions.items():
            if column in new_columns and column not in old_columns:
                target_columns.append(column)
                select_expressions.append(expression)
        quoted_targets = ", ".join(f'"{column}"' for column in target_columns)
        selects = ", ".join(select_expressions)
        connection.execute(
            text(
                f"INSERT INTO outbox_messages ({quoted_targets}) "
                f"SELECT {selects} FROM {legacy_table}"
            )
        )
        connection.execute(text(f"DROP TABLE {legacy_table}"))
        for index in outbox_table.indexes:
            index.create(connection, checkfirst=True)

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def healthy(self) -> bool:
        with self.engine.connect() as connection:
            return bool(connection.execute(text("SELECT 1")).scalar())


def _sqlite_pragmas(dbapi_connection: Any, _connection_record: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def as_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)
