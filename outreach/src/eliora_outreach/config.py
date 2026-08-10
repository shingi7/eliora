from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from .paths import AppPaths, default_paths

PLACEHOLDER_EMAILS = {
    "your@email.com",
    "owner@example.com",
    "sender@example.com",
    "test@example.com",
}
PLACEHOLDER_DOMAINS = {"example.com", "example.org", "example.net"}
STALE_ADDRESS = "info@elioratech.ai"
PLACEHOLDER_POSTAL = {
    "123 main street",
    "123 main st",
    "your address",
    "123 main street, city, state",
}
PRIVATE_EMAIL_POLICY_VERSION = "2026-08"
_CLOCK_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class CompanySettings(BaseModel):
    legal_name: str = "EliOra Tech Solutions LLC"
    website: str = "https://elioratechsolutions.com"
    relevant_site_urls: list[str] = Field(default_factory=list)

    @field_validator("website")
    @classmethod
    def public_site_must_be_real(cls, value: str) -> str:
        if any(
            value.lower().endswith(f".{domain}") or f"//{domain}" in value.lower()
            for domain in PLACEHOLDER_DOMAINS
        ):
            raise ValueError("Public website cannot use an .example placeholder domain")
        return value

    @field_validator("relevant_site_urls")
    @classmethod
    def relevant_urls_must_be_public(cls, value: list[str]) -> list[str]:
        for item in value:
            parsed = urlparse(item.strip())
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(f"Relevant site URL must be an absolute HTTP(S) URL: {item}")
        return [item.strip() for item in value if item.strip()]


