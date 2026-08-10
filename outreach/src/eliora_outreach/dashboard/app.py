from __future__ import annotations

import secrets
from html import escape
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..compliance import evaluate_dispatch_eligibility
from ..config import Settings, load_settings
from ..db import (
    AuditEvent,
    Company,
    Contact,
    Database,
    Draft,
    ImportRecord,
    LeadScore,
    MailboxCheckpoint,
    OutboxMessage,
    PainHypothesis,
    Run,
    Signal,
    Source,
    Suppression,
    ThreadEvent,
)
from ..paths import default_paths
from ..score_service import commercial_order_key
from .csrf import session_token, validate_token


def create_app(settings: Settings | None = None, database: Database | None = None):
    from starlette.middleware.sessions import SessionMiddleware

    settings = settings or load_settings()
    database = database or Database()
    database.create()
    app = FastAPI(title="EliOra Outreach Operations", docs_url=None, redoc_url=None)
    app.add_middleware(
        SessionMiddleware,
        secret_key=secrets.token_urlsafe(32),
        same_site="strict",
        https_only=False,
    )
    templates = Environment(
        loader=FileSystemLoader(Path(__file__).parent / "templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )

    def layout(request: Request, title: str, content: str) -> HTMLResponse:
        token = session_token(request.session)
        return HTMLResponse(
            templates.get_template("base.html").render(
                title=title, content=content, csrf_token=token
            )
        )

    def origin_clause(model, origin: str):
        if origin == "production":
            if model is OutboxMessage:
                return model.data_origin.in_(["production", "manual_send"])
            return model.data_origin == "production"
        if origin == "external":
            if model is OutboxMessage:
                return model.data_origin.in_(["external_research", "manual_send"])
            return model.data_origin == "external_research"
        if origin in {"demo", "test"}:
            return model.data_origin.in_(["synthetic", "owner_test"])
        return None

    def origin_filter(request: Request) -> str:
        value = request.query_params.get("origin", "production")
        return value if value in {"production", "external", "demo", "all"} else "production"

    def origin_links(current: str) -> str:
        return "Filter: " + " ".join(
            f"<a href='?origin={value}'>{label}</a>"
            for value, label in (
                ("production", "Production"),
                ("external", "External Research"),
                ("demo", "Demo/Test"),
                ("all", "All"),
            )
        )

    def safe_href(value: str) -> str:
        return value if value.lower().startswith(("https://", "http://")) else "#"

    def draft_validation_summary(draft: Draft) -> str:
        validation = (draft.quality_findings or {}).get("external_research_validation", {})
        if not isinstance(validation, dict):
            return draft.status
        status = str(validation.get("status", draft.status))
        errors = validation.get("errors", [])
        if isinstance(errors, list) and errors:
            return f"{status}: {'; '.join(str(error) for error in errors)}"
        return status

    def draft_status_label(status: str) -> str:
        return "Sent manually" if status == "sent_manually" else status

    def draft_contact_status(contact: Contact | None) -> str:
        if contact is None:
            return "needs_contact"
        if contact.source_verification_status == "verified":
            return "verified"
        if contact.appropriateness_status != "eligible":
            return "needs_review"
        return contact.source_verification_status or "not_checked"

    def draft_dispatch_state(draft: Draft | None, company: Company, contact: Contact | None) -> str:
        if draft and draft.status == "sent_manually":
            return "sent manually"
        eligibility = evaluate_dispatch_eligibility(
            settings,
            permission_basis=company.permission_basis,
            provider_policy_eligible=company.data_origin != "external_research",
            contact_valid=bool(
                contact and contact.syntactic_valid and contact.appropriateness_status == "eligible"
            ),
            official_domain=bool(contact and contact.official_domain),
            no_guessed_address=bool(contact and contact.no_guessed_address),
            draft_status=draft.status if draft else "missing",
            active_suppression=False,
            data_origin=company.data_origin,
        )
        return "ALLOWED" if eligibility.allowed else "BLOCKED"

    def display_label(value: str | None) -> str:
        if not value:
            return "unknown"
        return value.replace("_", " ").strip().title()

    def commercial_score_card(
        title: str,
        score: int | None,
        grade: str | None,
        breakdown: dict | None,
        labels: dict[str, str],
    ) -> str:
        rows: list[str] = []
        for key, label in labels.items():
            item = (breakdown or {}).get(key, {})
            if not isinstance(item, dict):
                item = {}
            rows.append(
                f"<tr><td>{escape(label)}</td><td>{item.get('points', 0)} / "
                f"{item.get('max_points', 0)}</td><td>{escape(str(item.get('reason', 'Not recorded.')))}</td></tr>"
            )
        return (
            f"<h2>{escape(title)}</h2><p class='score-hero'><strong>"
            f"{score if score is not None else '—'} / 100 — {escape(grade or '—')}</strong></p>"
            "<table><thead><tr><th>Component</th><th>Points</th><th>Reason</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )

    def commercial_summary_html(score: LeadScore) -> str:
        fit_labels = {
            "pain_specificity": "Pain specificity",
            "service_match": "Service match",
            "trigger_strength": "Trigger strength",
            "small_project_suitability": "Small-project suitability",
            "commercial_buyability": "Commercial buyability",
            "evidence_confidence": "Evidence confidence",
        }
        reach_labels = {
            "buyer_persona_clarity": "Buyer persona clarity",
            "appropriate_business_contact": "Appropriate contact",
            "contact_provenance_verification": "Provenance / verification",
            "channel_relevance": "Channel relevance",
        }
        return (
            f"<div class='grid'><div class='card'>{commercial_score_card('Opportunity Fit', score.opportunity_fit_score, score.opportunity_fit_grade, score.opportunity_fit_breakdown_json, fit_labels)}"
            f"<p><strong>Recommended project:</strong> {escape(score.primary_project_type or 'unknown')}<br>"
            f"<strong>Scope:</strong> {escape(display_label(score.project_scope_band))}<br>"
            f"<strong>Procurement friction:</strong> {escape(display_label(score.procurement_friction_band))} <small>(heuristic)</small></p></div>"
            f"<div class='card'>{commercial_score_card('Reachability', score.reachability_score, score.reachability_grade, score.reachability_breakdown_json, reach_labels)}"
            f"<p><strong>Buyer persona:</strong> {escape(display_label(score.primary_buyer_persona))}<br>"
            f"<strong>Priority:</strong> {escape(score.priority or 'not assigned')}</p></div></div>"
        )

    def dispatch_detail_html(company: Company, draft: Draft, contact: Contact | None) -> str:
        eligibility = evaluate_dispatch_eligibility(
            settings,
            permission_basis=company.permission_basis,
            provider_policy_eligible=company.data_origin != "external_research",
            contact_valid=bool(
                contact and contact.syntactic_valid and contact.appropriateness_status == "eligible"
            ),
            official_domain=bool(contact and contact.official_domain),
            no_guessed_address=bool(contact and contact.no_guessed_address),
            draft_status=draft.status,
            active_suppression=False,
            data_origin=company.data_origin,
        )
        reasons: list[str] = []
        if company.permission_basis == "unknown":
            reasons.append("Permission basis: unknown")
        if company.data_origin == "external_research":
            reasons.append("Provider policy: not eligible")
        if contact is None:
            reasons.append("Contact: needs contact")
        elif contact.source_verification_status != "verified":
            reasons.append(f"Contact source verification: {contact.source_verification_status}")
        if draft.status != "approved":
            reasons.append(f"Draft content: {draft.status}")
        if not reasons and not eligibility.allowed:
            reasons.append(eligibility.reason.replace("_", " "))
        reason_html = "".join(f"<li>{escape(reason)}</li>" for reason in reasons)
        return (
            "<h2>Dispatch eligibility</h2>"
            f"<p><strong>{'ALLOWED' if eligibility.allowed else 'BLOCKED'}</strong></p>"
            f"<h3>Reasons</h3><ul>{reason_html or '<li>None</li>'}</ul>"
        )

    def score_breakdown_html(score: LeadScore) -> str:
        components = (score.explanation or {}).get("components", {})
        maxima = {
            "company_fit": 20,
            "intent": 25,
            "service_fit": 25,
            "evidence_quality": 15,
            "contact_quality": 15,
        }
        labels = {
            "company_fit": "Company fit",
            "intent": "Intent",
            "service_fit": "Service fit",
            "evidence_quality": "Evidence quality",
            "contact_quality": "Contact quality",
        }
        rows = "".join(
            f"<tr><td>{escape(labels[key])}</td><td>{components.get(key, 0)} / {maximum}</td></tr>"
            for key, maximum in maxima.items()
        )
        fresh = (score.explanation or {}).get("fresh_signal_count", 0)
        penalties = (score.explanation or {}).get("quality_penalties", [])
        penalty_text = ", ".join(str(item).replace("_", " ") for item in penalties) or "None"
        return (
            f"<h2>Legacy score audit · Score breakdown</h2><p><strong>Total score: {score.total_score}</strong> · version {escape(score.score_version)}</p>"
            f"<table><thead><tr><th>Component</th><th>Score</th></tr></thead><tbody>{rows}"
            f"</tbody></table><p>Fresh signals: {fresh}</p>"
            f"<p>Penalties: {escape(penalty_text)}</p>"
        )

    def import_draft_validation_text(audit: AuditEvent | None) -> str:
        if audit is None or not isinstance(audit.metadata_json, dict):
            return "not recorded"
        values = audit.metadata_json.get("draft_validation", [])
        if not isinstance(values, list) or not values:
            return "none"
        summaries: list[str] = []
        for value in values:
            if not isinstance(value, dict):
                continue
            status = str(value.get("status", "review"))
            name = str(value.get("company_name", value.get("external_company_id", "unknown")))
            errors = value.get("errors", [])
            detail = f": {'; '.join(str(error) for error in errors)}" if errors else ""
            summaries.append(f"{name}: {status}{detail}")
        return " | ".join(summaries) or "none"

    def import_draft_counter_text(row: ImportRecord, audit: AuditEvent | None) -> str:
        metadata = audit.metadata_json if audit and isinstance(audit.metadata_json, dict) else {}
        persisted = metadata.get("drafts_persisted", "not recorded")
        send_ready = metadata.get("drafts_send_ready", "not recorded")
        return (
            f"pass {row.drafts_ready}; review {row.drafts_needs_review}; "
            f"persisted {persisted}; send-ready {send_ready}"
        )

    def display_disposition(company: Company, score: LeadScore) -> str:
        if score.disposition != "auto_send":
            return score.disposition
        eligibility = evaluate_dispatch_eligibility(
            settings,
            permission_basis=company.permission_basis,
            contact_valid=True,
            official_domain=True,
            draft_status="approved",
            active_suppression=False,
            data_origin=company.data_origin,
        )
        return score.disposition if eligibility.allowed else "needs_review"

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.get("/", response_class=HTMLResponse)
    async def overview(request: Request):
        origin = origin_filter(request)
        with database.session() as session:
            company_filter = origin_clause(Company, origin)
            score_filter = origin_clause(LeadScore, origin)
            draft_filter = origin_clause(Draft, origin)
            outbox_filter = origin_clause(OutboxMessage, origin)
            counts = {
                "companies researched": session.query(Company).filter(company_filter).count()
                if company_filter is not None
                else session.query(Company).count(),
                "legacy qualified": session.query(LeadScore)
                .filter(
                    LeadScore.total_score >= settings.targeting.min_score_auto_send, score_filter
                )
                .count()
                if score_filter is not None
                else session.query(LeadScore)
                .filter(LeadScore.total_score >= settings.targeting.min_score_auto_send)
                .count(),
                "needs review": session.query(LeadScore)
                .filter(LeadScore.disposition == "needs_review", score_filter)
                .count()
                if score_filter is not None
                else session.query(LeadScore)
                .filter(LeadScore.disposition == "needs_review")
                .count(),
                "needs contact": session.query(LeadScore)
                .filter(LeadScore.disposition == "needs_contact", score_filter)
                .count()
                if score_filter is not None
                else session.query(LeadScore)
                .filter(LeadScore.disposition == "needs_contact")
                .count(),
                "drafts content-ready": session.query(Draft)
                .filter(Draft.status == "approved", draft_filter)
                .count()
                if draft_filter is not None
                else session.query(Draft).filter(Draft.status == "approved").count(),
                "permission blocked": session.query(Company)
                .filter(Company.permission_basis == "unknown", company_filter)
                .count()
                if company_filter is not None
                else session.query(Company).filter(Company.permission_basis == "unknown").count(),
                "provider blocked": session.query(Company)
                .filter(Company.permission_basis == "unknown", company_filter)
                .count()
                if company_filter is not None
                else session.query(Company).filter(Company.permission_basis == "unknown").count(),
                "queued": session.query(OutboxMessage)
                .filter(OutboxMessage.state.in_(["pending", "retryable"]), outbox_filter)
                .count()
                if outbox_filter is not None
                else session.query(OutboxMessage)
                .filter(OutboxMessage.state.in_(["pending", "retryable"]))
                .count(),
                "prospect sent": session.query(OutboxMessage)
                .filter(OutboxMessage.state == "sent", outbox_filter)
                .count()
                if outbox_filter is not None
                else session.query(OutboxMessage).filter(OutboxMessage.state == "sent").count(),
                "owner transport tests": session.query(AuditEvent)
                .filter(AuditEvent.action == "owner_transport_test_sent")
                .count(),
                "replies": session.query(ThreadEvent)
                .filter(ThreadEvent.direction == "inbound")
                .count(),
                "opt-outs": session.query(Suppression)
                .filter(
                    Suppression.reason.in_(["opt_out", "not_interested"]),
                    Suppression.removed_at.is_(None),
                    origin_clause(Suppression, origin),
                )
                .count()
                if origin_clause(Suppression, origin) is not None
                else session.query(Suppression)
                .filter(
                    Suppression.reason.in_(["opt_out", "not_interested"]),
                    Suppression.removed_at.is_(None),
                )
                .count(),
            }
            commercial_query = session.query(Company, LeadScore).join(
                LeadScore, Company.id == LeadScore.company_id
            )
            if origin == "production":
                commercial_query = commercial_query.filter(
                    Company.data_origin == "production", LeadScore.data_origin == "production"
                )
            elif origin == "external":
                commercial_query = commercial_query.filter(
                    Company.data_origin == "external_research",
                    LeadScore.data_origin == "external_research",
                )
            elif origin == "demo":
                commercial_query = commercial_query.filter(
                    Company.data_origin.in_(["synthetic", "owner_test"])
                )
            commercial_rows = commercial_query.all()
            commercial_company_ids = {company.id for company, _score in commercial_rows}
            commercial_contacts = {
                contact.company_id: contact
                for contact in session.query(Contact)
                .filter(Contact.company_id.in_(commercial_company_ids))
                .all()
            }
            commercial_drafts: dict[str, Draft] = {}
            for draft in (
                session.query(Draft)
                .filter(Draft.company_id.in_(commercial_company_ids))
                .order_by(Draft.created_at.desc())
                .all()
            ):
                commercial_drafts.setdefault(draft.company_id, draft)
            counts.update(
                {
                    "total researched": len(commercial_rows),
                    "opportunity fit A": sum(
                        score.opportunity_fit_grade == "A" for _company, score in commercial_rows
                    ),
                    "opportunity fit B": sum(
                        score.opportunity_fit_grade == "B" for _company, score in commercial_rows
                    ),
                    "needs contact path": sum(
                        score.reachability_grade in {None, "C", "D"}
                        or company.id not in commercial_contacts
                        for company, score in commercial_rows
                    ),
                    "verified contact path": sum(
                        commercial_contacts.get(company.id) is not None
                        and commercial_contacts[company.id].source_verification_status == "verified"
                        for company, _score in commercial_rows
                    ),
                    "dispatch blocked": sum(
                        draft_dispatch_state(
                            commercial_drafts.get(company.id),
                            company,
                            commercial_contacts.get(company.id),
                        )
                        == "BLOCKED"
                        for company, _score in commercial_rows
                    ),
                }
            )
            last_run = session.query(Run).order_by(Run.started_at.desc()).first()
            production_today = (
                session.query(Run)
                .filter(Run.data_origin == "production", Run.status == "success")
                .order_by(Run.finished_at.desc())
                .first()
            )
            demo_run = (
                session.query(Run)
                .filter(Run.data_origin == "synthetic")
                .order_by(Run.started_at.desc())
                .first()
            )
        cards = "".join(
            f"<div class='card'><div class='eyebrow'>{escape(label.capitalize())}</div><div class='metric'>{value}</div></div>"
            for label, value in counts.items()
        )
        paused = (default_paths().pause_file).exists()
        state = "PAUSED" if paused else ("LIVE" if settings.live.enabled else "DRY RUN")
        token = session_token(request.session)
        content = f"<p class='eyebrow'>Signal → decision</p><h1>Outreach control room</h1><p class='muted'>Small-volume, evidence-led client research and outreach. State: <strong class='status'>{state}</strong></p><p>{origin_links(origin)}</p><form method='post' action='/pause' style='margin:20px 0'><input type='hidden' name='csrf_token' value='{escape(token)}'><button class='danger' type='submit'>Pause future outreach</button></form><section class='grid'>{cards}</section><section class='card' style='margin-top:20px'><h2>Run status</h2><p>{escape('Last run: ' + str(last_run.finished_at) if last_run else 'No run yet.')}</p><p>Last production research: {escape(str(production_today.finished_at) if production_today else 'not completed')}</p><p>Last demo: {escape(str(demo_run.finished_at) if demo_run else 'not run')}</p><p>Production gate: <strong>{'complete' if settings.live.production_research_completed else 'incomplete'}</strong>; scheduler: {_scheduler_label()}</p><p class='muted'>Research is bounded. Dry runs create no outbox rows and sending is blocked outside the configured recipient window.</p></section>"
        return layout(request, "Overview", content)

    def _scheduler_label() -> str:
        return "inspect with CLI"

    @app.post("/pause")
    async def pause(request: Request, csrf_token: str = Form(...)):
        if not validate_token(request.session, csrf_token):
            raise HTTPException(403, "Invalid CSRF token")
        paths = default_paths()
        paths.pause_file.write_text("paused by dashboard\n", encoding="utf-8")
        return RedirectResponse("/", status_code=303)

    @app.post("/resume")
    async def resume(request: Request, csrf_token: str = Form(...)):
        if not validate_token(request.session, csrf_token):
            raise HTTPException(403, "Invalid CSRF token")
        paths = default_paths()
        if paths.pause_file.exists():
            paths.pause_file.unlink()
        return RedirectResponse("/", status_code=303)

    @app.get("/leads", response_class=HTMLResponse)
    async def leads(request: Request):
        origin = origin_filter(request)
        with database.session() as session:
            query = session.query(Company, LeadScore).join(
                LeadScore, Company.id == LeadScore.company_id
            )
            if origin == "production":
                query = query.filter(
                    Company.data_origin == "production", LeadScore.data_origin == "production"
                )
            elif origin == "demo":
                query = query.filter(Company.data_origin.in_(["synthetic", "owner_test"]))
            elif origin == "external":
                query = query.filter(
                    Company.data_origin == "external_research",
                    LeadScore.data_origin == "external_research",
                )
            rows = query.all()
            rows.sort(key=lambda item: commercial_order_key(*item))
            company_ids = {company.id for company, _score in rows}
            contacts = {
                contact.company_id: contact
                for contact in session.query(Contact)
                .filter(Contact.company_id.in_(company_ids))
                .all()
            }
            drafts: dict[str, Draft] = {}
            for draft in (
                session.query(Draft)
                .filter(Draft.company_id.in_(company_ids))
                .order_by(Draft.created_at.desc())
                .all()
            ):
                drafts.setdefault(draft.company_id, draft)
        body = "".join(
            f"<tr><td><a href='/leads/{escape(score.id)}'>{escape(company.name)}</a></td>"
            f"<td><strong>{score.opportunity_fit_grade or '—'} {score.opportunity_fit_score if score.opportunity_fit_score is not None else '—'}</strong></td>"
            f"<td>{score.reachability_grade or '—'} {score.reachability_score if score.reachability_score is not None else '—'}</td>"
            f"<td>{escape(score.priority or 'not scored')}</td>"
            f"<td>{escape(score.primary_project_type or 'unknown')}</td>"
            f"<td>{escape(display_label(score.primary_buyer_persona))}</td>"
            f"<td>{escape(draft_contact_status(contacts.get(company.id)))}</td>"
            f"<td>{escape(draft_dispatch_state(drafts.get(company.id), company, contacts.get(company.id)))}</td>"
            f"<td>{escape(company.data_origin)}</td></tr>"
            for company, score in rows
        )
        content = (
            f"<p class='eyebrow'>Evidence ledger</p><h1>Leads</h1><p class='muted'>{origin_links(origin)}<br>Commercial ordering is Opportunity Fit, then Reachability, then legacy score. Dispatch eligibility is separate and rechecked at dispatch.</p><table><thead><tr><th>Company</th><th>Opportunity Fit</th><th>Reachability</th><th>Priority</th><th>Primary project</th><th>Buyer persona</th><th>Contact status</th><th>Dispatch status</th><th>Origin</th></tr></thead><tbody>"
            + (
                body
                or "<tr><td colspan='9'>No leads yet. Run the offline demo or a production research cycle.</td></tr>"
            )
            + "</tbody></table>"
        )
        return layout(request, "Leads", content)

    @app.get("/leads/{lead_id}", response_class=HTMLResponse)
    async def lead_detail(request: Request, lead_id: str):
        with database.session() as session:
            score = session.get(LeadScore, lead_id)
            if score is None:
                score = (
                    session.query(LeadScore)
                    .filter(LeadScore.company_id == lead_id)
                    .order_by(LeadScore.scored_at.desc())
                    .first()
                )
            if score is None:
                raise HTTPException(404, "Lead not found")
            company = session.get(Company, score.company_id)
            sources = (
                session.query(Source)
                .filter(Source.company_id == score.company_id)
                .order_by(Source.retrieved_at.desc())
                .all()
            )
            signals = session.query(Signal).filter(Signal.company_id == score.company_id).all()
            pains = (
                session.query(PainHypothesis)
                .filter(PainHypothesis.company_id == score.company_id)
                .all()
            )
            contact = (
                session.query(Contact)
                .filter(Contact.company_id == score.company_id)
                .order_by(Contact.first_seen_at)
                .first()
            )
            drafts = (
                session.query(Draft)
                .filter(Draft.company_id == score.company_id)
                .order_by(Draft.created_at.desc())
                .all()
            )
            last_contacted = (
                session.query(OutboxMessage)
                .join(Draft, Draft.id == OutboxMessage.draft_id)
                .filter(OutboxMessage.state == "sent", Draft.company_id == score.company_id)
                .order_by(OutboxMessage.sent_at.desc())
                .first()
            )
            import_run = None
            import_record = None
            run_ids = [source.originating_run_id for source in sources if source.originating_run_id]
            if run_ids:
                import_run = session.get(Run, run_ids[0])
                if import_run:
                    import_record = (
                        session.query(ImportRecord)
                        .filter(ImportRecord.run_id == import_run.id)
                        .first()
                    )
        if company is None:
            raise HTTPException(404, "Company not found")
        evidence = (
            "".join(
                f"<li><a href='{escape(safe_href(source.url))}'>{escape(source.title)}</a> · {escape(source.source_tier)} · {escape(source.retrieved_at.date().isoformat())}<br>{escape(source.excerpt)}</li>"
                for source in sources
            )
            or "<li>No evidence persisted.</li>"
        )
        fact_list = (
            "".join(
                f"<li>{escape(signal.observed_signal)} <small>({escape(signal.signal_type)})</small></li>"
                for signal in signals
            )
            or "<li>None</li>"
        )
        pain_list = (
            "".join(
                f"<li>{escape(pain.hypothesis)} <small>({pain.confidence:.2f})</small></li>"
                for pain in pains
            )
            or "<li>None</li>"
        )
        contact_html = (
            f"{escape(contact.display_name or 'Unnamed contact')} · {escape(contact.title or 'Title not recorded')} · {escape(contact.email)}<br>source: <a href='{escape(safe_href(contact.source_url))}'>{escape(contact.source_url)}</a><br>no guessed address: {contact.no_guessed_address} · MX: {escape(contact.mx_result or 'not checked')} · source verification: {escape(contact.source_verification_status)}"
            if contact
            else "No eligible official-domain contact."
        )
        draft_html = (
            "".join(
                f"<h3>{escape(draft.subject)} · {escape(draft_status_label(draft.status))} · validation: {escape(draft_validation_summary(draft))}</h3><pre class='wrapped'>{escape(draft.plain_text_body)}</pre>"
                for draft in drafts
            )
            or "No draft."
        )
        import_html = (
            f"<div class='card' style='margin-top:20px'><h2>External research import</h2><p>Import ID: {escape(import_record.id if import_record else '')}<br>Generated: {escape(str(import_record.generated_at) if import_record else '')}<br>Source: {escape(import_record.source_system if import_record else '')} / {escape(import_record.source_method if import_record else '')}<br>Bundle: {escape(import_record.bundle_hash[:16] if import_record else '')}</p></div>"
            if import_record
            else ""
        )
        dispatch_html = (
            dispatch_detail_html(company, drafts[0], contact)
            if drafts
            else "<h2>Dispatch Eligibility</h2><p><strong>BLOCKED</strong></p><ul><li>No draft is persisted.</li><li>Contact path must be established before dispatch.</li></ul>"
        )
        contacted_html = (
            f"<p><strong>Last contacted:</strong> {escape(str(last_contacted.sent_at))} · "
            f"{escape('Manual' if last_contacted.data_origin == 'manual_send' else last_contacted.mail_provider)}</p>"
            if last_contacted and last_contacted.sent_at
            else "<p><strong>Last contacted:</strong> never</p>"
        )
        content = (
            f"<p class='eyebrow'>Lead detail · {escape(company.data_origin)}</p><h1>{escape(company.name)}</h1>"
            f"<p><a href='{escape(safe_href(company.official_website))}'>{escape(company.registrable_domain)}</a> · {escape(company.vertical)} · {escape(company.country or 'unknown')} · domain confidence {company.official_domain_confidence:.2f}</p>"
            f"<p><strong>Opportunity Fit {score.opportunity_fit_score if score.opportunity_fit_score is not None else '—'} ({escape(score.opportunity_fit_grade or '—')})</strong> · Reachability {score.reachability_score if score.reachability_score is not None else '—'} ({escape(score.reachability_grade or '—')}) · legacy score {score.total_score}</p>"
            f"<div class='grid'><div class='card'>{contacted_html}{dispatch_html}</div></div>"
            f"{commercial_summary_html(score)}"
            f"<div class='grid'><div class='card'><h2>Observed facts</h2><ul>{fact_list}</ul></div><div class='card'><h2>Pain hypotheses</h2><ul>{pain_list}</ul></div><div class='card'><h2>Contact provenance</h2><p>{contact_html}</p></div></div>"
            f"<div class='card' style='margin-top:20px'><h2>Evidence ledger</h2><ul>{evidence}</ul></div>"
            f"<details class='card' style='margin-top:20px'><summary>Legacy score audit</summary>{score_breakdown_html(score)}</details>"
            f"<div class='card' style='margin-top:20px'><h2>Draft</h2>{draft_html}</div>"
            f"{import_html}"
        )
        return layout(request, "Lead detail", content)

    @app.get("/drafts", response_class=HTMLResponse)
    async def drafts(request: Request):
        origin = origin_filter(request)
        with database.session() as session:
            query = session.query(Draft)
            if origin == "production":
                query = query.filter(Draft.data_origin == "production")
            elif origin == "external":
                query = query.filter(Draft.data_origin == "external_research")
            elif origin == "demo":
                query = query.filter(Draft.data_origin.in_(["synthetic", "owner_test"]))
            rows = query.order_by(Draft.created_at.desc()).all()
            companies = {
                company.id: company
                for company in session.query(Company)
                .filter(Company.id.in_({draft.company_id for draft in rows}))
                .all()
            }
            contacts = {
                contact.id: contact
                for contact in session.query(Contact)
                .filter(Contact.id.in_({draft.contact_id for draft in rows if draft.contact_id}))
                .all()
            }

            def contact_for(draft: Draft) -> Contact | None:
                return contacts.get(draft.contact_id or "")

        body = "".join(
            f"<tr><td>{escape(companies[d.company_id].name)}</td><td>{escape(d.subject)}</td><td>{escape(draft_status_label(d.status))}</td><td>{escape('PASS' if (d.quality_findings or {}).get('passed') else 'REVIEW')}</td><td>{escape(draft_contact_status(contact_for(d)))}</td><td>{escape(companies[d.company_id].permission_basis)}</td><td>{escape(draft_dispatch_state(d, companies[d.company_id], contact_for(d)))}</td><td>{escape(d.data_origin)}</td><td><details><summary>Preview</summary><pre>{escape(d.plain_text_body)}</pre></details></td></tr>"
            for d in rows
        )
        content = (
            f"<p class='eyebrow'>Guarded content</p><h1>Drafts</h1><p>{origin_links(origin)}</p><p class='muted'>Content: PASS means the deterministic draft validator passed. Send: BLOCKED is independent and remains fail-closed until contact, permission, and provider gates pass.</p><table><thead><tr><th>Company</th><th>Subject</th><th>Status</th><th>Draft validation</th><th>Contact status</th><th>Permission</th><th>Send readiness</th><th>Origin</th><th>Preview</th></tr></thead><tbody>"
            + (body or "<tr><td colspan='9'>No drafts yet.</td></tr>")
            + "</tbody></table>"
        )
        return layout(request, "Drafts", content)

    @app.get("/messages", response_class=HTMLResponse)
    async def messages(request: Request):
        origin = origin_filter(request)
        with database.session() as session:
            query = (
                session.query(OutboxMessage, Draft, Company, Contact)
                .join(Draft, Draft.id == OutboxMessage.draft_id)
                .join(Company, Company.id == Draft.company_id)
                .outerjoin(Contact, Contact.id == Draft.contact_id)
            )
            if origin == "production":
                query = query.filter(OutboxMessage.data_origin.in_(["production", "manual_send"]))
            elif origin == "external":
                query = query.filter(
                    OutboxMessage.data_origin.in_(["external_research", "manual_send"])
                )
            elif origin == "demo":
                query = query.filter(OutboxMessage.data_origin.in_(["synthetic", "owner_test"]))
            rows = query.order_by(OutboxMessage.scheduled_for.desc()).all()
        body = "".join(
            f"<tr><td>{escape(m.id)}</td><td>{escape(company.name)}</td><td>{escape(contact.email if contact else '')}</td><td>{escape(m.manual_subject or draft.subject)}</td><td>{escape(m.state)}</td><td>{escape('Manual' if m.data_origin == 'manual_send' else m.mail_provider)}</td><td>{escape(m.data_origin)}</td><td>{escape((m.sent_at or m.scheduled_for).isoformat())}</td><td>{escape(m.rfc_message_id or 'pending')}</td><td>{escape(m.last_error_category or '')}</td></tr>"
            for m, draft, company, contact in rows
        )
        content = (
            f"<p class='eyebrow'>Outbox</p><h1>Messages and replies</h1><p>{origin_links(origin)}</p><p class='muted'>Prospect Sent excludes owner transport tests. The system never auto-replies; substantive inbound messages require owner action.</p><table><thead><tr><th>ID</th><th>Company</th><th>Recipient</th><th>Subject</th><th>State</th><th>Transport/source</th><th>Origin</th><th>Sent/scheduled</th><th>RFC Message-ID</th><th>Error category</th></tr></thead><tbody>"
            + (body or "<tr><td colspan='10'>No messages yet.</td></tr>")
            + "</tbody></table>"
        )
        return layout(request, "Messages", content)

    @app.get("/imports", response_class=HTMLResponse)
    async def imports(request: Request):
        with database.session() as session:
            rows = (
                session.query(ImportRecord)
                .order_by(ImportRecord.imported_at.desc())
                .limit(50)
                .all()
            )
            audit_by_import = {
                row.id: (
                    session.query(AuditEvent)
                    .filter(
                        AuditEvent.action.in_(
                            [
                                "external_research_imported",
                                "external_research_import_reconciled",
                            ]
                        ),
                        AuditEvent.entity_id == row.id,
                    )
                    .order_by(AuditEvent.timestamp.desc())
                    .first()
                )
                for row in rows
            }
        body = "".join(
            f"<tr><td>{escape(row.id)}</td><td>{escape(row.imported_at.isoformat())}</td><td>{escape(row.filename)}</td><td>{row.company_count}</td><td>{row.accepted_count}/{row.rejected_count}</td><td>{row.warning_count}</td><td>{row.contacts_verified}/{row.contacts_unverified}</td><td>{escape(import_draft_counter_text(row, audit_by_import[row.id]))}</td><td>{escape(import_draft_validation_text(audit_by_import[row.id]))}</td><td>{row.prospect_messages_sent}</td><td>{escape(row.bundle_hash[:16])}</td></tr>"
            for row in rows
        )
        content = (
            "<p class='eyebrow'>External research</p><h1>Imports</h1><p class='muted'>Manual ChatGPT research is real prospect research with a distinct origin. Imports never create prospect messages. Draft pass/persisted counts are independent from send readiness.</p><table><thead><tr><th>Import ID</th><th>Time</th><th>Filename</th><th>Companies</th><th>Accepted/rejected</th><th>Warnings</th><th>Contacts verified/unverified</th><th>Draft counters</th><th>Draft validation</th><th>Prospect sends</th><th>Bundle hash</th></tr></thead><tbody>"
            + (body or "<tr><td colspan='11'>No external research imports.</td></tr>")
            + "</tbody></table>"
        )
        return layout(request, "Imports", content)

    @app.get("/suppressions", response_class=HTMLResponse)
    async def suppressions(request: Request):
        with database.session() as session:
            rows = (
                session.query(Suppression)
                .filter(Suppression.removed_at.is_(None))
                .order_by(Suppression.created_at.desc())
                .all()
            )
        body = "".join(
            f"<tr><td>{escape(s.scope)}</td><td>{escape(s.normalized_value)}</td><td>{escape(s.reason)}</td><td>{escape(s.created_at.isoformat())}</td></tr>"
            for s in rows
        )
        content = (
            "<p class='eyebrow'>Recipient respect</p><h1>Suppressions</h1><table><thead><tr><th>Scope</th><th>Value</th><th>Reason</th><th>Created</th></tr></thead><tbody>"
            + (body or "<tr><td colspan='4'>No active suppressions.</td></tr>")
            + "</tbody></table>"
        )
        return layout(request, "Suppressions", content)

    @app.get("/runs", response_class=HTMLResponse)
    async def runs(request: Request):
        with database.session() as session:
            rows = session.query(Run).order_by(Run.started_at.desc()).limit(50).all()
        body = "".join(
            f"<tr><td>{escape(r.logical_run_key or r.run_key)}<br><span class='muted'>{escape(r.run_key)}</span></td>"
            f"<td>{r.attempt_number}</td><td>{escape(r.run_mode)}</td><td>{escape(r.data_origin)}</td>"
            f"<td>{escape(r.status)}</td><td>{'yes' if r.retryable else 'no'}</td>"
            f"<td>{escape(r.retry_not_before.isoformat() if r.retry_not_before else '')}</td>"
            f"<td>{escape(r.provider_request_id or '')}</td>"
            f"<td>{escape(r.started_at.isoformat() if r.started_at else '')}<br>"
            f"{escape(r.finished_at.isoformat() if r.finished_at else 'running')}</td>"
            f"<td>{escape(str(r.counters))}<br>prospect_messages_sent=0</td>"
            f"<td>{escape(r.error_category or '')}<br>{escape(r.error_summary or '')}</td></tr>"
            for r in rows
        )
        content = (
            "<p class='eyebrow'>Audit trail</p><h1>Runs</h1><p class='muted'>Production attempts show logical key, attempt number, terminal status, retry metadata, provider request ID, usage, timestamps, and zero-send counters.</p><table><thead><tr><th>Logical / physical run</th><th>Attempt</th><th>Mode</th><th>Origin</th><th>Status</th><th>Retryable</th><th>Retry not before</th><th>Request ID</th><th>Started / finished</th><th>Counters</th><th>Error category / sanitized error</th></tr></thead><tbody>"
            + (body or "<tr><td colspan='11'>No runs yet.</td></tr>")
            + "</tbody></table>"
        )
        return layout(request, "Runs", content)

    @app.get("/settings", response_class=HTMLResponse)
    async def settings_page(request: Request):
        with database.session() as session:
            checkpoint = session.get(
                MailboxCheckpoint,
                {"mail_provider": "namecheap_private_email", "folder": "INBOX"},
            )
            uncertain = (
                session.query(OutboxMessage).filter(OutboxMessage.state == "uncertain").count()
            )
        sync_status = (
            f"UID {checkpoint.uid}; {checkpoint.updated_at.isoformat()}"
            if checkpoint
            else "not run"
        )
        content = f"<p class='eyebrow'>Configuration</p><h1>Settings</h1><div class='grid'><div class='card'><h2>Mode</h2><p>{'Live enabled' if settings.live.enabled else 'Dry run / live disabled'}</p><p>Production research gate: {'complete' if settings.live.production_research_completed else 'incomplete'}</p></div><div class='card'><h2>Sender</h2><p>{escape(settings.sender.display_name)}<br>{escape(settings.sender.email[:1] + '***@' + settings.sender.email.split('@', 1)[1] if '@' in settings.sender.email else '(not configured)')}</p></div><div class='card'><h2>Mail transport</h2><p>{escape(settings.providers.mail_provider)}<br>SMTP {escape(settings.providers.smtp_host)}:{settings.providers.smtp_port}<br>IMAP {escape(settings.providers.imap_host)}:{settings.providers.imap_port}</p></div><div class='card'><h2>Mailbox sync</h2><p>Reply sync: {'enabled' if settings.providers.mail_reply_sync else 'disabled'}<br>Last INBOX checkpoint: {escape(sync_status)}<br>Uncertain deliveries: {uncertain}</p></div><div class='card'><h2>Window</h2><p>{escape(settings.schedule.timezone)}<br>{escape(settings.schedule.send_start)}–{settings.schedule.send_end}</p></div><div class='card'><h2>Research budgets</h2><p>queries {settings.research.max_queries}; candidates {settings.research.max_candidates}; deep {settings.research.max_deep_research}; qualified {settings.research.max_qualified}<br>web-search {settings.research.max_web_search_calls}; analysis {settings.research.max_analysis_calls}; HTTP {settings.research.max_http_requests}; pages/domain {settings.research.max_pages_per_domain}</p></div><div class='card'><h2>Meeting link</h2><p>{'Configured' if settings.sender.meeting_link else 'Not configured'}</p></div></div><p class='muted'>Use <code>./outreachctl setup</code> for changes. The mailbox password is held only by the OS credential store and is never rendered here.</p>"
        return layout(request, "Settings", content)

    return app


def run_dashboard(host: str = "127.0.0.1", port: int = 8765) -> None:
    import uvicorn

    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Dashboard is localhost-only unless an explicit deployment change is made")
    uvicorn.run(create_app(), host=host, port=port)
