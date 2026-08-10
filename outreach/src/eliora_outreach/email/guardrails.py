from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from ..config import SenderSettings
from ..models import DraftContent

DISALLOWED_HYPE = {
    "revolutionary",
    "game-changing",
    "10x",
    "guaranteed",
    "world-class",
    "best-in-class",
}
FAKE_THREAD_PREFIX = re.compile(r"^(re|fwd|fw):", re.IGNORECASE)


@dataclass(frozen=True)
class GuardrailFinding:
    code: str
    message: str
    severity: str = "error"


@dataclass
class GuardrailReport:
    passed: bool
    findings: list[GuardrailFinding] = field(default_factory=list)


def check_draft(
    content: DraftContent,
    sender: SenderSettings,
    *,
    approved_fact_ids: set[str],
    allowed_domains: set[str] | None = None,
    recipient_suppressed: bool = False,
    word_limits: tuple[int, int] = (80, 145),
    max_links: int = 1,
) -> GuardrailReport:
    findings: list[GuardrailFinding] = []
    body = content.body
    if FAKE_THREAD_PREFIX.match(content.subject.strip()):
        findings.append(
            GuardrailFinding(
                "fake_thread_subject", "Subject cannot pretend to be an existing thread"
            )
        )
    for label, value in (
        ("disclosure", sender.disclosure),
        ("postal_address", sender.postal_address),
        ("opt_out", sender.opt_out),
    ):
        if not value or value not in body:
            findings.append(GuardrailFinding(f"missing_{label}", f"Required {label} is missing"))
    words_before_footer = body.split(sender.disclosure, 1)[0].split()
    if len(words_before_footer) < word_limits[0] and "closing" not in content.subject.lower():
        findings.append(
            GuardrailFinding("too_short", f"Body has fewer than {word_limits[0]} pre-footer words")
        )
    if len(words_before_footer) > word_limits[1]:
        findings.append(
            GuardrailFinding("too_long", f"Body exceeds {word_limits[1]} pre-footer words")
        )
    urls = re.findall(r"https?://[^\s<>]+", body)
    if len(urls) > max_links:
        findings.append(GuardrailFinding("too_many_links", "Body contains more than one link"))
    if allowed_domains:
        for url in urls:
            if (urlparse(url).hostname or "").lower() not in allowed_domains:
                findings.append(
                    GuardrailFinding(
                        "unapproved_url", "Body contains a URL outside the approved domain set"
                    )
                )
    for phrase in DISALLOWED_HYPE:
        if phrase.lower() in body.lower():
            findings.append(GuardrailFinding("hype", f"Disallowed hype phrase: {phrase}"))
    if re.search(
        r"\b(?:has|is experiencing|needs)\s+(?:a problem|pain|manual work)\b", body, re.IGNORECASE
    ):
        findings.append(
            GuardrailFinding("asserted_pain", "Pain language must remain a tentative hypothesis")
        )
    if not content.source_fact_ids or not set(content.source_fact_ids).issubset(approved_fact_ids):
        findings.append(
            GuardrailFinding(
                "unsupported_fact", "Every observed fact must map to an approved source fact ID"
            )
        )
    if recipient_suppressed:
        findings.append(
            GuardrailFinding("suppressed", "Recipient or company is actively suppressed")
        )
    return GuardrailReport(not findings, findings)


def deterministic_quality_findings(report: GuardrailReport) -> dict[str, object]:
    return {
        "passed": report.passed,
        "findings": [
            {"code": item.code, "message": item.message, "severity": item.severity}
            for item in report.findings
        ],
    }