class SenderSettings(BaseModel):
    display_name: str = "EliOra Tech Solutions"
    title: str = "Lead Data Engineer"
    email: str = "shingai@elioratechsolutions.com"
    reply_to: str = "shingai@elioratechsolutions.com"
    owner_bcc: str = "shingai@elioratechsolutions.com"
    postal_address: str = ""
    disclosure: str = "Business outreach from EliOra Tech Solutions."
    opt_out: str = 'Not relevant? Reply "no thanks" and I will not contact you again.'
    meeting_link: str = ""

    @field_validator("disclosure", "opt_out")
    @classmethod
    def required_copy(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Required compliance copy cannot be blank")
        return value.strip()

    @field_validator("postal_address")
    @classmethod
    def reject_placeholder_postal(cls, value: str) -> str:
        if value.strip().lower() in PLACEHOLDER_POSTAL:
            raise ValueError(
                "A real physical postal address is required; placeholder address rejected"
            )
        return value.strip()

    @field_validator("meeting_link")
    @classmethod
    def meeting_link_must_be_https(cls, value: str) -> str:
        value = value.strip()
        if not value:
            return ""
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("meeting_link must be blank or a valid https:// URL")
        return value


class ScheduleSettings(BaseModel):
    timezone: str = "America/New_York"
    research_time: str = "09:00"
    send_start: str = "07:00"
    send_end: str = "19:00"
    fallback_timezone: str = "America/New_York"
    followup_business_days: list[int] = Field(default_factory=lambda: [5, 12])

    @field_validator("timezone", "fallback_timezone")
    @classmethod
    def timezone_must_exist(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except Exception as exc:
            raise ValueError(f"Unknown IANA timezone: {value}") from exc
        return value

    @field_validator("research_time", "send_start", "send_end")
    @classmethod
    def clock_time_must_be_valid(cls, value: str) -> str:
        if not _CLOCK_RE.fullmatch(value):
            raise ValueError("Time must use 24-hour HH:MM format")
        return value

    @model_validator(mode="after")
    def send_window_must_be_ordered(self) -> ScheduleSettings:
        if self.send_end < self.send_start:
            raise ValueError("send_end must be at or after send_start")
        return self


class LimitSettings(BaseModel):
    recommended_daily_initials: int = Field(default=5, ge=1, le=10)
    recommended_daily_followups: int = Field(default=1, ge=0, le=3)
    hard_daily_followups: int = Field(default=3, ge=0, le=10)
    hard_daily_prospect_messages: int = Field(default=10, ge=1, le=10)
    hard_daily_recipients: int = Field(default=20, ge=1, le=20)
    openai_calls: int = Field(default=25, ge=1)
    web_search_calls: int = Field(default=8, ge=1)
    pages_fetched: int = Field(default=100, ge=1)
    companies_researched: int = Field(default=12, ge=1)
    drafts_generated: int = Field(default=12, ge=1)
    random_delay_minutes: tuple[int, int] = (4, 16)

    @model_validator(mode="after")
    def safe_delay(self) -> LimitSettings:
        if (
            self.random_delay_minutes[0] < 0
            or self.random_delay_minutes[1] < self.random_delay_minutes[0]
        ):
            raise ValueError("random_delay_minutes must be an ordered non-negative range")
        return self


class TargetingSettings(BaseModel):
    allowed_countries: list[str] = Field(default_factory=lambda: ["United States", "USA", "US"])
    min_score_auto_send: int = Field(default=82, ge=0, le=100)
    min_pain_confidence: float = Field(default=0.80, ge=0, le=1)
    min_research_confidence: float = Field(default=0.82, ge=0, le=1)
    fresh_signal_days: int = Field(default=120, ge=1)
    cooldown_days: int = Field(default=180, ge=1)
    vertical_weights: dict[str, int] = Field(
        default_factory=lambda: {
            "healthcare": 35,
            "financial_services": 25,
            "operational_business": 30,
            "sports": 10,
        }
    )
    exclusions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def weights_sum_to_100(self) -> TargetingSettings:
        if sum(self.vertical_weights.values()) != 100:
            raise ValueError("Target vertical weights must total 100")
        return self


class ResearchSettings(BaseModel):
    """Bounded production research controls; never contains credentials."""

    mode: Literal["production"] = "production"
    provider: Literal["openai_responses"] = "openai_responses"
    geography: str = "US"
    max_queries: int = Field(default=8, ge=1, le=50)
    max_candidates: int = Field(default=30, ge=1, le=200)
    max_deep_research: int = Field(default=12, ge=1, le=100)
    max_qualified: int = Field(default=5, ge=1, le=50)
    max_web_search_calls: int = Field(default=20, ge=1, le=100)
    max_analysis_calls: int = Field(default=30, ge=1, le=100)
    max_http_requests: int = Field(default=80, ge=1, le=500)
    max_pages_per_domain: int = Field(default=8, ge=1, le=20)
    max_run_seconds: int = Field(default=600, ge=30, le=3600)
    company_cooldown_days: int = Field(default=30, ge=1, le=365)
    page_cache_days: int = Field(default=10, ge=1, le=30)
    signal_strong_days: int = Field(default=90, ge=1, le=365)
    signal_max_days: int = Field(default=180, ge=1, le=730)
    search_context_size: Literal["low", "medium", "high"] = "medium"

    @model_validator(mode="after")
    def freshness_range(self) -> ResearchSettings:
        if self.signal_max_days < self.signal_strong_days:
            raise ValueError("signal_max_days must be at least signal_strong_days")
        return self


class ProviderSettings(BaseModel):
    openai_model: str = "gpt-5.4-mini"
    mail_provider: str = "namecheap_private_email"
    mail_reply_sync: bool = True
    smtp_host: str = "mail.privateemail.com"
    smtp_port: int = Field(default=465, ge=1, le=65535)
    smtp_security: Literal["ssl", "starttls"] = "ssl"
    imap_host: str = "mail.privateemail.com"
    imap_port: int = Field(default=993, ge=1, le=65535)
    imap_security: Literal["ssl", "starttls"] = "ssl"
    mail_timeout_seconds: int = Field(default=30, ge=1, le=120)
    mailbox_username: str | None = None
    permission_basis_required: bool = True
    permission_policy_acknowledged: bool = False
    permission_policy_version: str | None = PRIVATE_EMAIL_POLICY_VERSION
    research_user_agent: str = "EliOra-Outreach-Research/1.0 (+https://elioratechsolutions.com)"
    openai_api_key: SecretStr | None = None
    # Legacy-only fields. They are migrated/ignored for the default provider.
    gmail_reply_sync: bool | None = None
    gmail_credentials_path: str | None = None

    @model_validator(mode="after")
    def validate_mail_transport(self) -> ProviderSettings:
        if self.mail_provider != "namecheap_private_email":
            raise ValueError(
                "Only namecheap_private_email is supported by the default production path"
            )
        if self.smtp_security == "ssl" and self.smtp_port != 465:
            raise ValueError("SMTP SSL/TLS must use port 465")
        if self.smtp_security == "starttls" and self.smtp_port != 587:
            raise ValueError("SMTP STARTTLS must use port 587")
        if self.imap_security == "ssl" and self.imap_port != 993:
            raise ValueError("IMAP SSL/TLS must use port 993")
        if self.imap_security == "starttls" and self.imap_port != 143:
            raise ValueError("IMAP STARTTLS must use port 143")
        return self


class LiveSettings(BaseModel):
    enabled: bool = False
    policy_acknowledged: bool = False
    owner_test_sent: bool = False
    dry_run_completed: bool = False
    production_research_completed: bool = False
    activated_at: str | None = None


class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    company: CompanySettings = Field(default_factory=CompanySettings)
    sender: SenderSettings = Field(default_factory=SenderSettings)
    schedule: ScheduleSettings = Field(default_factory=ScheduleSettings)
    limits: LimitSettings = Field(default_factory=LimitSettings)
    targeting: TargetingSettings = Field(default_factory=TargetingSettings)
    research: ResearchSettings = Field(default_factory=ResearchSettings)
    providers: ProviderSettings = Field(default_factory=ProviderSettings)
    live: LiveSettings = Field(default_factory=LiveSettings)
    dashboard_port: int = 8765
    config_version: int = 4
    config_migration_notice: str | None = None

    @model_validator(mode="after")
    def validate_placeholders(self) -> Settings:
        for label in ("sender.email", "sender.reply_to", "sender.owner_bcc"):
            value: Any = self
            for part in label.split("."):
                value = getattr(value, part)
            if value and is_placeholder_email(value):
                raise ValueError(f"{label} contains a placeholder address")
        if self.live.enabled:
            self.validate_live_fields()
        return self

    def validate_live_fields(self) -> None:
        for label in ("email", "reply_to", "owner_bcc"):
            value = getattr(self.sender, label)
            if not value or not looks_like_email(value):
                raise ValueError(f"sender.{label} must be a valid configured address for live mode")
        if not self.sender.postal_address.strip():
            raise ValueError("sender.postal_address is required for live mode")
        if not self.sender.disclosure.strip() or not self.sender.opt_out.strip():
            raise ValueError("disclosure and opt_out are required for live mode")
        if not self.providers.mail_reply_sync:
            raise ValueError("reply synchronization must be enabled for live mode")
        mailbox_username = self.providers.mailbox_username or self.sender.email
        if mailbox_username.lower() != self.sender.email.lower():
            raise ValueError("mailbox_username must match sender.email for authenticated identity")
        if self.providers.permission_basis_required and (
            not self.providers.permission_policy_acknowledged
            or self.providers.permission_policy_version != PRIVATE_EMAIL_POLICY_VERSION
        ):
            raise ValueError(
                "Namecheap provider policy and permission-basis acknowledgement are required"
            )


def looks_like_email(value: str) -> bool:
    return bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]{2,}", value.strip()))


def is_placeholder_email(value: str) -> bool:
    lowered = value.strip().lower()
    domain = lowered.rsplit("@", 1)[-1] if "@" in lowered else ""
    return (
        lowered in PLACEHOLDER_EMAILS or domain in PLACEHOLDER_DOMAINS or lowered == STALE_ADDRESS
    )


def mask_email(value: str | None) -> str:
    if not value or "@" not in value:
        return "(not configured)" if not value else "***"
    local, domain = value.split("@", 1)
    return f"{local[:1]}***@{domain}"


def _env_overrides(data: dict[str, Any]) -> dict[str, Any]:
    providers = dict(data.get("providers", {}))
    if os.getenv("ELIORA_OPENAI_API_KEY"):
        providers["openai_api_key"] = os.environ["ELIORA_OPENAI_API_KEY"]
    elif "openai_api_key" not in providers:
        try:
            from .secrets import OPENAI_ACCOUNT, OPENAI_API_KEY, default_secret_store

            stored = default_secret_store().get(OPENAI_ACCOUNT, OPENAI_API_KEY)
            if stored:
                providers["openai_api_key"] = stored
        except Exception:
            # A missing/unavailable keyring must not prevent offline configuration use.
            pass
    if os.getenv("ELIORA_OPENAI_MODEL"):
        providers["openai_model"] = os.environ["ELIORA_OPENAI_MODEL"]
    data["providers"] = providers
    return data


def migrate_config_data(data: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    """Migrate the old Gmail-shaped config without treating OAuth paths as passwords."""
    data = dict(data)
    providers = dict(data.get("providers", {}))
    migrated = False
    notices: list[str] = []
    if "mail_reply_sync" not in providers and "gmail_reply_sync" in providers:
        providers["mail_reply_sync"] = providers["gmail_reply_sync"]
        migrated = True
    if "gmail_reply_sync" in providers:
        providers.pop("gmail_reply_sync", None)
        migrated = True
        notices.append("Gmail reply-sync setting migrated to provider-neutral mail_reply_sync.")
    if "gmail_credentials_path" in providers:
        providers.pop("gmail_credentials_path", None)
        migrated = True
        notices.append(
            "Legacy Gmail OAuth path was removed; no credential was converted to a mailbox password."
        )
    data["providers"] = providers
    if data.get("config_version", 1) < 4:
        data["config_version"] = 4
        migrated = True
        notices.append("Configuration version updated with bounded production research settings.")
    if migrated:
        return data, " ".join(
            notices
        ) or "Configuration migrated to Private Email transport defaults."
    return data, None


def load_settings(path: Path | None = None, paths: AppPaths | None = None) -> Settings:
    paths = paths or default_paths()
    config_path = path or Path(os.getenv("ELIORA_OUTREACH_CONFIG", paths.config_file))
    if not config_path.exists():
        return Settings()
    original_text = config_path.read_text(encoding="utf-8")
    raw = yaml.safe_load(original_text) or {}
    migrated, notice = migrate_config_data(raw)
    if notice:
        # Validate the candidate before changing the existing file. The old file is
        # retained as a backup and the migration write is atomic.
        candidate = Settings.model_validate(_env_overrides(dict(migrated)))
        backup = config_path.with_name(f"{config_path.name}.gmail-backup.yml")
        if not backup.exists():
            _atomic_write_text(backup, original_text)
        _atomic_write_text(
            config_path,
            yaml.safe_dump(
                _settings_payload(
                    candidate,
                    preserved_openai_api_key=raw.get("providers", {}).get("openai_api_key"),
                ),
                sort_keys=False,
            ),
        )
    migrated["config_migration_notice"] = notice
    return Settings.model_validate(_env_overrides(migrated))


def write_settings(
    settings: Settings, path: Path | None = None, paths: AppPaths | None = None
) -> Path:
    paths = paths or default_paths()
    target = path or paths.config_file
    target.parent.mkdir(parents=True, exist_ok=True)
    preserved_openai_api_key = _existing_openai_api_key(target)
    _atomic_write_text(
        target,
        yaml.safe_dump(
            _settings_payload(settings, preserved_openai_api_key=preserved_openai_api_key),
            sort_keys=False,
        ),
    )
    return target


def _settings_payload(
    settings: Settings, preserved_openai_api_key: Any | None = None
) -> dict[str, Any]:
    payload = settings.model_dump(
        mode="json", exclude_none=True, exclude={"config_migration_notice"}
    )
    # New API keys are loaded from the environment/keyring and are never copied
    # into YAML. If an older config already contains one, preserve it verbatim
    # instead of silently replacing or deleting a user's existing secret.
    payload.get("providers", {}).pop("openai_api_key", None)
    if preserved_openai_api_key:
        payload.setdefault("providers", {})["openai_api_key"] = preserved_openai_api_key
    return payload


def _existing_openai_api_key(target: Path) -> Any | None:
    if not target.exists():
        return None
    try:
        existing = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
        return (existing.get("providers", {}) or {}).get("openai_api_key")
    except (OSError, TypeError, ValueError, yaml.YAMLError):
        return None


def _atomic_write_text(target: Path, content: str) -> None:
    """Write a private config without exposing a partial or world-readable file."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
        )
        temporary = Path(temporary_name)
        if os.name != "nt":
            os.chmod(temporary, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        temporary = None
        if os.name != "nt":
            target.chmod(0o600)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
