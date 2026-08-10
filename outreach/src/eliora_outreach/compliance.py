from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import Settings, is_placeholder_email

NAMECHEAP_AUTO_SEND_BASES = {
    "owner_approved",
    "existing_relationship",
    "explicit_inbound_request",
    "contractual_or_transactional",
    "synthetic_test",
}


@dataclass(frozen=True)
class DispatchEligibility:
    allowed: bool
    reason: str
    provider_policy_eligible: bool


def evaluate_dispatch_eligibility(
    settings: Settings,
    *,
    permission_basis: str,
    provider_policy_eligible: bool | None = None,
    contact_valid: bool,
    official_domain: bool,
    no_guessed_address: bool = True,
    draft_status: str,
    active_suppression: bool,
    data_origin: str = "production",
) -> DispatchEligibility:
    """One fail-closed predicate shared by scoring, queueing, dashboard, and dispatch."""
    if data_origin != "production":
        return DispatchEligibility(False, "non_production_origin", False)
    if active_suppression:
        return DispatchEligibility(False, "suppressed", False)
    if draft_status != "approved":
        return DispatchEligibility(False, "draft_not_approved", False)
    if not contact_valid or not no_guessed_address:
        return DispatchEligibility(False, "contact_provenance_required", False)
    if not official_domain:
        return DispatchEligibility(False, "official_domain_required", False)
    if settings.providers.mail_provider == "namecheap_private_email":
        policy_ok = (
            permission_basis in NAMECHEAP_AUTO_SEND_BASES
            if settings.providers.permission_basis_required
            else True
        )
    else:
        policy_ok = bool(provider_policy_eligible)
    if not policy_ok:
        return DispatchEligibility(False, "permission_basis_required", False)
    return DispatchEligibility(True, "eligible", True)


def validate_live_preconditions(
    settings: Settings,
    *,
    mail_transport_ok: bool,
    smtp_authenticated: bool,
    imap_authenticated: bool,
    sender_identity_verified: bool,
    owner_test_sent: bool,
    dry_run_completed: bool,
    production_research_completed: bool = False,
    database_ok: bool,
    pending_uncertain: int = 0,
) -> list[str]:
    failures: list[str] = []
    try:
        settings.validate_live_fields()
    except ValueError as exc:
        failures.append(str(exc))
    if not mail_transport_ok:
        failures.append("Private Email transport connectivity has not passed")
    if not smtp_authenticated:
        failures.append("SMTP authentication has not passed")
    if not imap_authenticated:
        failures.append("IMAP authentication and Sent-folder discovery have not passed")
    if not sender_identity_verified:
        failures.append("Authenticated mailbox identity has not been verified against sender.email")
    if not settings.sender.owner_bcc:
        failures.append("Owner BCC is required")
    if not owner_test_sent:
        failures.append("A successful owner-only test email is required")
    if not dry_run_completed:
        failures.append("At least one successful dry run is required")
    if not production_research_completed:
        failures.append("A successful production web-research dry run is required")
    if not settings.providers.mail_reply_sync:
        failures.append("Reply synchronization is required")
    if not settings.targeting.allowed_countries:
        failures.append("A geography policy is required")
    if settings.limits.hard_daily_prospect_messages > 10:
        failures.append(
            "Hard daily prospect cap must be 10 or lower without advanced acknowledgement"
        )
    if pending_uncertain:
        failures.append("Uncertain outbox sends must be reconciled before activation")
    if not database_ok:
        failures.append("Database health check failed")
    return failures


def can_send(settings: Settings) -> tuple[bool, list[str]]:
    if not settings.live.enabled:
        return False, ["Live mode is disabled"]
    try:
        settings.validate_live_fields()
    except ValueError as exc:
        return False, [str(exc)]
    if not settings.live.production_research_completed:
        return False, ["A successful production web-research dry run is required"]
    if any(
        is_placeholder_email(value)
        for value in (settings.sender.email, settings.sender.reply_to, settings.sender.owner_bcc)
    ):
        return False, ["Configured sender addresses contain placeholders"]
    return True, []


def advisory_dns_checks(domain: str) -> dict[str, Any]:
    """DNS authentication is advisory: presence does not prove deliverability."""
    import dns.resolver

    result: dict[str, Any] = {"domain": domain, "spf": False, "dmarc": False, "advisory": True}
    try:
        result["spf"] = any(
            "v=spf1" in str(record) for record in dns.resolver.resolve(domain, "TXT", lifetime=3)
        )
    except Exception:
        pass
    try:
        result["dmarc"] = bool(dns.resolver.resolve(f"_dmarc.{domain}", "TXT", lifetime=3))
    except Exception:
        pass
    return result
