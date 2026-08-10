from __future__ import annotations

import csv
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer
from sqlalchemy import select

from .compliance import (
    NAMECHEAP_AUTO_SEND_BASES,
    advisory_dns_checks,
    can_send,
    evaluate_dispatch_eligibility,
    validate_live_preconditions,
)
from .config import (
    PRIVATE_EMAIL_POLICY_VERSION,
    Settings,
    load_settings,
    mask_email,
    write_settings,
)
from .contact_service import ContactAttachError, attach_contact
from .dashboard.app import run_dashboard
from .db import (
    CURRENT_SCHEMA_VERSION,
    AuditEvent,
    Company,
    Contact,
    Database,
    Draft,
    ImportRecord,
    LeadScore,
    OutboxMessage,
    PainHypothesis,
    Run,
    SchemaVersion,
    Signal,
    Source,
)
from .due import decide_due
from .enums import SuppressionScope
from .explicit_send import ExplicitSendError, preview_explicit_send, send_explicit
from .locks import application_lock
from .manual_send import (
    ManualSendError,
    manual_send_candidates,
    reconcile_manual_sends,
    record_manual_send,
)
from .paths import AppPaths, default_paths
from .pipeline import dispatch_pending, run_synthetic_demo
from .providers.base import MailTransportError
from .providers.private_email_provider import PrivateEmailProvider
from .research.canonicalize import registrable_domain, validate_public_url
from .research.contacts import check_mx
from .research.import_bridge import (
    ExternalResearchBundle,
    ImportBridgeError,
    generation_prompt,
    import_bundle,
    reconcile_import_drafts,
    template_bundle,
    validate_bundle_file,
    verify_import_contacts,
)
from .research.production import ProductionResearchError, run_production_research
from .score_service import commercial_order_key, recompute_scores, score_rows
from .secrets import OPENAI_ACCOUNT, OPENAI_API_KEY, default_secret_store
from .suppression import active_suppressions, add_suppression, remove_suppression

app = typer.Typer(
    help="EliOra's local-first, evidence-led outreach operations tool.", no_args_is_help=True
)
auth_app = typer.Typer(help="Authenticate external providers.")
schedule_app = typer.Typer(help="Install or inspect the OS-native hourly scheduler.")
lead_app = typer.Typer(help="Inspect scored leads.")
scores_app = typer.Typer(help="Recompute and inspect commercial prioritization scores.")
draft_app = typer.Typer(help="Inspect and review drafts.")
manual_send_app = typer.Typer(help="Record prospect emails sent manually outside EliOra.")
suppress_app = typer.Typer(help="Manage permanent recipient suppressions.")
live_app = typer.Typer(help="Enable or disable live outreach.")
privacy_app = typer.Typer(help="Manage private cached research data.")
secrets_app = typer.Typer(help="Manage mailbox and OpenAI secrets in the OS credential store.")
config_app = typer.Typer(help="Inspect or edit private outreach configuration.")
research_app = typer.Typer(help="Validate and import owner-created external research bundles.")
app.add_typer(auth_app, name="auth")
app.add_typer(schedule_app, name="schedule")
app.add_typer(lead_app, name="lead")
app.add_typer(scores_app, name="scores")
app.add_typer(draft_app, name="draft")
app.add_typer(manual_send_app, name="manual-send")
app.add_typer(suppress_app, name="suppress")
app.add_typer(live_app, name="live")
app.add_typer(privacy_app, name="privacy")
app.add_typer(secrets_app, name="secrets")
app.add_typer(config_app, name="config")
app.add_typer(research_app, name="research")


def _paths_db() -> tuple[AppPaths, Database]:
    paths = default_paths()
    database = Database(paths=paths)
    database.create()
    return paths, database


def _schema_migration_status(session: Any) -> tuple[bool, str]:
    """Report the applied schema set against the one current code version."""
    applied = {row.version for row in session.query(SchemaVersion).all()}
    expected = set(range(1, CURRENT_SCHEMA_VERSION + 1))
    missing = sorted(expected - applied)
    latest = max(applied, default=0)
    if missing:
        return False, f"version {latest}; missing {', '.join(str(value) for value in missing)}"
    return True, f"version {latest}"


def _echo_production_failure(exc: ProductionResearchError) -> None:
    heading = (
        "Production research retry blocked"
        if exc.category == "retry_cooldown"
        else f"Production research failed [{exc.category}]"
    )
    typer.echo(heading)
    typer.echo(f"category: {exc.category}")
    typer.echo(f"retryable: {'yes' if exc.retryable else 'no'}")
    typer.echo(
        "retry_not_before: "
        + (exc.retry_not_before.isoformat() if exc.retry_not_before else "none")
    )
    typer.echo(f"request_id: {exc.request_id or 'none'}")
    if exc.action:
        typer.echo(f"action: {exc.action}")
    typer.echo(f"details: {str(exc)[:500]}")
    typer.echo("prospect_messages_sent: 0")


@research_app.command("schema")
def research_schema(output: Path | None = typer.Option(None, "--output")) -> None:
    """Print or write the strict external-research JSON Schema."""
    payload = (
        json.dumps(ExternalResearchBundle.model_json_schema(), indent=2, sort_keys=True) + "\n"
    )
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
        typer.echo(f"Wrote external research schema to {output}")
    else:
        typer.echo(payload, nl=False)


@research_app.command("template")
def research_template(output: Path | None = typer.Option(None, "--output")) -> None:
    """Print or write a clearly synthetic educational bundle."""
    payload = json.dumps(template_bundle(), indent=2) + "\n"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
        typer.echo(f"Wrote synthetic educational template to {output}")
    else:
        typer.echo(payload, nl=False)


@research_app.command("prompt")
def research_prompt(
    max_companies: int = typer.Option(5, "--max-companies", min=1, max=20),
) -> None:
    """Print the reusable ChatGPT research-generation prompt."""
    typer.echo(generation_prompt(max_companies))


def _echo_import_validation_error(exc: ImportBridgeError) -> None:
    typer.echo(f"Research bundle rejected: {exc}")
    for error in exc.errors[:30]:
        typer.echo(f"- {error}")
    if len(exc.errors) > 30:
        typer.echo(f"- ... {len(exc.errors) - 30} more validation errors")


def _echo_research_validation_details(result: Any) -> None:
    if result.contact_verifications:
        typer.echo("Contact verification:")
        by_id = {item.external_company_id: item for item in result.bundle.companies}
        for external_company_id, verification in result.contact_verifications.items():
            company = by_id[external_company_id]
            typer.echo(f"  {company.company_name}: {verification.status} — {verification.detail}")
    if result.draft_validations:
        typer.echo("Draft validation:")
        for draft in result.draft_validations:
            if draft.passed:
                typer.echo(f"  {draft.company_name}: PASS (content/evidence)")
            else:
                typer.echo(f"  {draft.company_name}: REVIEW")
                for error in draft.errors:
                    typer.echo(f"    - {error}")
            if draft.warnings:
                for warning in draft.warnings:
                    typer.echo(f"    - warning: {warning}")
            if draft.contact_dependent_issues:
                for issue in draft.contact_dependent_issues:
                    typer.echo(f"    - contact policy: {issue}")
            if not draft.send_ready:
                typer.echo(
                    "    - send-ready: blocked (" + ", ".join(draft.dispatch_blocked_reasons) + ")"
                )


@research_app.command("validate")
def research_validate(
    file: Path = typer.Argument(..., exists=False),
    verify_sources: bool = typer.Option(
        False,
        "--verify-sources",
        help="Fetch public contact sources with the hardened crawler; failures remain review-only.",
    ),
) -> None:
    """Validate an external research bundle without touching the database."""
    try:
        settings = load_settings(paths=default_paths())
        result = validate_bundle_file(file, verify_sources=verify_sources, settings=settings)
    except ImportBridgeError as exc:
        _echo_import_validation_error(exc)
        raise typer.Exit(code=1) from None
    typer.echo(f"VALID: {file}")
    typer.echo(f"bundle_hash: {result.bundle_hash}")
    for key, value in result.preview.items():
        typer.echo(f"{key}: {value}")
    _echo_research_validation_details(result)
    for warning in result.warnings:
        typer.echo(f"WARNING: {warning}")


@research_app.command("import")
def research_import(
    file: Path = typer.Argument(..., exists=False),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation only; validation still runs."),
    verify_sources: bool = typer.Option(
        False,
        "--verify-sources",
        help="Fetch public contact sources with the hardened crawler; failures remain review-only.",
    ),
    database_path: Path | None = typer.Option(None, "--database"),
) -> None:
    """Validate and atomically import external research with zero prospect sends."""
    paths = default_paths()
    try:
        settings = load_settings(paths=paths)
        result = validate_bundle_file(file, verify_sources=verify_sources, settings=settings)
    except ImportBridgeError as exc:
        _echo_import_validation_error(exc)
        raise typer.Exit(code=1) from None
    except Exception as exc:
        typer.echo(f"Research import failed; transaction rolled back ({type(exc).__name__}).")
        raise typer.Exit(code=1) from None
    preview = result.preview
    typer.echo("External Research Import")
    typer.echo("------------------------")
    for key, value in preview.items():
        label = key.replace("_", " ").capitalize()
        typer.echo(f"{label}: {value}")
    _echo_research_validation_details(result)
    typer.echo("This will add research records only.")
    typer.echo("Prospect messages sent: 0")
    typer.echo("Live mode will not change.")
    if not yes and not typer.confirm("Continue?", default=False):
        typer.echo("Import cancelled; no database mutation performed.")
        return
    database = Database(path=database_path, paths=paths) if database_path else Database(paths=paths)
    try:
        imported = import_bundle(
            database,
            settings,
            result,
            confirmation_at=datetime.now(timezone.utc),
            verify_sources=verify_sources,
        )
    except ImportBridgeError as exc:
        _echo_import_validation_error(exc)
        raise typer.Exit(code=1) from None
    for key, value in imported.items():
        typer.echo(f"{key}: {value}")


