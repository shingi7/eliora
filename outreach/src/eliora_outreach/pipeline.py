from __future__ import annotations

import hashlib
import socket
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select

from .compliance import evaluate_dispatch_eligibility
from .config import SenderSettings, Settings
from .db import (
    AuditEvent,
    Company,
    Contact,
    Database,
    Draft,
    LeadScore,
    OutboxMessage,
    PainHypothesis,
    Run,
    Signal,
    Source,
    utcnow,
)
from .due import within_send_window
from .email.followups import cancel_sequence
from .email.guardrails import check_draft, deterministic_quality_findings
from .email.outbox import create_outbox, lease_pending, send_leased
from .email.render import render_draft
from .email.replies import classify_reply
from .enums import (
    RunStatus,
    RunType,
    SignalType,
    SourceType,
    SuppressionReason,
    SuppressionScope,
)
from .logging_config import sanitize_log_message
from .models import ContactRecord, SourceEvidence
from .models import PainHypothesis as PainModel
from .providers.fake import FakeEmailProvider
from .research.canonicalize import registrable_domain
from .score_service import apply_commercial_score, commercial_score_for_records
from .scoring import LeadInputs, score_lead
from .suppression import add_suppression, is_suppressed
from .usage import dispatch_capacity, increment_usage


def create_run(
    database: Database,
    run_key: str,
    run_type: RunType,
    *,
    run_mode: str | None = None,
    data_origin: str = "production",
    logical_run_key: str | None = None,
    attempt_number: int = 1,
    research_provider: str | None = None,
) -> Run | None:
    with database.session() as session:
        if session.scalar(select(Run).where(Run.run_key == run_key)):
            return None
        row = Run(
            run_key=run_key,
            logical_run_key=logical_run_key or run_key,
            attempt_number=attempt_number,
            run_type=run_type.value,
            run_mode=run_mode or run_type.value,
            data_origin=data_origin,
            status=RunStatus.RUNNING.value,
            host=socket.gethostname(),
            app_version="0.1.0",
            research_provider=research_provider,
        )
        session.add(row)
        session.flush()
        return row


def finish_run(
    database: Database,
    run_id: str,
    status: RunStatus,
    counters: dict[str, Any],
    error: str | None = None,
    *,
    error_category: str | None = None,
    retryable: bool = False,
    retry_not_before: datetime | None = None,
    provider_request_id: str | None = None,
) -> None:
    with database.session() as session:
        row = session.get(Run, run_id)
        if row:
            row.finished_at = utcnow()
            row.status = status.value
            row.counters = counters
            row.error_summary = sanitize_log_message(error) if error else None
            row.error_category = error_category
            row.retryable = retryable
            row.retry_not_before = retry_not_before
            row.provider_request_id = provider_request_id


