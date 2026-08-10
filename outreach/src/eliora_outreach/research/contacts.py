from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import unquote

from bs4 import BeautifulSoup

from .canonicalize import registrable_domain, validate_public_url

FREE_DOMAINS = {
    "gmail.com",
    "googlemail.com",
    "yahoo.com",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "icloud.com",
    "proton.me",
    "protonmail.com",
    "aol.com",
}
INAPPROPRIATE = {
    "abuse",
    "privacy",
    "legal",
    "security",
    "noreply",
    "no-reply",
    "billing",
    "support",
    "helpdesk",
    "careers",
    "jobs",
    "press",
    "media",
    "investor",
    "investors",
}
GENERAL = {"info", "hello", "contact"}
RELEVANT = {
    "operations",
    "ops",
    "data",
    "analytics",
    "finance",
    "cfo",
    "revenue",
    "revops",
    "gtm",
    "business",
}


@dataclass(frozen=True)
class ContactValidation:
    email: str
    valid: bool
    official_domain: bool
    category: str
    quality: int
    reason: str
    mx_valid: bool | None = None
    mx_result: str = "not_checked"


@dataclass(frozen=True)
class PublicContactCandidate:
    email: str
    source_url: str
    extraction_method: str
    display_name: str | None = None
    role: str | None = None
    context: str = ""
    source_title: str = ""


def normalized_email(value: str) -> str:
    return value.strip().lower()


def role_category(email: str, role: str | None = None) -> str:
    local = normalized_email(email).split("@", 1)[0]
    role_text = f"{local} {role or ''}".lower()
    if local in INAPPROPRIATE:
        return "inappropriate"
    if local in GENERAL:
        return "general"
    if any(token in role_text for token in RELEVANT):
        return "relevant_role"
    if "." in local or "_" in local or "-" in local:
        return "named"
    return "other"


def validate_public_contact(
    email: str,
    company_domain: str,
    *,
    source_url: str | None,
    extraction_method: str | None,
    role: str | None = None,
    mx_valid: bool | None = None,
    mx_result: str = "not_checked",
) -> ContactValidation:
    value = normalized_email(email)
    if not source_url or extraction_method not in {"visible_text", "mailto", "jsonld"}:
        return ContactValidation(
            value,
            False,
            False,
            "unverified",
            0,
            "No approved official source extraction",
            mx_valid,
            mx_result,
        )
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]{2,}", value):
        return ContactValidation(
            value, False, False, "invalid", 0, "Invalid email syntax", mx_valid, mx_result
        )
    local, domain = value.rsplit("@", 1)
    official = registrable_domain(domain) == registrable_domain(company_domain)
    if domain in FREE_DOMAINS:
        return ContactValidation(
            value,
            False,
            official,
            "free",
            0,
            "Free or personal mailbox provider",
            mx_valid,
            mx_result,
        )
    if not official:
        return ContactValidation(
            value,
            False,
            False,
            "domain_mismatch",
            0,
            "Email domain does not match official company domain",
            mx_valid,
            mx_result,
        )
    category = role_category(value, role)
    if category == "inappropriate":
        return ContactValidation(
            value,
            False,
            True,
            category,
            0,
            "Role inbox is not an appropriate sales target",
            mx_valid,
            mx_result,
        )
    quality = {"named": 15, "relevant_role": 13, "general": 9}.get(category, 0)
    if quality == 0:
        return ContactValidation(
            value,
            False,
            True,
            category,
            0,
            "No relevant published business contact category",
            mx_valid,
            mx_result,
        )
    return ContactValidation(
        value,
        True,
        True,
        category,
        quality,
        "Explicitly published on official domain",
        mx_valid,
        mx_result,
    )


def extract_public_contacts(
    html: str, source_url: str, company_domain: str, *, source_title: str = ""
) -> list[PublicContactCandidate]:
    """Extract only addresses explicitly present on an official public page.

    This deliberately has no local-part generation or name-to-email inference.
    """
    canonical_source = validate_public_url(source_url, resolve=False)
    if registrable_domain(canonical_source) != registrable_domain(company_domain):
        return []
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        if tag.name != "script" or tag.get("type") != "application/ld+json":
            tag.decompose()
    found: dict[str, PublicContactCandidate] = {}
    pattern = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.IGNORECASE)

    def add(
        email: str, method: str, *, display_name: str | None = None, role: str | None = None
    ) -> None:
        value = unquote(email).strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]{2,}", value):
            return
        context = " ".join(soup.get_text(" ").split())
        found.setdefault(
            value,
            PublicContactCandidate(
                value,
                canonical_source,
                method,
                display_name=display_name,
                role=role,
                context=context[:400],
                source_title=source_title[:500],
            ),
        )

    for link in soup.select('a[href^="mailto:"]'):
        href = str(link.get("href", ""))[7:].split("?", 1)[0]
        for email in pattern.findall(href):
            add(email, "mailto", role=link.get_text(" ", strip=True)[:120] or None)
    for email in pattern.findall(soup.get_text(" ")):
        add(email, "visible_text")

    def walk_json(value: object) -> None:
        if isinstance(value, dict):
            email = value.get("email")
            if isinstance(email, str):
                for item in pattern.findall(email):
                    add(
                        item,
                        "jsonld",
                        display_name=str(value.get("name")) if value.get("name") else None,
                        role=str(value.get("jobTitle")) if value.get("jobTitle") else None,
                    )
            for nested in value.values():
                walk_json(nested)
        elif isinstance(value, list):
            for nested in value:
                walk_json(nested)

    for script in BeautifulSoup(html, "html.parser").select('script[type="application/ld+json"]'):
        try:
            walk_json(json.loads(script.string or script.get_text()))
        except (TypeError, ValueError):
            continue
    return list(found.values())


def check_mx(domain: str, timeout: float = 3.0) -> tuple[bool | None, str]:
    try:
        import dns.resolver

        answer = dns.resolver.resolve(domain, "MX", lifetime=timeout)
        return bool(answer), "mx_present" if answer else "mx_empty"
    except Exception as exc:  # DNS is advisory and must never crash research.
        return None, type(exc).__name__
