from __future__ import annotations

import re
from datetime import date
from html import unescape

from bs4 import BeautifulSoup

from ..models import ExtractionResult
from ..prompts import SYSTEM_SAFETY


def clean_public_text(html: str, max_chars: int = 12000) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "form", "noscript", "svg", "nav", "footer"]):
        tag.decompose()
    text = " ".join(unescape(soup.get_text(" ")).split())
    return text[:max_chars]


def validate_extraction(result: ExtractionResult, source_ids: set[str]) -> ExtractionResult:
    for signal in result.signals:
        if signal.get("source_id") not in source_ids:
            raise ValueError("Every extracted observed signal must reference an existing source ID")
    signal_ids = {str(signal.get("id")) for signal in result.signals}
    for hypothesis in result.pain_hypotheses:
        missing = set(hypothesis.get("supporting_signal_ids", [])) - signal_ids
        if missing:
            raise ValueError(f"Pain hypothesis references unknown signal IDs: {sorted(missing)}")
        text = str(hypothesis.get("hypothesis", "")).lower()
        if any(assertion in text for assertion in ("has a problem", "is struggling", "definitely")):
            raise ValueError("Pain hypothesis must remain explicitly tentative")
    return result


def extract_deterministic_company_facts(text: str, source_id: str) -> dict[str, object]:
    """Small safe fallback used by offline demo and as a model-input normalizer."""
    date_match = re.search(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", text)
    return {
        "source_id": source_id,
        "observed_signal": text[:500].strip(),
        "signal_date": date(*map(int, date_match.groups())) if date_match else None,
        "instruction_policy": SYSTEM_SAFETY,
    }