@research_app.command("show-import")
def research_show_import(import_id: str) -> None:
    """Show a private import audit record without rendering raw bundle content."""
    _paths, database = _paths_db()
    with database.session() as session:
        row = session.get(ImportRecord, import_id)
        if row is None:
            raise typer.BadParameter("Import record not found")
        for key in (
            "id",
            "bundle_hash",
            "schema_version",
            "generated_at",
            "imported_at",
            "source_system",
            "source_method",
            "filename",
            "company_count",
            "accepted_count",
            "rejected_count",
            "warning_count",
            "evidence_count",
            "contacts_verified",
            "contacts_unverified",
            "drafts_ready",
            "drafts_needs_review",
            "prospect_messages_sent",
            "status",
        ):
            typer.echo(f"{key}: {getattr(row, key)}")
        audit = (
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
        if audit and isinstance(audit.metadata_json, dict):
            for key in (
                "drafts_passing_validation",
                "drafts_needing_review",
                "drafts_send_ready",
                "drafts_persisted",
                "prospect_messages_sent",
            ):
                if key in audit.metadata_json:
                    typer.echo(f"{key}: {audit.metadata_json[key]}")
            typer.echo(
                "draft_validation_semantics: content/evidence pass is separate from send readiness"
            )
            typer.echo("draft_validation:")
            typer.echo(
                json.dumps(
                    audit.metadata_json.get("draft_validation", []),
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )


@research_app.command("reconcile-import")
def research_reconcile_import(
    import_id: str = typer.Argument(...),
    file: Path = typer.Argument(..., exists=False),
) -> None:
    """Materialize missing drafts for an existing import without re-importing it."""
    paths = default_paths()
    settings = load_settings(paths=paths)
    try:
        validation = validate_bundle_file(file, settings=settings)
        result = reconcile_import_drafts(Database(paths=paths), settings, import_id, validation)
    except ImportBridgeError as exc:
        _echo_import_validation_error(exc)
        raise typer.Exit(code=1) from None
    for key, value in result.items():
        typer.echo(f"{key}: {value}")


@research_app.command("verify-import")
def research_verify_import(import_id: str = typer.Argument(...)) -> None:
    """Recheck only contacts belonging to one external research import."""
    try:
        result = verify_import_contacts(Database(paths=default_paths()), import_id)
    except ImportBridgeError as exc:
        _echo_import_validation_error(exc)
        raise typer.Exit(code=1) from None
    for key, value in result.items():
        if key == "results":
            typer.echo("results:")
            for item in value:
                typer.echo(f"  {item['email']}: {item['status']} — {item['reason']}")
        else:
            typer.echo(f"{key}: {value}")


@app.command()
def setup(
    advanced: bool = typer.Option(
        False, "--advanced", help="Edit every non-secret configuration field."
    ),
) -> None:
    """Create or update the private config with a concise, idempotent setup."""
    paths = default_paths()
    config_exists = paths.config_file.exists()
    current = load_settings(paths=paths)

    def ask(label: str, default: str = "") -> str:
        return typer.prompt(label, default=default, show_default=bool(default))

    raw = current.model_dump(mode="python")
    _fill_missing_setup_defaults(raw)
    company = raw["company"]
    sender = raw["sender"]

    if advanced:
        _setup_advanced(raw, ask)
    else:
        if not raw["providers"].get("mailbox_username"):
            raw["providers"]["mailbox_username"] = sender["email"]
        if not sender.get("postal_address", "").strip():
            typer.echo(
                "A one-time private postal address is required for compliant outreach. "
                "It is saved only in the private config outside the repository."
            )
            sender["postal_address"] = ask("Private physical postal address")
            if not sender["postal_address"].strip():
                raise typer.BadParameter("Private physical postal address cannot be blank")
        if not sender.get("meeting_link", "").strip():
            sender["meeting_link"] = ask(
                "Optional https:// meeting link (blank to skip)", ""
            ).strip()
        if _policy_acknowledgement_needed(current):
            typer.echo(
                "Namecheap policy gate: prospects without an eligible permission basis may "
                "be researched, scored, drafted, and exported, but never auto-dispatched."
            )
            acknowledged = typer.confirm("Acknowledge this policy gate", default=False)
            raw["providers"]["permission_policy_acknowledged"] = acknowledged
            raw["providers"]["permission_policy_version"] = (
                PRIVATE_EMAIL_POLICY_VERSION if acknowledged else None
            )

    try:
        _validate_setup_urls(company)
        settings = Settings.model_validate(raw)
        if not settings.sender.postal_address.strip():
            raise ValueError("A physical postal address is required before live mode")
        if (
            not settings.sender.email
            or not settings.sender.reply_to
            or not settings.sender.owner_bcc
        ):
            raise ValueError("Sender, Reply-To, and owner BCC addresses are required")
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if not config_exists:
        typer.echo(_setup_summary(settings))
        if not typer.confirm("Save this configuration?", default=True):
            raise typer.Abort()
    target = write_settings(settings, paths=paths)
    typer.echo(f"Saved private configuration to {target}")
    typer.echo(
        "Live mode state was preserved. Use config show for a safe summary; no secret was requested."
    )


def _policy_acknowledgement_needed(settings: Settings) -> bool:
    return settings.providers.permission_basis_required and (
        not settings.providers.permission_policy_acknowledged
        or settings.providers.permission_policy_version != PRIVATE_EMAIL_POLICY_VERSION
    )


def _fill_missing_setup_defaults(raw: dict[str, Any]) -> None:
    """Treat blank stable fields as unset while preserving deliberate false/empty lists."""
    defaults = Settings().model_dump(mode="python")
    fields = {
        "company": ("legal_name", "website"),
        "sender": (
            "display_name",
            "title",
            "email",
            "reply_to",
            "owner_bcc",
            "disclosure",
            "opt_out",
        ),
        "schedule": ("timezone", "research_time", "send_start", "send_end", "fallback_timezone"),
        "providers": (
            "openai_model",
            "mail_provider",
            "smtp_host",
            "smtp_security",
            "imap_host",
            "imap_security",
            "research_user_agent",
        ),
    }
    for section, names in fields.items():
        for name in names:
            value = raw[section].get(name)
            if value is None or (isinstance(value, str) and not value.strip()):
                raw[section][name] = defaults[section][name]


def _validate_setup_urls(company: dict[str, Any]) -> None:
    website = str(company.get("website", ""))
    if website:
        validate_public_url(website, resolve=False)
    for url in company.get("relevant_site_urls", []):
        validate_public_url(str(url), resolve=False)


def _setup_summary(settings: Settings) -> str:
    return (
        "\nEffective setup:\n"
        f"  Company: {settings.company.legal_name}\n"
        f"  Website: {settings.company.website}\n"
        f"  Sender: {mask_email(settings.sender.email)} ({settings.sender.title})\n"
        f"  Postal address: {'configured privately' if settings.sender.postal_address else 'missing'}\n"
        f"  Meeting link: {'configured' if settings.sender.meeting_link else 'not configured'}\n"
        f"  Timezone/window: {settings.schedule.timezone} "
        f"{settings.schedule.send_start}–{settings.schedule.send_end}\n"
        f"  Daily recommendations: {settings.limits.recommended_daily_initials} initial / "
        f"{settings.limits.recommended_daily_followups} follow-up; hard prospect cap "
        f"{settings.limits.hard_daily_prospect_messages}\n"
        f"  Mail provider: {settings.providers.mail_provider}"
    )


def _setup_advanced(raw: dict[str, Any], ask) -> None:
    company = raw["company"]
    sender = raw["sender"]
    schedule = raw["schedule"]
    limits = raw["limits"]
    providers = raw["providers"]
    targeting = raw["targeting"]
    research = raw["research"]

    company["legal_name"] = ask("Company legal name", company["legal_name"])
    company["website"] = ask("Public website", company["website"])
    company["relevant_site_urls"] = _csv(
        ask(
            "Optional relevant public site URLs (comma-separated)",
            ",".join(company.get("relevant_site_urls", [])),
        )
    )
    sender["display_name"] = ask("Sender display name", sender["display_name"])
    sender["title"] = ask("Sender title", sender["title"])
    sender["email"] = ask("Authenticated sender email", sender["email"])
    sender["reply_to"] = ask("Reply-To email", sender["reply_to"])
    sender["owner_bcc"] = ask("Owner/BCC email", sender["owner_bcc"])
    sender["postal_address"] = ask("Private physical postal address", sender["postal_address"])
    if not sender["postal_address"].strip():
        raise typer.BadParameter("Private physical postal address cannot be blank")
    sender["disclosure"] = ask("Business outreach disclosure", sender["disclosure"])
    sender["opt_out"] = ask("Reply-based opt-out wording", sender["opt_out"])
    sender["meeting_link"] = ask("Optional https:// meeting link", sender.get("meeting_link", ""))
    schedule["timezone"] = ask("Timezone", schedule["timezone"])
    schedule["research_time"] = ask("Daily research time", schedule["research_time"])
    schedule["send_start"] = ask("Weekday send-window start", schedule["send_start"])
    schedule["send_end"] = ask("Weekday send-window end", schedule["send_end"])
    limits["recommended_daily_initials"] = _ask_int(
        ask("Recommended daily initial cap", str(limits["recommended_daily_initials"]))
    )
    limits["recommended_daily_followups"] = _ask_int(
        ask("Recommended daily follow-up cap", str(limits["recommended_daily_followups"]))
    )
    limits["hard_daily_followups"] = _ask_int(
        ask("Hard daily follow-up cap", str(limits["hard_daily_followups"]))
    )
    limits["hard_daily_prospect_messages"] = _ask_int(
        ask("Hard daily prospect-message cap", str(limits["hard_daily_prospect_messages"]))
    )
    limits["hard_daily_recipients"] = _ask_int(
        ask("Hard daily recipient cap", str(limits["hard_daily_recipients"]))
    )
    for field, label in (
        ("openai_calls", "OpenAI daily call cap"),
        ("web_search_calls", "Web-search daily call cap"),
        ("pages_fetched", "Daily fetched-page cap"),
        ("companies_researched", "Daily researched-company cap"),
        ("drafts_generated", "Daily generated-draft cap"),
    ):
        limits[field] = _ask_int(ask(label, str(limits[field])))
    delay = _csv(
        ask("Random delay minutes (min,max)", ",".join(map(str, limits["random_delay_minutes"])))
    )
    if len(delay) != 2:
        raise typer.BadParameter("Random delay must be two integers: min,max")
    limits["random_delay_minutes"] = [_ask_int(item) for item in delay]
    providers["openai_model"] = ask("OpenAI model", providers.get("openai_model", "gpt-5.4-mini"))
    providers["mail_provider"] = "namecheap_private_email"
    providers["mailbox_username"] = ask(
        "Private Email mailbox username (full address)",
        providers.get("mailbox_username") or sender["email"],
    )
    providers["mail_reply_sync"] = typer.confirm(
        "Enable tracked Private Email reply synchronization",
        default=providers.get("mail_reply_sync", True),
    )
    providers["smtp_host"] = ask("SMTP host", providers["smtp_host"])
    providers["smtp_port"] = _ask_int(ask("SMTP port", str(providers["smtp_port"])))
    providers["smtp_security"] = ask("SMTP security (ssl or starttls)", providers["smtp_security"])
    providers["imap_host"] = ask("IMAP host", providers["imap_host"])
    providers["imap_port"] = _ask_int(ask("IMAP port", str(providers["imap_port"])))
    providers["imap_security"] = ask("IMAP security (ssl or starttls)", providers["imap_security"])
    providers["mail_timeout_seconds"] = _ask_int(
        ask("Mail timeout seconds", str(providers["mail_timeout_seconds"]))
    )
    providers["permission_policy_acknowledged"] = typer.confirm(
        "Acknowledge the Namecheap policy gate",
        default=providers.get("permission_policy_acknowledged", False),
    )
    providers["permission_policy_version"] = (
        PRIVATE_EMAIL_POLICY_VERSION if providers["permission_policy_acknowledged"] else None
    )
    weights = [
        _ask_int(item)
        for item in ask(
            "Vertical weights healthcare,financial_services,operational_business,sports",
            ",".join(str(value) for value in targeting["vertical_weights"].values()),
        ).split(",")
    ]
    if len(weights) != 4 or sum(weights) != 100:
        raise typer.BadParameter("Vertical weights must be four integers totaling 100")
    targeting["vertical_weights"] = dict(
        zip(
            ("healthcare", "financial_services", "operational_business", "sports"),
            weights,
            strict=True,
        )
    )
    targeting["exclusions"] = _csv(
        ask("Excluded industries/terms (comma-separated)", ",".join(targeting["exclusions"]))
    )
    research["geography"] = ask("Research geography", research["geography"])
    for field, label in (
        ("max_queries", "Max discovery queries per run"),
        ("max_candidates", "Max discovery candidates per run"),
        ("max_deep_research", "Max companies for deep research"),
        ("max_qualified", "Max qualified/drafted leads per run"),
        ("max_web_search_calls", "Max web-search calls per run"),
        ("max_analysis_calls", "Max structured-analysis calls per run"),
        ("max_http_requests", "Max official-site HTTP requests per run"),
        ("max_pages_per_domain", "Max pages per company domain"),
        ("max_run_seconds", "Max research run seconds"),
        ("company_cooldown_days", "Company research cooldown days"),
        ("page_cache_days", "Public-page cache days"),
        ("signal_strong_days", "Strong signal freshness days"),
        ("signal_max_days", "Maximum signal freshness days"),
    ):
        research[field] = _ask_int(ask(label, str(research[field])))
    research["search_context_size"] = ask(
        "Web-search context size (low,medium,high)", research["search_context_size"]
    )


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _ask_int(value: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise typer.BadParameter(f"Expected an integer, got {value!r}") from exc


@auth_app.command("private-email")
def auth_private_email() -> None:
    """Authenticate Private Email SMTP and IMAP without sending a message."""
    settings = load_settings()
    username = settings.providers.mailbox_username or settings.sender.email
    if not username or "@" not in username:
        raise typer.BadParameter(
            "Configure the full Private Email mailbox username with setup first"
        )
    if settings.sender.email and username.lower() != settings.sender.email.lower():
        raise typer.BadParameter(
            "Mailbox username must match sender.email for identity verification"
        )
    provider = PrivateEmailProvider(
        settings.providers,
        username=username,
        secret_store=default_secret_store(),
    )
    try:
        result = provider.connectivity_check()
    except Exception as exc:
        category = getattr(exc, "category", type(exc).__name__)
        raise typer.BadParameter(f"Private Email connectivity failed: {category}") from None
    typer.echo(
        f"Private Email SMTP + IMAP ready for {mask_email(username)}; "
        f"INBOX={result['inbox']} Sent={result['sent']}. No message was sent."
    )


def _mailbox_username(settings: Settings) -> str:
    return settings.providers.mailbox_username or settings.sender.email


def _mail_password_present(settings: Settings) -> tuple[bool, str]:
    username = _mailbox_username(settings)
    if not username:
        return False, "mailbox username not configured"
    try:
        present = bool(default_secret_store().get(username))
    except Exception as exc:
        return False, f"OS credential store unavailable ({type(exc).__name__})"
    return present, "configured" if present else "missing"


def _keychain_secret_present(account: str, key: str) -> tuple[bool, str]:
    try:
        present = bool(default_secret_store().get(account, key))
    except Exception as exc:
        return False, f"unavailable ({type(exc).__name__})"
    return present, "yes" if present else "no"


def _scheduler_state() -> str:
    """Read scheduler state without installing, removing, or starting anything."""
    try:
        system = platform.system()
        if system == "Darwin":
            result = subprocess.run(
                ["launchctl", "print", f"gui/{os.getuid()}/com.eliora.outreach"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            return "installed" if result.returncode == 0 else "not installed"
        if system == "Linux":
            result = subprocess.run(
                ["systemctl", "--user", "is-enabled", "eliora-outreach.timer"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            return "installed" if result.returncode == 0 else "not installed"
        if system == "Windows":
            result = subprocess.run(
                ["schtasks", "/Query", "/TN", "EliOra-Outreach"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            return "installed" if result.returncode == 0 else "not installed"
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return "unknown"


@config_app.command("show")
def config_show() -> None:
    """Show safe effective configuration and private-state locations."""
    paths = default_paths()
    settings = load_settings(paths=paths)
    mailbox_present, mailbox_detail = _mail_password_present(settings)
    openai_keychain, openai_detail = _keychain_secret_present(OPENAI_ACCOUNT, OPENAI_API_KEY)
    database_state = "present" if paths.db.exists() else "not created"
    policy_state = "acknowledged" if not _policy_acknowledgement_needed(settings) else "required"
    typer.echo(f"config_file={paths.config_file}")
    typer.echo(f"database={paths.db} ({database_state})")
    typer.echo(f"logs={paths.logs}")
    typer.echo(f"company={settings.company.legal_name}")
    typer.echo(f"website={settings.company.website}")
    typer.echo(f"relevant_site_urls={len(settings.company.relevant_site_urls)} configured")
    typer.echo(f"sender={mask_email(settings.sender.email)} title={settings.sender.title}")
    typer.echo(f"reply_to={mask_email(settings.sender.reply_to)}")
    typer.echo(f"owner_bcc={mask_email(settings.sender.owner_bcc)}")
    typer.echo(
        f"postal_address={'configured privately' if settings.sender.postal_address else 'missing'}"
    )
    typer.echo(f"meeting_link={'configured' if settings.sender.meeting_link else 'not configured'}")
    typer.echo(
        f"schedule={settings.schedule.timezone} research={settings.schedule.research_time} "
        f"send={settings.schedule.send_start}-{settings.schedule.send_end}"
    )
    typer.echo(
        f"limits=initials:{settings.limits.recommended_daily_initials} "
        f"followups:{settings.limits.recommended_daily_followups} "
        f"hard_prospect:{settings.limits.hard_daily_prospect_messages}"
    )
    typer.echo(
        f"mail_provider={settings.providers.mail_provider} "
        f"mailbox={mask_email(_mailbox_username(settings))} "
        f"smtp={settings.providers.smtp_host}:{settings.providers.smtp_port}/{settings.providers.smtp_security} "
        f"imap={settings.providers.imap_host}:{settings.providers.imap_port}/{settings.providers.imap_security}"
    )
    typer.echo(f"reply_sync={'enabled' if settings.providers.mail_reply_sync else 'disabled'}")
    typer.echo(f"permission_policy={policy_state}")
    typer.echo(f"openai_model={settings.providers.openai_model}")
    typer.echo(
        "research="
        f"provider:{settings.research.provider} geography:{settings.research.geography} "
        f"queries:{settings.research.max_queries} candidates:{settings.research.max_candidates} "
        f"deep:{settings.research.max_deep_research} qualified:{settings.research.max_qualified} "
        f"web_search:{settings.research.max_web_search_calls} analysis:{settings.research.max_analysis_calls}"
    )
    typer.echo(
        "production_research_gate="
        f"{'completed' if settings.live.production_research_completed else 'not completed'}"
    )
    typer.echo(f"mail_password_in_keychain={'yes' if mailbox_present else 'no'}")
    typer.echo(f"openai_key_in_keychain={'yes' if openai_keychain else 'no'}")
    if mailbox_detail.startswith("OS credential store unavailable") or openai_detail.startswith(
        "unavailable"
    ):
        typer.echo("keychain_status=unavailable")
    typer.echo(
        f"openai_effective={'configured' if settings.providers.openai_api_key else 'not configured'}"
    )
    typer.echo(f"live={'enabled' if settings.live.enabled else 'disabled'}")
    typer.echo(f"scheduler={_scheduler_state()}")


@secrets_app.command("set-mail-password")
def secrets_set_mail_password() -> None:
    """Store the mailbox password in the OS credential store without echoing it."""
    settings = load_settings()
    username = _mailbox_username(settings)
    if not username or "@" not in username:
        raise typer.BadParameter("Configure sender.email or mailbox_username with setup first")
    password = typer.prompt(
        "Private Email mailbox password", hide_input=True, confirmation_prompt=True
    )
    if not password:
        raise typer.BadParameter("Mailbox password cannot be blank")
    default_secret_store().set(username, password)
    typer.echo(f"Stored mailbox password in the OS credential store for {mask_email(username)}.")


@secrets_app.command("delete-mail-password")
def secrets_delete_mail_password() -> None:
    """Delete the stored mailbox password from the OS credential store."""
    settings = load_settings()
    username = _mailbox_username(settings)
    if not username:
        raise typer.BadParameter("Mailbox username is not configured")
    default_secret_store().delete(username)
    typer.echo(f"Deleted mailbox password for {mask_email(username)} from the OS credential store.")


@secrets_app.command("set-openai-key")
def secrets_set_openai_key() -> None:
    """Store the OpenAI API key in the OS credential store without echoing it."""
    api_key = typer.prompt("OpenAI API key", hide_input=True, confirmation_prompt=True)
    if not api_key.strip():
        raise typer.BadParameter("OpenAI API key cannot be blank")
    default_secret_store().set(OPENAI_ACCOUNT, api_key.strip(), OPENAI_API_KEY)
    typer.echo("Stored the OpenAI API key in the OS credential store.")


@secrets_app.command("delete-openai-key")
def secrets_delete_openai_key() -> None:
    """Delete the OpenAI API key from the OS credential store."""
    default_secret_store().delete(OPENAI_ACCOUNT, OPENAI_API_KEY)
    typer.echo("Deleted the OpenAI API key from the OS credential store.")


@secrets_app.command("status")
def secrets_status() -> None:
    """Show only whether configured secrets exist; never show their values."""
    settings = load_settings()
    present, detail = _mail_password_present(settings)
    openai_present, openai_detail = _keychain_secret_present(OPENAI_ACCOUNT, OPENAI_API_KEY)
    typer.echo(
        f"mailbox={mask_email(_mailbox_username(settings))} "
        f"password={'configured' if present else detail} "
        f"openai_key={'configured' if openai_present else openai_detail}"
    )


@app.command()
def doctor() -> None:
    """Run fail-closed configuration, database, provider, and scheduler checks."""
    paths, database = _paths_db()
    settings = load_settings(paths=paths)
    checks: list[tuple[str, bool, str]] = []
    checks.append(("Python", sys.version_info >= (3, 11), platform.python_version()))
    checks.append(
        ("Private config path", paths.config_file.parent != Path.cwd(), str(paths.config_file))
    )
    checks.append(("Database", database.healthy(), str(paths.db)))
    with database.session() as session:
        schema_ok, schema_detail = _schema_migration_status(session)
        uncertain = session.query(OutboxMessage).filter(OutboxMessage.state == "uncertain").count()
        external_import_complete = (
            session.query(ImportRecord).filter(ImportRecord.status == "success").count() > 0
        )
        production_success = (
            session.query(Run)
            .filter(
                Run.data_origin == "production",
                Run.run_type == "production_dry_run",
                Run.status == "success",
            )
            .count()
            > 0
        )
    checks.append(("Schema migration", schema_ok, schema_detail))
    checks.append(
        (
            "External/manual research import",
            external_import_complete,
            "completed" if external_import_complete else "not completed",
        )
    )
    checks.append(
        (
            "Live mode",
            not settings.live.enabled,
            "disabled" if not settings.live.enabled else "enabled",
        )
    )
    checks.append(
        (
            "Owner-only transport test",
            settings.live.owner_test_sent,
            "passed" if settings.live.owner_test_sent else "not completed",
        )
    )
    checks.append(
        (
            "Offline/legacy dry run",
            settings.live.dry_run_completed,
            "completed" if settings.live.dry_run_completed else "not completed",
        )
    )
    checks.append(
        (
            "Production web research dry run",
            settings.live.production_research_completed and production_success,
            "completed"
            if settings.live.production_research_completed and production_success
            else "not completed",
        )
    )
    checks.append(("Sender", bool(settings.sender.email), mask_email(settings.sender.email)))
    checks.append(
        ("Owner BCC", bool(settings.sender.owner_bcc), mask_email(settings.sender.owner_bcc))
    )
    checks.append(
        (
            "Reply sync",
            settings.providers.mail_reply_sync,
            "enabled" if settings.providers.mail_reply_sync else "disabled",
        )
    )
    openai_configured = bool(
        settings.providers.openai_api_key or os.getenv("ELIORA_OPENAI_API_KEY")
    )
    checks.append(
        (
            "OpenAI",
            True,
            "configured" if openai_configured else "not configured; offline mode available",
        )
    )
    secret_present, secret_detail = _mail_password_present(settings)
    checks.append(("Mailbox OS secret", secret_present, secret_detail))
    checks.append(
        (
            "Mail provider",
            settings.providers.mail_provider == "namecheap_private_email",
            f"{settings.providers.mail_provider} "
            f"SMTP {settings.providers.smtp_host}:{settings.providers.smtp_port} "
            f"IMAP {settings.providers.imap_host}:{settings.providers.imap_port}",
        )
    )
    checks.append(
        (
            "Permission policy acknowledgement",
            not _policy_acknowledgement_needed(settings),
            "acknowledged" if not _policy_acknowledgement_needed(settings) else "required",
        )
    )
    smtp_ok = imap_ok = False
    if secret_present and _mailbox_username(settings).lower() == settings.sender.email.lower():
        try:
            transport = PrivateEmailProvider(
                settings.providers,
                username=_mailbox_username(settings),
                secret_store=default_secret_store(),
            )
            try:
                transport.smtp.authenticate()
                smtp_ok = True
                smtp_detail = "authenticated"
            except Exception as exc:
                smtp_detail = getattr(exc, "category", type(exc).__name__)
            checks.append(("SMTP authentication", smtp_ok, smtp_detail))
            imap_detail = "authenticated"
            try:
                transport.imap.authenticate()
                imap_ok = True
            except Exception as exc:
                imap_detail = getattr(exc, "category", type(exc).__name__)
            checks.append(
                (
                    "IMAP authentication / folders",
                    imap_ok,
                    f"INBOX={transport.imap.folders.inbox} Sent={transport.imap.folders.sent}"
                    if imap_ok
                    else imap_detail,
                )
            )
        except Exception as exc:
            detail = getattr(exc, "category", type(exc).__name__)
            checks.append(("SMTP authentication", False, detail))
            checks.append(("IMAP authentication / folders", False, detail))
    else:
        detail = (
            "run secrets set-mail-password first"
            if not secret_present
            else "username/sender mismatch"
        )
        checks.append(("SMTP authentication", False, detail))
        checks.append(("IMAP authentication / folders", False, detail))
    sender_domain = (
        registrable_domain(settings.sender.email.split("@", 1)[-1])
        if "@" in settings.sender.email
        else ""
    )
    if sender_domain:
        mx_ok, mx_detail = check_mx(sender_domain)
        checks.append(("Sender-domain MX", mx_ok is not False, mx_detail))
        try:
            dns_status = advisory_dns_checks(sender_domain)
            checks.append(
                (
                    "SPF/DMARC advisory",
                    True,
                    f"SPF={dns_status['spf']} DMARC={dns_status['dmarc']}",
                )
            )
        except Exception as exc:
            checks.append(("SPF/DMARC advisory", True, f"unavailable ({type(exc).__name__})"))
    checks.append(("Uncertain sends", uncertain == 0, str(uncertain)))
    checks.append(("Scheduler", True, "inspect with schedule status"))
    for label, passed, detail in checks:
        typer.echo(f"{'PASS' if passed else 'FAIL':4} {label}: {detail}")
    if not all(item[1] for item in checks):
        raise typer.Exit(code=1)


@app.command("send-test")
def send_test(
    to: str | None = typer.Option(None, "--to", help="Optional; must equal configured owner/BCC."),
) -> None:
    """Send an explicit owner-only test; never accepts a prospect recipient by default."""
    settings = load_settings()
    if not settings.sender.owner_bcc:
        raise typer.BadParameter("Configure owner/BCC with setup first")
    to = to or settings.sender.owner_bcc
    if to.strip().lower() != settings.sender.owner_bcc.strip().lower():
        raise typer.BadParameter("send-test is owner-only; --to must equal configured owner/BCC")
    confirmed = typer.confirm(
        f"Send one owner-only test to {mask_email(to)} through Private Email?", default=False
    )
    if not confirmed:
        raise typer.Abort()
    typer.echo("Owner-only test is authorized; no prospect recipient is permitted.")
    from .email.render import build_mime, deterministic_message_id

    provider = PrivateEmailProvider(
        settings.providers,
        username=_mailbox_username(settings),
        secret_store=default_secret_store(),
    )
    from .models import DraftContent

    content = DraftContent(
        subject="EliOra outreach engine mail transport test",
        body=f"This is an owner-only test.\n\n{settings.sender.disclosure}\n{settings.sender.postal_address}\n{settings.sender.opt_out}",
        html_body="<p>This is an owner-only test.</p>",
        source_fact_ids=[],
    )
    raw = build_mime(
        content=content,
        sender=settings.sender,
        recipient=to,
        message_id=deterministic_message_id("owner-test", settings.sender.email),
    ).as_bytes()
    try:
        provider.send(raw, idempotency_key="owner-test", envelope_recipients=[to])
        if (
            provider.find_by_message_id(
                deterministic_message_id("owner-test", settings.sender.email)
            )
            is None
        ):
            raise typer.BadParameter(
                "SMTP acceptance could not be reconciled in the IMAP Sent folder"
            )
    except typer.BadParameter:
        raise
    except Exception as exc:
        category = getattr(exc, "category", type(exc).__name__)
        raise typer.BadParameter(f"Owner-only transport test failed: {category}") from None
    updated = settings.model_copy(
        update={"live": settings.live.model_copy(update={"owner_test_sent": True})}
    )
    write_settings(updated)
    _paths, database = _paths_db()
    from .enums import RunStatus, RunType
    from .pipeline import create_run, finish_run

    owner_run = create_run(
        database,
        f"owner_test:{datetime.now(timezone.utc).isoformat()}",
        RunType.OWNER_TEST,
        run_mode="owner_test",
        data_origin="owner_test",
    )
    if owner_run:
        finish_run(database, owner_run.id, RunStatus.SUCCESS, {"prospect_messages_sent": 0})
    with database.session() as session:
        session.add(
            AuditEvent(
                actor="owner",
                action="owner_transport_test_sent",
                entity_type="transport",
                metadata_json={"origin": "owner_test", "prospect": False},
            )
        )
    typer.echo("Owner-only test sent and recorded.")


@app.command("send-now")
def send_now_command(
    draft_id: str,
    recipient: str | None = typer.Option(
        None,
        "--recipient",
        help="Optional override; must exactly match the persisted contact.",
    ),
    yes: bool = typer.Option(False, "--yes", help="Skip the one-draft confirmation."),
) -> None:
    """Send exactly one approved contact-backed draft by explicit owner command."""
    paths, database = _paths_db()
    settings = load_settings(paths=paths)
    try:
        preview = preview_explicit_send(
            database,
            settings,
            draft_id=draft_id,
            recipient=recipient,
        )
    except ExplicitSendError as exc:
        typer.echo(f"BLOCKED: {exc}")
        raise typer.Exit(code=1) from None

    typer.echo("Preview — exactly one email; nothing has been sent yet")
    typer.echo(f"company:   {preview.company}")
    typer.echo(f"recipient: {preview.recipient}")
    typer.echo(f"subject:   {preview.subject}")
    typer.echo(f"sender:    {preview.sender}")
    typer.echo("body:")
    typer.echo(preview.body)
    if not yes and not typer.confirm(
        f"Send this one email to {preview.recipient} through Namecheap Private Email?",
        default=False,
    ):
        typer.echo("Cancelled; no email sent.")
        return

    with application_lock(paths.lock_file) as acquired:
        if not acquired:
            typer.echo("BLOCKED: another outreach operation holds the application lock")
            raise typer.Exit(code=1)
        provider = PrivateEmailProvider(
            settings.providers,
            username=_mailbox_username(settings),
            secret_store=default_secret_store(),
        )
        try:
            result = send_explicit(
                database,
                settings,
                draft_id=draft_id,
                recipient=recipient,
                provider=provider,
            )
        except ExplicitSendError as exc:
            typer.echo(f"BLOCKED: {exc}")
            raise typer.Exit(code=1) from None
        except MailTransportError as exc:
            with database.session() as session:
                row = session.scalar(
                    select(OutboxMessage).where(OutboxMessage.draft_id == draft_id)
                )
                state = row.state if row else "not_created"
            if exc.uncertain:
                typer.echo(
                    f"BLOCKED: uncertain delivery ({exc.category}); outbox_state={state}. "
                    "Do not retry until reconciliation."
                )
            else:
                typer.echo(f"BLOCKED: transport failed ({exc.category}); outbox_state={state}")
            raise typer.Exit(code=1) from None
        except Exception as exc:
            typer.echo(f"BLOCKED: explicit send failed ({type(exc).__name__})")
            raise typer.Exit(code=1) from None
    typer.echo(f"sent: {result.company} / {result.subject}")
    typer.echo(
        f"outbox_id={result.outbox_id} recipient={result.recipient} "
        f"sent_at={result.sent_at.isoformat()}"
    )
    typer.echo(
        f"source={result.data_origin} provider=namecheap_private_email "
        f"message_id={result.message_id or 'pending'}"
    )
    typer.echo("prospect_messages_sent: 1")


@app.command()
def demo() -> None:
    """Run the complete synthetic pipeline offline through a fake mail provider."""
    _paths, database = _paths_db()
    result = run_synthetic_demo(database)
    typer.echo("DEMO / SYNTHETIC — offline only; never production data")
    for key, value in result.items():
        typer.echo(f"{key}: {value}")


def _record_dry_run(settings: Settings, database: Database) -> None:
    day = datetime.now(timezone.utc).date().isoformat()
    from .enums import RunStatus, RunType
    from .pipeline import create_run, finish_run

    run = create_run(database, f"{day}:dry_run", RunType.DRY_RUN)
    if run:
        finish_run(database, run.id, RunStatus.SUCCESS, {"researched": 0, "drafts": 0, "sent": 0})
        write_settings(
            settings.model_copy(
                update={"live": settings.live.model_copy(update={"dry_run_completed": True})}
            )
        )


@app.command()
def run(
    dry_run: bool = typer.Option(False, "--dry-run"),
    live: bool = typer.Option(False, "--live"),
    max_qualified: int | None = typer.Option(None, "--max-qualified", min=1),
    max_candidates: int | None = typer.Option(None, "--max-candidates", min=1),
    max_deep_research: int | None = typer.Option(None, "--max-deep-research", min=1),
) -> None:
    """Run real bounded production research; --dry-run never dispatches prospects."""
    paths, database = _paths_db()
    settings = load_settings(paths=paths)
    with application_lock(paths.lock_file) as acquired:
        if not acquired:
            typer.echo("Another outreach run holds the application lock; exiting cleanly.")
            return
        if not dry_run and not live:
            typer.echo(
                "Choose --dry-run for production research or --live for research plus dispatch."
            )
            raise typer.Exit(code=2)
        if dry_run and live:
            typer.echo("Choose one mode: --dry-run or --live, not both.")
            raise typer.Exit(code=2)
        if live:
            allowed, failures = can_send(settings)
            if not allowed:
                for failure in failures:
                    typer.echo(f"BLOCKED: {failure}")
                raise typer.Exit(code=1)
            from .email.sync import sync_tracked_replies

            provider = PrivateEmailProvider(
                settings.providers,
                username=_mailbox_username(settings),
                secret_store=default_secret_store(),
            )
            sync_result = sync_tracked_replies(
                database, provider, owner_email=settings.sender.email
            )
            typer.echo(
                f"Reply sync: fetched={sync_result['fetched']} recorded={sync_result['recorded']}"
            )
            result = dispatch_pending(database, settings, provider=provider, paths=paths)
            for key, value in result.items():
                typer.echo(f"{key}: {value}")
        typer.echo(
            "PRODUCTION WEB RESEARCH — PROSPECT SENDING DISABLED"
            if dry_run
            else "PRODUCTION WEB RESEARCH — DISPATCH REMAINS GATED"
        )
        try:
            result = run_production_research(
                database,
                settings,
                max_qualified=max_qualified,
                max_candidates=max_candidates,
                max_deep_research=max_deep_research,
                live_mode=live,
                check_mx_records=True,
            )
        except ProductionResearchError as exc:
            _echo_production_failure(exc)
            raise typer.Exit(code=1) from None
        if result.get("status") == "success":
            updated = settings.model_copy(
                update={
                    "live": settings.live.model_copy(
                        update={"production_research_completed": True, "dry_run_completed": True}
                    )
                }
            )
            write_settings(updated, paths=paths)
            settings = updated
        for key, value in result.items():
            typer.echo(f"{key}: {value}")
        if live:
            from .email.sync import sync_tracked_replies

            provider = PrivateEmailProvider(
                settings.providers,
                username=_mailbox_username(settings),
                secret_store=default_secret_store(),
            )
            sync_result = sync_tracked_replies(
                database, provider, owner_email=settings.sender.email
            )
            typer.echo(
                f"Reply sync: fetched={sync_result['fetched']} recorded={sync_result['recorded']}"
            )
            dispatch_result = dispatch_pending(database, settings, provider=provider, paths=paths)
            for key, value in dispatch_result.items():
                typer.echo(f"{key}: {value}")
        else:
            typer.echo("prospect messages sent: 0")


@app.command("run-if-due")
def run_if_due() -> None:
    """Catch up one current business-day cycle after login/hourly wake without backlog bursts."""
    paths, database = _paths_db()
    settings = load_settings(paths=paths)
    now = datetime.now(timezone.utc)
    decision = decide_due(
        now,
        timezone=settings.schedule.timezone,
        research_time=settings.schedule.research_time,
        send_start=settings.schedule.send_start,
        send_end=settings.schedule.send_end,
        paused=paths.pause_file.exists(),
    )
    typer.echo(
        f"due={decision.research_due} dispatch_window={decision.dispatch_allowed} reason={decision.reason}"
    )
    if decision.research_due:
        try:
            result = run_production_research(
                database, settings, live_mode=settings.live.enabled, check_mx_records=True
            )
            if result.get("status") == "success":
                settings = settings.model_copy(
                    update={
                        "live": settings.live.model_copy(
                            update={
                                "production_research_completed": True,
                                "dry_run_completed": True,
                            }
                        )
                    }
                )
                write_settings(settings, paths=paths)
            typer.echo(f"production research: {result.get('status')}")
        except ProductionResearchError as exc:
            typer.echo(f"BLOCKED: production research unavailable [{exc.category}]")
            if exc.action:
                typer.echo(f"action: {exc.action}")
            typer.echo(f"request_id: {exc.request_id or 'none'}")
            typer.echo(
                f"retryable: {'yes' if exc.retryable else 'no'}; "
                f"retry_not_before: {exc.retry_not_before.isoformat() if exc.retry_not_before else 'none'}; "
                "prospect_messages_sent: 0"
            )
    if settings.live.enabled:
        allowed, failures = can_send(settings)
        if not allowed:
            for failure in failures:
                typer.echo(f"BLOCKED: {failure}")
            return
        from .email.sync import sync_tracked_replies

        provider = PrivateEmailProvider(
            settings.providers,
            username=_mailbox_username(settings),
            secret_store=default_secret_store(),
        )
        try:
            sync_result = sync_tracked_replies(
                database, provider, owner_email=settings.sender.email
            )
            typer.echo(
                f"Reply sync: fetched={sync_result['fetched']} recorded={sync_result['recorded']}"
            )
            if decision.dispatch_allowed:
                result = dispatch_pending(database, settings, provider=provider, paths=paths)
                for key, value in result.items():
                    typer.echo(f"{key}: {value}")
            else:
                typer.echo("Messages remain queued until the next valid send window.")
        except Exception as exc:
            typer.echo(f"BLOCKED: Private Email sync/dispatch unavailable ({type(exc).__name__})")
    elif not decision.dispatch_allowed:
        typer.echo("Messages remain queued until the next valid send window.")


@app.command()
def dispatch() -> None:
    """Dispatch only due, leased, fully validated outbox messages in live mode."""
    paths, database = _paths_db()
    settings = load_settings(paths=paths)
    allowed, failures = can_send(settings)
    if not allowed:
        for failure in failures:
            typer.echo(f"BLOCKED: {failure}")
        raise typer.Exit(code=1)
    from .email.sync import sync_tracked_replies

    provider = PrivateEmailProvider(
        settings.providers,
        username=_mailbox_username(settings),
        secret_store=default_secret_store(),
    )
    sync_result = sync_tracked_replies(database, provider, owner_email=settings.sender.email)
    typer.echo(f"Reply sync: fetched={sync_result['fetched']} recorded={sync_result['recorded']}")
    result = dispatch_pending(database, settings, provider=provider, paths=paths)
    for key, value in result.items():
        typer.echo(f"{key}: {value}")


@app.command("reply-sync")
def reply_sync() -> None:
    """Synchronize only tracked threads; any human reply stops automation."""
    paths, database = _paths_db()
    settings = load_settings(paths=paths)
    if not settings.providers.mail_reply_sync:
        raise typer.BadParameter(
            "Reply synchronization is disabled; live mode cannot use this setting"
        )
    provider = PrivateEmailProvider(
        settings.providers,
        username=_mailbox_username(settings),
        secret_store=default_secret_store(),
    )
    from .email.sync import sync_tracked_replies

    result = sync_tracked_replies(
        database,
        provider,
        owner_email=settings.sender.email,
    )
    typer.echo(
        f"Reply sync complete: fetched={result['fetched']} recorded={result['recorded']} "
        f"suppressed={result['suppressed']} cancelled={result['cancelled']}."
    )


@app.command()
def dashboard() -> None:
    """Start the localhost-only dashboard."""
    settings = load_settings()
    typer.echo(f"Dashboard: http://127.0.0.1:{settings.dashboard_port}")
    run_dashboard(port=settings.dashboard_port)


@app.command()
def pause() -> None:
    paths = default_paths()
    paths.pause_file.write_text("paused by owner\n", encoding="utf-8")
    typer.echo("Outreach paused. Research and dispatch will not run until resume.")


@app.command()
def resume() -> None:
    paths = default_paths()
    if paths.pause_file.exists():
        paths.pause_file.unlink()
    typer.echo("Outreach resumed; normal due and send-window gates still apply.")


@live_app.command("enable")
def live_enable() -> None:
    """Activate live mode only after the owner types the exact confirmation phrase."""
    paths, database = _paths_db()
    settings = load_settings(paths=paths)
    pending_uncertain = 0
    with database.session() as session:
        pending_uncertain = (
            session.query(OutboxMessage).filter(OutboxMessage.state == "uncertain").count()
        )
    mail_transport_ok = smtp_authenticated = imap_authenticated = False
    sender_identity_verified = False
    username = _mailbox_username(settings)
    try:
        if username and username.lower() == settings.sender.email.lower():
            sender_identity_verified = True
            provider = PrivateEmailProvider(
                settings.providers,
                username=username,
                secret_store=default_secret_store(),
            )
            provider.connectivity_check()
            mail_transport_ok = smtp_authenticated = imap_authenticated = True
    except Exception as exc:
        typer.echo(
            "Private Email verification unavailable: "
            f"{getattr(exc, 'category', type(exc).__name__)}"
        )
    failures = validate_live_preconditions(
        settings,
        mail_transport_ok=mail_transport_ok,
        smtp_authenticated=smtp_authenticated,
        imap_authenticated=imap_authenticated,
        sender_identity_verified=sender_identity_verified,
        owner_test_sent=settings.live.owner_test_sent,
        dry_run_completed=settings.live.dry_run_completed,
        production_research_completed=settings.live.production_research_completed,
        database_ok=database.healthy(),
        pending_uncertain=pending_uncertain,
    )
    if failures:
        for failure in failures:
            typer.echo(f"BLOCKED: {failure}")
        raise typer.Exit(code=1)
    if settings.targeting.min_score_auto_send < 75:
        warning = typer.prompt(
            "Auto-send threshold is below 75. Type ACKNOWLEDGE LOW AUTO-SEND THRESHOLD to continue"
        )
        if warning != "ACKNOWLEDGE LOW AUTO-SEND THRESHOLD":
            raise typer.BadParameter("Lower-threshold acknowledgement did not match")
    phrase = typer.prompt("Type ENABLE ELIORA OUTREACH to activate live mode")
    if phrase != "ENABLE ELIORA OUTREACH":
        raise typer.BadParameter("Activation phrase did not match")
    updated = settings.model_copy(
        update={
            "live": settings.live.model_copy(
                update={
                    "enabled": True,
                    "policy_acknowledged": True,
                    "activated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        }
    )
    write_settings(updated, paths=paths)
    typer.echo(
        "Live mode enabled. Every message remains subject to per-message gates, window, quota, suppression, and reconciliation."
    )


@live_app.command("disable")
def live_disable() -> None:
    settings = load_settings()
    write_settings(
        settings.model_copy(update={"live": settings.live.model_copy(update={"enabled": False})})
    )
    typer.echo("Live mode disabled.")


@schedule_app.command("install")
def schedule_install() -> None:
    script = _scheduler_script("install")
    subprocess.run(
        ["bash", str(script)]
        if platform.system() != "Windows"
        else ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        check=True,
    )


@schedule_app.command("uninstall")
def schedule_uninstall() -> None:
    script = _scheduler_script("uninstall")
    subprocess.run(
        ["bash", str(script)]
        if platform.system() != "Windows"
        else ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        check=True,
    )


@schedule_app.command("status")
def schedule_status() -> None:
    system = platform.system()
    paths = default_paths()
    if system == "Darwin":
        label = "com.eliora.outreach"
        result = subprocess.run(
            ["launchctl", "print", f"gui/{os.getuid()}/{label}"], capture_output=True, text=True
        )
        typer.echo("installed" if result.returncode == 0 else "not installed")
    elif system == "Linux":
        result = subprocess.run(
            ["systemctl", "--user", "is-enabled", "eliora-outreach.timer"],
            capture_output=True,
            text=True,
        )
        typer.echo(result.stdout.strip() or "not installed")
    else:
        typer.echo("Use Get-ScheduledTask -TaskName EliOra-Outreach in PowerShell")
    typer.echo(f"pause_file={paths.pause_file}")


def _scheduler_script(action: str) -> Path:
    directory = Path(__file__).resolve().parents[2] / "scripts"
    system = platform.system()
    if system == "Darwin":
        return (
            directory / f"{'install' if action == 'install' else 'uninstall'}_macos_launchagent.sh"
        )
    if system == "Linux":
        return directory / f"{'install' if action == 'install' else 'uninstall'}_linux_systemd.sh"
    return directory / f"{'install' if action == 'install' else 'uninstall'}_windows_task.ps1"


@lead_app.command("list")
def lead_list() -> None:
    _paths, database = _paths_db()
    rows = score_rows(database, origin="production")
    for _company, row in rows:
        typer.echo(
            f"{row.company_id}\tFit {row.opportunity_fit_grade or '-'} "
            f"{row.opportunity_fit_score if row.opportunity_fit_score is not None else '-'}\t"
            f"Reach {row.reachability_grade or '-'} "
            f"{row.reachability_score if row.reachability_score is not None else '-'}\t"
            f"{row.priority or '-'}\tlegacy {row.total_score}\t{row.disposition}"
        )


@lead_app.command("show")
def lead_show(lead_id: str) -> None:
    _paths, database = _paths_db()
    with database.session() as session:
        from sqlalchemy import select

        row = session.get(LeadScore, lead_id) or session.scalar(
            select(LeadScore)
            .where(LeadScore.company_id == lead_id)
            .order_by(LeadScore.scored_at.desc())
        )
    if not row:
        raise typer.BadParameter("Lead not found")
    typer.echo(
        f"company={row.company_id}\n"
        f"opportunity_fit={row.opportunity_fit_score} ({row.opportunity_fit_grade})\n"
        f"reachability={row.reachability_score} ({row.reachability_grade})\n"
        f"priority={row.priority}\n"
        f"project={row.primary_project_type}\n"
        f"buyer={row.primary_buyer_persona}\n"
        f"scope={row.project_scope_band}\n"
        f"procurement_friction={row.procurement_friction_band}\n"
        f"legacy_score={row.total_score}\n"
        f"legacy_disposition={row.disposition}\n"
        f"opportunity_fit_breakdown={row.opportunity_fit_breakdown_json}\n"
        f"reachability_breakdown={row.reachability_breakdown_json}\n"
        f"legacy_explanation={row.explanation}"
    )


@lead_app.command("set-permission")
def lead_set_permission(
    lead_id: str,
    basis: str = typer.Option(
        ..., "--basis", help="Eligible permission basis for Namecheap auto-dispatch."
    ),
    source: str = typer.Option(..., "--source", help="Short owner-auditable source or note."),
) -> None:
    """Record an explicit per-company basis required for production auto-dispatch."""
    if basis not in NAMECHEAP_AUTO_SEND_BASES - {"synthetic_test"}:
        allowed = ", ".join(sorted(NAMECHEAP_AUTO_SEND_BASES - {"synthetic_test"}))
        raise typer.BadParameter(f"basis must be one of: {allowed}")
    if not source.strip():
        raise typer.BadParameter("source cannot be blank")
    _paths, database = _paths_db()
    with database.session() as session:
        company = session.get(Company, lead_id)
        if company is None:
            score = session.get(LeadScore, lead_id)
            company = session.get(Company, score.company_id) if score else None
        if company is None:
            raise typer.BadParameter("Company/lead not found")
        company.permission_basis = basis
        company.permission_basis_source = source.strip()[:1000]
        session.add(
            AuditEvent(
                actor="owner",
                action="permission_basis_recorded",
                entity_type="company",
                entity_id=company.id,
                metadata_json={"basis": basis, "source": source.strip()[:1000]},
            )
        )
        company_id = company.id
    typer.echo(f"Recorded {basis} for {company_id}; Namecheap auto-dispatch remains policy-gated.")


@lead_app.command("add-contact")
def lead_add_contact(
    lead_id: str,
    email: str = typer.Option(..., "--email", help="Publicly sourced business email."),
    name: str | None = typer.Option(None, "--name", help="Published contact name, if known."),
    title: str | None = typer.Option(None, "--title", help="Published contact title, if known."),
    source_url: str = typer.Option(..., "--source-url", help="Real public source URL."),
    source_type: str = typer.Option(..., "--source-type", help="Existing evidence source type."),
    extraction_method: str = typer.Option(
        "visible_text",
        "--extraction-method",
        help="How the address was observed: visible_text, mailto, or jsonld.",
    ),
    draft_id: str | None = typer.Option(
        None,
        "--draft-id",
        help="Existing draft to attach; required only when several drafts lack contacts.",
    ),
) -> None:
    """Attach one provenance-backed business contact without creating send work."""
    _paths, database = _paths_db()
    try:
        result = attach_contact(
            database,
            company_id=lead_id,
            email=email,
            display_name=name,
            title=title,
            source_url=source_url,
            source_type=source_type,
            extraction_method=extraction_method,
            draft_id=draft_id,
        )
    except ContactAttachError as exc:
        typer.echo(f"BLOCKED: {exc}")
        raise typer.Exit(code=1) from None
    typer.echo(f"{result.status}: {result.company} / {result.email}")
    typer.echo(f"contact_id={result.contact_id} draft_id={result.draft_id or 'none'}")
    typer.echo(
        f"name={result.display_name or 'unknown'} title={result.title or 'unknown'} "
        f"source={result.source_url} verification={result.source_verification_status}"
    )
    typer.echo(
        f"reachability={result.reachability_after} ({result.reachability_grade or '-'}) "
        f"previous={result.reachability_before} permission_basis={result.permission_basis}"
    )
    typer.echo("outbox_rows_created: 0; prospect_messages_sent: 0")


@scores_app.command("recompute")
def scores_recompute(
    origin: str = typer.Option("all", "--origin", help="all, production, or external"),
) -> None:
    """Recompute commercial scores without changing legacy scores or dispatch state."""
    if origin not in {"all", "production", "external"}:
        raise typer.BadParameter("origin must be all, production, or external")
    _paths, database = _paths_db()
    result = recompute_scores(database, origin=origin)
    typer.echo(f"Recomputed {result['recomputed']} leads")
    typer.echo(f"Opportunity Fit grades: {result['opportunity_fit_grades']}")
    typer.echo(f"Reachability grades: {result['reachability_grades']}")
    typer.echo("outbox rows created: 0")
    typer.echo("prospect messages sent: 0")
    for row in result["before_after"]:
        typer.echo(
            f"{row['company']}\tFit {row['opportunity_fit_after']}\t"
            f"Reach {row['reachability_after']}\tlegacy {row['legacy_score']}"
        )


@scores_app.command("show")
def scores_show(
    origin: str = typer.Option("all", "--origin", help="all, production, or external"),
) -> None:
    """Show commercial ordering and the separate legacy score."""
    if origin not in {"all", "production", "external"}:
        raise typer.BadParameter("origin must be all, production, or external")
    _paths, database = _paths_db()
    rows = score_rows(database, origin=origin)
    typer.echo("Company\tOpportunity Fit\tReachability\tPriority\tProject\tBuyer\tLegacy")
    for company, row in rows:
        typer.echo(
            f"{company.name}\t{row.opportunity_fit_grade or '-'} "
            f"{row.opportunity_fit_score if row.opportunity_fit_score is not None else '-'}\t"
            f"{row.reachability_grade or '-'} "
            f"{row.reachability_score if row.reachability_score is not None else '-'}\t"
            f"{row.priority or '-'}\t{row.primary_project_type or '-'}\t"
            f"{row.primary_buyer_persona or '-'}\t{row.total_score}"
        )


@draft_app.command("list")
def draft_list() -> None:
    _paths, database = _paths_db()
    with database.session() as session:
        rows = session.query(Draft).order_by(Draft.created_at.desc()).all()
    for row in rows:
        typer.echo(f"{row.id}\t{row.status}\t{row.subject}")


@draft_app.command("show")
def draft_show(draft_id: str) -> None:
    _paths, database = _paths_db()
    with database.session() as session:
        row = session.get(Draft, draft_id)
    if not row:
        raise typer.BadParameter("Draft not found")
    typer.echo(f"{row.subject}\n\n{row.plain_text_body}\n\nquality={row.quality_findings}")


@draft_app.command("approve")
def draft_approve(draft_id: str) -> None:
    _set_draft_status(draft_id, "approved")


@draft_app.command("reject")
def draft_reject(draft_id: str) -> None:
    _set_draft_status(draft_id, "rejected")


def _parse_manual_sent_at(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise typer.BadParameter(
            "sent_at must be ISO-8601, for example 2026-08-10T14:30:00-04:00"
        ) from exc
    if parsed.tzinfo is None:
        raise typer.BadParameter("sent_at must include a timezone offset")
    return parsed.astimezone(timezone.utc)


@manual_send_app.command("candidates")
def manual_send_candidate_list() -> None:
    """List real persisted drafts that can be recorded after a manual send."""
    _paths, database = _paths_db()
    rows = manual_send_candidates(database)
    typer.echo("Company\tDraft ID\tRecipient\tSubject\tStatus")
    for row in rows:
        typer.echo(
            f"{row['company']}\t{row['draft_id']}\t{row['recipient']}\t"
            f"{row['subject']}\t{row['status']}"
        )
    if not rows:
        typer.echo("No unsent contact-backed drafts found.")


@manual_send_app.command("record")
def manual_send_record(
    draft_id: str = typer.Argument(..., help="Persisted draft ID for the manual send."),
    recipient: str = typer.Option(..., "--recipient", help="Recipient actually sent to."),
    subject: str = typer.Option(..., "--subject", help="Subject actually sent."),
    sent_at: str | None = typer.Option(
        None,
        "--sent-at",
        help="ISO-8601 send time with timezone; defaults to now if omitted.",
    ),
    rfc_message_id: str | None = typer.Option(
        None, "--rfc-message-id", help="Real RFC Message-ID, if the owner can retrieve it."
    ),
    provider_message_id: str | None = typer.Option(None, "--provider-message-id"),
    provider_thread_id: str | None = typer.Option(None, "--provider-thread-id"),
    mailbox_uid: str | None = typer.Option(
        None, "--mailbox-uid", help="Sent-folder UID, if known."
    ),
    note: str | None = typer.Option(
        None, "--note", help="Short operator note retained in the audit."
    ),
    yes: bool = typer.Option(False, "--yes", help="Skip the safety confirmation."),
) -> None:
    """Record a manual send; this command never sends email."""
    parsed_sent_at = _parse_manual_sent_at(sent_at)
    if not yes:
        typer.confirm(
            f"Record manual send for draft {draft_id} to {recipient}? "
            "This only updates the local database and will not send email",
            abort=True,
        )
    _paths, database = _paths_db()
    try:
        result = record_manual_send(
            database,
            draft_id=draft_id,
            recipient=recipient,
            subject=subject,
            sent_at=parsed_sent_at,
            rfc_message_id=rfc_message_id,
            provider_message_id=provider_message_id,
            provider_thread_id=provider_thread_id,
            mailbox_uid=mailbox_uid,
            note=note,
        )
    except ManualSendError as exc:
        typer.echo(f"BLOCKED: {exc}")
        raise typer.Exit(code=1) from None
    typer.echo(f"{result.status}: {result.company} / {result.subject}")
    typer.echo(f"draft_id={result.draft_id} outbox_id={result.outbox_id}")
    typer.echo(f"recipient={result.recipient} sent_at={result.sent_at.isoformat()}")
    typer.echo(f"source=Manual message_id={'known' if result.message_id_known else 'pending'}")
    typer.echo("prospect_messages_sent: 0 (record-only; no email sent)")


@manual_send_app.command("reconcile")
def manual_send_reconcile(
    draft_id: str | None = typer.Option(
        None, "--draft-id", help="Reconcile one manual-send draft."
    ),
    window_minutes: int = typer.Option(180, "--window-minutes", min=1, max=1440),
) -> None:
    """Use a narrow IMAP Sent lookup to attach real message/thread metadata."""
    paths, database = _paths_db()
    settings = load_settings(paths=paths)
    provider = PrivateEmailProvider(
        settings.providers,
        username=_mailbox_username(settings),
        secret_store=default_secret_store(),
    )
    try:
        result = reconcile_manual_sends(
            database,
            provider,
            draft_id=draft_id,
            window_minutes=window_minutes,
        )
    except ManualSendError as exc:
        typer.echo(f"BLOCKED: {exc}")
        raise typer.Exit(code=1) from None
    except Exception as exc:
        typer.echo(f"RECONCILIATION FAILED: {type(exc).__name__}: {exc}")
        raise typer.Exit(code=1) from None
    for key, value in result.items():
        typer.echo(f"{key}: {value}")
    typer.echo("No email was sent; reconciliation is IMAP read-only plus local metadata update.")


def _set_draft_status(draft_id: str, status: str) -> None:
    _paths, database = _paths_db()
    with database.session() as session:
        row = session.get(Draft, draft_id)
        if not row:
            raise typer.BadParameter("Draft not found")
        row.status = status
    typer.echo(f"{draft_id}: {status}")


@suppress_app.command("add")
def suppress_add(
    value: str,
    scope: str = typer.Option(..., "--scope"),
    reason: str = typer.Option(..., "--reason"),
) -> None:
    if scope not in {"email", "domain", "company"}:
        raise typer.BadParameter("scope must be email, domain, or company")
    _paths, database = _paths_db()
    row = add_suppression(database, value, SuppressionScope(scope), reason)
    typer.echo(f"suppressed {row.scope}:{row.normalized_value}")


@suppress_app.command("list")
def suppress_list() -> None:
    _paths, database = _paths_db()
    for row in active_suppressions(database):
        typer.echo(f"{row.id}\t{row.scope}\t{row.normalized_value}\t{row.reason}")


@suppress_app.command("remove")
def suppress_remove(suppression_id: str, reason: str = typer.Option(..., "--reason")) -> None:
    _paths, database = _paths_db()
    if not remove_suppression(database, suppression_id, reason):
        raise typer.BadParameter("Active suppression not found")
    typer.echo("Suppression removed deliberately and auditably.")


@app.command("export")
def export_data(
    format: str = typer.Option("csv", "--format"),
    output: Path = typer.Option(..., "--output"),
    origin: str = typer.Option("production", "--origin"),
) -> None:
    if format != "csv":
        raise typer.BadParameter("Only csv export is supported")
    if origin not in {"production", "external", "all"}:
        raise typer.BadParameter("origin must be production, external, or all")
    _paths, database = _paths_db()
    settings = load_settings()
    output.parent.mkdir(parents=True, exist_ok=True)
    with database.session() as session, output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "company",
                "domain",
                "score",
                "legacy_score",
                "disposition",
                "opportunity_fit_score",
                "opportunity_fit_grade",
                "opportunity_fit_version",
                "reachability_score",
                "reachability_grade",
                "reachability_version",
                "priority",
                "primary_buyer_persona",
                "primary_project_type",
                "project_scope_band",
                "procurement_friction_band",
                "vertical",
                "signal",
                "signal_date",
                "evidence_urls",
                "pain_hypothesis",
                "contact",
                "contact_source",
                "permission_basis",
                "provider_eligibility",
                "dispatch_allowed",
                "dispatch_blocked_reasons",
                "draft_subject",
                "draft_body",
                "status",
                "origin",
            ]
        )
        lead_query = session.query(LeadScore)
        if origin == "production":
            lead_query = lead_query.filter(LeadScore.data_origin == "production")
        elif origin == "external":
            lead_query = lead_query.filter(LeadScore.data_origin == "external_research")
        lead_pairs: list[tuple[LeadScore, Company]] = []
        for row in lead_query.all():
            company = session.get(Company, row.company_id)
            if company is not None:
                lead_pairs.append((row, company))
        lead_pairs.sort(key=lambda pair: commercial_order_key(pair[1], pair[0]))
        for row, company in lead_pairs:
            signal = (
                session.query(Signal)
                .filter(Signal.company_id == company.id)
                .order_by(Signal.extracted_at.desc())
                .first()
            )
            sources = session.query(Source).filter(Source.company_id == company.id).all()
            pains = (
                session.query(PainHypothesis).filter(PainHypothesis.company_id == company.id).all()
            )
            contact = session.query(Contact).filter(Contact.company_id == company.id).first()
            draft = (
                session.query(Draft)
                .filter(Draft.company_id == company.id)
                .order_by(Draft.created_at.desc())
                .first()
            )
            eligibility = evaluate_dispatch_eligibility(
                settings,
                permission_basis=company.permission_basis,
                contact_valid=bool(
                    contact
                    and contact.syntactic_valid
                    and contact.appropriateness_status == "eligible"
                ),
                official_domain=bool(contact and contact.official_domain),
                no_guessed_address=bool(contact and contact.no_guessed_address),
                draft_status=draft.status if draft else "missing",
                active_suppression=False,
                data_origin=company.data_origin,
            )
            blocked_reasons: list[str] = []
            if not eligibility.allowed:
                blocked_reasons.append(eligibility.reason)
            if company.permission_basis == "unknown":
                blocked_reasons.append("permission_basis=unknown")
            if company.data_origin == "external_research":
                blocked_reasons.append("provider_policy=not_eligible")
            if contact is None:
                blocked_reasons.append("contact_missing")
            writer.writerow(
                [
                    company.name,
                    company.registrable_domain,
                    row.total_score,
                    row.total_score,
                    row.disposition,
                    row.opportunity_fit_score,
                    row.opportunity_fit_grade,
                    row.opportunity_fit_version,
                    row.reachability_score,
                    row.reachability_grade,
                    row.reachability_version,
                    row.priority,
                    row.primary_buyer_persona,
                    row.primary_project_type,
                    row.project_scope_band,
                    row.procurement_friction_band,
                    company.vertical,
                    signal.observed_signal if signal else "",
                    signal.signal_date.date().isoformat() if signal and signal.signal_date else "",
                    " | ".join(source.url for source in sources),
                    " | ".join(pain.hypothesis for pain in pains),
                    contact.email if contact else "",
                    contact.source_url if contact else "",
                    company.permission_basis,
                    eligibility.reason if not eligibility.allowed else "eligible",
                    eligibility.allowed,
                    " | ".join(dict.fromkeys(blocked_reasons)),
                    draft.subject if draft else "",
                    draft.plain_text_body if draft else "",
                    draft.status if draft else "",
                    company.data_origin,
                ]
            )
    typer.echo(f"Exported private lead data to {output}")


@privacy_app.command("purge-cache")
def privacy_purge_cache(older_than: int = typer.Option(90, "--older-than")) -> None:
    paths = default_paths()
    cutoff = datetime.now(timezone.utc).timestamp() - older_than * 86400
    removed = 0
    for path in paths.cache.rglob("*"):
        if path.is_file() and path.stat().st_mtime < cutoff:
            path.unlink()
            removed += 1
    typer.echo(f"Purged {removed} cached research files older than {older_than} days.")