def dispatch_pending(
    database: Database,
    settings: Settings,
    *,
    provider=None,
    now: datetime | None = None,
    paths=None,
) -> dict[str, int | str]:
    """Dispatch one due message after rechecking window, quota, and suppression gates."""
    now = now or utcnow()
    if not settings.live.enabled:
        return {"sent": 0, "blocked": "live_disabled"}
    if paths is not None and paths.pause_file.exists():
        return {"sent": 0, "blocked": "paused"}
    if not within_send_window(
        now,
        settings.schedule.send_start,
        settings.schedule.send_end,
        settings.schedule.fallback_timezone,
    ):
        return {"sent": 0, "blocked": "outside_send_window"}
    message = lease_pending(database, now=now)
    if message is None:
        return {"sent": 0, "blocked": "no_due_messages"}
    if provider is None:
        from .paths import default_paths
        from .providers.private_email_provider import PrivateEmailProvider
        from .secrets import default_secret_store

        paths = paths or default_paths()
        provider = PrivateEmailProvider(
            settings.providers,
            username=settings.providers.mailbox_username or settings.sender.email,
            secret_store=default_secret_store(),
        )
    with database.session() as session:
        draft = session.get(Draft, message.draft_id)
        contact = session.get(Contact, draft.contact_id) if draft else None
        company = session.get(Company, draft.company_id) if draft else None
    if not draft or not contact or not company:
        with database.session() as session:
            current = session.get(OutboxMessage, message.id)
            if current:
                current.state = "failed"
                current.last_error_category = "outbox_reference_missing"
        return {"sent": 0, "blocked": "outbox_reference_missing"}
    usage_day = now.astimezone(ZoneInfo(settings.schedule.fallback_timezone)).date()
    suppressed = is_suppressed(
        database,
        email=contact.email,
        domain=company.registrable_domain,
        company_id=company.id,
    )
    eligibility = evaluate_dispatch_eligibility(
        settings,
        permission_basis=company.permission_basis,
        contact_valid=(
            contact.syntactic_valid
            and contact.appropriateness_status == "eligible"
            and "@" in contact.email
            and registrable_domain(contact.email.rsplit("@", 1)[-1])
            == registrable_domain(company.registrable_domain)
        ),
        official_domain=contact.official_domain,
        no_guessed_address=contact.no_guessed_address,
        draft_status=draft.status,
        active_suppression=suppressed,
        data_origin=(
            "production"
            if company.data_origin == draft.data_origin == message.data_origin == "production"
            else "non_production"
        ),
    )
    if not eligibility.allowed:
        with database.session() as session:
            current = session.get(OutboxMessage, message.id)
            if current:
                current.state = "cancelled" if eligibility.reason == "suppressed" else "pending"
                current.last_error_category = eligibility.reason
        return {"sent": 0, "blocked": eligibility.reason}
    if not dispatch_capacity(
        database,
        usage_day,
        settings.schedule.fallback_timezone,
        settings.limits,
        sequence_step=draft.sequence_step,
    ):
        with database.session() as session:
            current = session.get(OutboxMessage, message.id)
            if current:
                current.state = "retryable"
                current.last_error_category = "daily_quota"
        return {"sent": 0, "blocked": "daily_quota"}
    sent = send_leased(
        database,
        provider,
        message.id,
        sender=settings.sender,
        recipient=contact.email,
    )
    increment_usage(
        database,
        usage_day,
        settings.schedule.fallback_timezone,
        initial_messages_sent=1 if draft.sequence_step == 1 else 0,
        followups_sent=1 if draft.sequence_step > 1 else 0,
        total_recipients=1
        + int(
            bool(
                settings.sender.owner_bcc
                and settings.sender.owner_bcc.lower() != contact.email.lower()
            )
        ),
    )
    return {"sent": 1, "message_id": sent.id}


