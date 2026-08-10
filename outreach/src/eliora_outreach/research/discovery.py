from __future__ import annotations

import json
from datetime import date
from typing import Any, Protocol

from ..models import DiscoveredCandidate
from ..prompts import SYSTEM_SAFETY
from ..providers.base import ProviderResult, WebSearchResult
from .canonicalize import (
    is_directory_or_data_broker,
    is_reserved_domain,
    registrable_domain,
    validate_public_url,
)
from .query_planner import QueryPlan, plan_queries


class DiscoveryProvider(Protocol):
    def search(self, query: str, **kwargs: Any) -> ProviderResult | list[dict[str, Any]]: ...


def validate_candidate(raw: dict[str, Any]) -> DiscoveredCandidate:
    candidate = DiscoveredCandidate.model_validate(raw)
    website = str(candidate.official_website_candidate)
    canonical = validate_public_url(website, resolve=False)
    domain = registrable_domain(canonical)
    if is_reserved_domain(canonical) or is_directory_or_data_broker(canonical):
        raise ValueError("Candidate domain is reserved or not an official company domain")
    if not domain:
        raise ValueError("Candidate has no registrable domain")
    if not candidate.observed_signal.get("source_urls"):
        raise ValueError("Candidate must include a source URL")
    return candidate


def _search_candidates(value: object, source_urls: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        candidates = value.get("candidates", value.get("results", []))
        if isinstance(candidates, list):
            return [item for item in candidates if isinstance(item, dict)]
    if isinstance(value, str):
        try:
            cleaned = value.strip().removeprefix("```json").removesuffix("```").strip()
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            return []
        return _search_candidates(parsed, source_urls)
    return []


def _provider_candidates(result: object) -> list[dict[str, Any]]:
    if isinstance(result, ProviderResult):
        value = result.value
        sources = value.source_urls if isinstance(value, WebSearchResult) else ()
        candidates = _search_candidates(value, sources)
        if not candidates and isinstance(value, WebSearchResult):
            candidates = _search_candidates(value.output_text, value.source_urls)
        return candidates
    return _search_candidates(result)


def bounded_discovery(
    provider: DiscoveryProvider, day: date, *, max_queries: int = 8, max_candidates: int = 30
) -> tuple[list[QueryPlan], list[DiscoveredCandidate]]:
    queries = plan_queries(day, max_queries=max_queries)
    results: list[DiscoveredCandidate] = []
    seen_domains: set[str] = set()
    for query in queries:
        try:
            response = provider.search(
                f"{SYSTEM_SAFETY}\nSearch query: {query.query}",
                max_tool_calls=1,
                search_context_size="medium",
            )
        except TypeError:
            response = provider.search(f"{SYSTEM_SAFETY}\nSearch query: {query.query}")
        for raw in _provider_candidates(response):
            try:
                candidate = validate_candidate(raw)
            except Exception:
                continue
            domain = registrable_domain(str(candidate.official_website_candidate))
            if domain in seen_domains:
                continue
            seen_domains.add(domain)
            results.append(candidate)
            if len(results) >= max_candidates:
                return queries, results
    return queries, results