def run_synthetic_demo(database: Database, settings: Settings | None = None) -> dict[str, object]:
    """Offline end-to-end path: evidence -> score -> guarded draft -> fake send -> opt-out."""
    database.create()
    settings = settings or Settings(
        sender=SenderSettings(
            display_name="EliOra Demo",
            title="Co-Founder",
            email="owner@eliora.example",
            reply_to="owner@eliora.example",
            owner_bcc="owner@eliora.example",
            postal_address="100 Demo Way, New York, NY 10001",
        )
    )
    run = create_run(
        database,
        f"demo:{datetime.now(timezone.utc).date().isoformat()}",
        RunType.DEMO,
        run_mode="demo",
        data_origin="synthetic",
    )
    if not run:
        return {"status": "already_complete"}
    company_id = "northstar-health-operations"
    source_one = "northstar-about"
    source_two = "northstar-press"
    with database.session() as session:
        company = session.get(Company, company_id)
        contact: Contact | None = None
        if not company:
            company = Company(
                id=company_id,
                name="Northstar Health Operations",
                registrable_domain="northstarhealth.example",
                official_website="https://northstarhealth.example",
                country="United States",
                state="NY",
                city="New York",
                timezone="America/New_York",
                timezone_confidence=0.8,
                vertical="healthcare",
                employee_band="50-99",
                permission_basis="synthetic_test",
                permission_basis_source="offline demo fixture",
                data_origin="synthetic",
            )
            session.add(company)
            session.add_all(
                [
                    Source(
                        id=source_one,
                        company_id=company_id,
                        url="https://northstarhealth.example/about",
                        canonical_url_hash=hashlib.sha256(b"about").hexdigest(),
                        source_type=SourceType.OFFICIAL.value,
                        title="About Northstar Health Operations",
                        publisher="northstarhealth.example",
                        excerpt="Northstar Health Operations announced a 2026 expansion across three provider locations.",
                        source_quality=1.0,
                        http_status=200,
                        data_origin="synthetic",
                    ),
                    Source(
                        id=source_two,
                        company_id=company_id,
                        url="https://northstarhealth.example/news/expansion",
                        canonical_url_hash=hashlib.sha256(b"press").hexdigest(),
                        source_type=SourceType.OFFICIAL_PRESS.value,
                        title="Northstar announces provider operations expansion",
                        publisher="northstarhealth.example",
                        excerpt="The company is adding locations and a centralized prior-authorization operations team.",
                        source_quality=1.0,
                        http_status=200,
                        data_origin="synthetic",
                    ),
                    Signal(
                        id="northstar-signal",
                        company_id=company_id,
                        source_id=source_two,
                        signal_type=SignalType.HEALTHCARE_ADMINISTRATION.value,
                        observed_signal="The company announced a centralized prior-authorization operations team in 2026.",
                        confidence=0.95,
                        data_origin="synthetic",
                    ),
                    PainHypothesis(
                        id="northstar-pain",
                        company_id=company_id,
                        category=SignalType.HEALTHCARE_ADMINISTRATION.value,
                        hypothesis="The expansion may create additional coordination and reporting work across authorization workflows.",
                        confidence=0.88,
                        service_mapping="workflow automation and decision support",
                        supporting_signal_ids=["northstar-signal"],
                        data_origin="synthetic",
                    ),
                ]
            )
            contact = Contact(
                id="northstar-contact",
                company_id=company_id,
                email="operations@northstarhealth.example",
                role_inbox_category="relevant_role",
                source_id=source_two,
                source_url="https://northstarhealth.example/news/expansion",
                extraction_method="mailto",
                official_domain=True,
                syntactic_valid=True,
                mx_valid=None,
                appropriateness_status="eligible",
                appropriateness_reason="Official synthetic fixture contact",
                data_origin="synthetic",
            )
            session.add(contact)
            session.flush()
        else:
            contact = session.scalar(select(Contact).where(Contact.company_id == company_id))
            if contact is None:
                raise RuntimeError("Synthetic company is missing its contact")
        if contact is None:
            raise RuntimeError("Synthetic company is missing its contact")
        sources = list(session.scalars(select(Source).where(Source.company_id == company_id)))
        signals = list(session.scalars(select(Signal).where(Signal.company_id == company_id)))
        pains = list(
            session.scalars(select(PainHypothesis).where(PainHypothesis.company_id == company_id))
        )
    source_models = [
        SourceEvidence(
            id=s.id,
            url=s.url,  # type: ignore[arg-type]
            title=s.title,
            publisher=s.publisher,
            source_type=SourceType(s.source_type),
            retrieved_at=s.retrieved_at or utcnow(),
            excerpt=s.excerpt,
            source_quality=s.source_quality,
        )
        for s in sources
    ]
    pain_models = [
        PainModel(
            id=p.id,
            company_id=company_id,
            category=SignalType(p.category),
            pain_hypothesis=p.hypothesis,
            confidence=p.confidence,
            service_match=p.service_mapping,
            supporting_signal_ids=p.supporting_signal_ids,
        )
        for p in pains
    ]
    contact_model = ContactRecord(
        id=contact.id,
        company_id=company_id,
        email=contact.email,
        source_id=contact.source_id,
        source_url=contact.source_url,  # type: ignore[arg-type]
        extraction_method=contact.extraction_method,
        role=contact.role_inbox_category,
        official_domain=contact.official_domain,
        syntactic_valid=contact.syntactic_valid,
        mx_valid=contact.mx_valid,
        appropriateness_status=contact.appropriateness_status,
        appropriateness_reason=contact.appropriateness_reason,
        contact_quality=13,
    )
    result = score_lead(
        LeadInputs(
            "United States",
            "50-99",
            source_models,
            1,
            24,
            pain_models,
            contact_model,
            research_confidence=0.91,
        ),
        settings.targeting,
    )
    commercial_score = commercial_score_for_records(
        company,
        sources,
        signals,
        pains,
        contact,
    )
    sender = settings.sender
    content = render_draft(
        company_name="Northstar Health Operations",
        observation="the company announced a centralized prior-authorization operations team",
        hypothesis="authorization reporting and handoffs",
        service="workflow automation",
        source_fact_ids=["northstar-signal"],
        sender=sender,
    )
    report = check_draft(
        content, sender, approved_fact_ids={"northstar-signal"}, word_limits=(20, 145)
    )
    draft_id = "northstar-draft"
    with database.session() as session:
        draft = session.get(Draft, draft_id)
        if not draft:
            draft = Draft(
                id=draft_id,
                company_id=company_id,
                contact_id=contact.id,
                sequence_step=1,
                subject=content.subject,
                plain_text_body=content.body,
                html_body=content.html_body,
                source_facts_used=content.source_fact_ids,
                model=content.model,
                prompt_version=content.prompt_version,
                content_hash=hashlib.sha256(content.body.encode()).hexdigest(),
                quality_findings=deterministic_quality_findings(report),
                status="approved" if report.passed else "needs_review",
                data_origin="synthetic",
            )
            session.add(draft)
        lead_score = LeadScore(
            id="northstar-score",
            company_id=company_id,
            score_version=result.score_version,
            icp_score=result.company_fit,
            intent_score=result.intent,
            service_fit_score=result.service_fit,
            evidence_quality_score=result.evidence_quality,
            contact_quality_score=result.contact_quality,
            penalties=result.penalties,
            total_score=result.total,
            disposition=result.disposition.value,
            explanation=result.explanation,
            data_origin="synthetic",
        )
        apply_commercial_score(lead_score, commercial_score)
        session.add(lead_score)
        session.add(
            AuditEvent(
                actor="system",
                action="demo_pipeline_complete",
                entity_type="company",
                entity_id=company_id,
                metadata_json={"score": result.total, "guardrails_passed": report.passed},
            )
        )
    fake = FakeEmailProvider()
    outbox = create_outbox(
        database,
        draft,
        scheduled_for=utcnow(),
        sender=sender,
        recipient=contact.email,
        data_origin="synthetic",
    )
    leased = lease_pending(database)
    if leased:
        send_leased(database, fake, leased.id, sender=sender, recipient=contact.email)
        fake.add_reply(
            f"thread-{outbox.idempotency_key}", "No thanks, please remove me.", sender=contact.email
        )
        classification = classify_reply("Re: " + content.subject, "No thanks, please remove me.")
        add_suppression(
            database,
            contact.email,
            SuppressionScope.EMAIL,
            SuppressionReason.OPT_OUT.value,
            data_origin="synthetic",
        )
        add_suppression(
            database,
            "northstarhealth.example",
            SuppressionScope.DOMAIN,
            SuppressionReason.OPT_OUT.value,
            data_origin="synthetic",
        )
        cancel_sequence(database, company_id=company_id, reason=classification.event_class.value)
    finish_run(
        database,
        run.id,
        RunStatus.SUCCESS,
        {"companies": 1, "drafts": 1, "sent": 1, "suppressed": 2},
    )
    return {
        "status": "success",
        "company": company.name,
        "score": result.total,
        "disposition": result.disposition.value,
        "draft_guardrails": report.passed,
        "reply": "unsubscribe",
        "offline": True,
    }
