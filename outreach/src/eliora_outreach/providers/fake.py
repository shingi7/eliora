from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from .base import ProviderResult, WebSearchResult


class FakeResearchProvider:
    def __init__(self, candidates: list[dict[str, Any]] | None = None) -> None:
        self.candidates = candidates or []
        self.queries: list[str] = []

    def search(self, query: str) -> list[dict[str, Any]]:
        self.queries.append(query)
        return list(self.candidates)


class FakeProductionResearchProvider:
    """Offline fixture provider whose IDs look like production responses, never demo data."""

    def __init__(
        self,
        candidates: list[dict[str, Any]] | None = None,
        analyses: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.candidates = candidates or [
            {
                "company_name": "Harbor Operations",
                "official_website_candidate": "https://harbor-operations.com",
                "country": "United States",
                "vertical": "operational_business",
                "employee_band": "50-99",
                "observed_signal": {
                    "signal_category": "reporting",
                    "observed_signal": "The company is hiring for reporting and data operations.",
                    "source_urls": ["https://harbor-operations.com/news/expansion"],
                },
                "why_potential_fit": "Public reporting workflow signal.",
                "recommended_research_pages": ["https://harbor-operations.com/about"],
                "confidence": 0.9,
            }
        ]
        self.analyses = analyses or {
            "harbor-operations.com": {
                "company": {
                    "name": "Harbor Operations",
                    "official_website": "https://harbor-operations.com",
                    "country": "United States",
                    "vertical": "operational_business",
                    "employee_band": "50-99",
                },
                "sources": [
                    {
                        "url": "https://harbor-operations.com/about",
                        "title": "About Harbor Operations",
                        "publisher": "harbor-operations.com",
                        "source_type": "official",
                        "source_tier": "A",
                        "excerpt": "Harbor Operations supports multi-location reporting and operational data workflows.",
                    },
                    {
                        "url": "https://harbor-operations.com/news/expansion",
                        "title": "Harbor Operations expands its reporting team",
                        "publisher": "harbor-operations.com",
                        "source_type": "official_press",
                        "source_tier": "A",
                        "excerpt": "The company is expanding its reporting and data operations team.",
                    },
                ],
                "signals": [
                    {
                        "source_url": "https://harbor-operations.com/news/expansion",
                        "signal_type": "manual_reporting",
                        "observed_signal": "The company is expanding its reporting and data operations team.",
                        "confidence": 0.9,
                    }
                ],
                "pain_hypotheses": [
                    {
                        "category": "manual_reporting",
                        "hypothesis": "The expansion may create more recurring reporting handoffs.",
                        "confidence": 0.86,
                        "service_match": "Reporting Automation Sprint",
                    }
                ],
                "contacts": [
                    {
                        "email": "operations@harbor-operations.com",
                        "source_url": "https://harbor-operations.com/about",
                        "extraction_method": "visible_text",
                        "explicitly_published": True,
                        "role": "Operations",
                        "context": "Operations contact published on the company page.",
                    }
                ],
                "overall_confidence": 0.9,
            }
        }
        self.queries: list[str] = []

    def search(
        self,
        query: str,
        *,
        allowed_domains: list[str] | None = None,
        max_tool_calls: int = 1,
        search_context_size: str = "medium",
    ) -> ProviderResult:
        self.queries.append(query)
        if allowed_domains:
            domain = allowed_domains[0]
            payload = self.analyses.get(domain, {})
            rows = payload.get("sources", [])
            urls = tuple(
                str(item["url"]) for item in rows if isinstance(item, dict) and item.get("url")
            )
            output = json.dumps(payload)
        else:
            urls = tuple(
                str(url)
                for candidate in self.candidates
                for url in (candidate.get("observed_signal") or {}).get("source_urls", [])
            )
            output = json.dumps({"candidates": self.candidates})
        value = WebSearchResult(
            output_text=output,
            response_id=f"production-request-{len(self.queries)}",
            model="offline-production-fixture",
            tool_calls=max_tool_calls,
            queries=(query,),
            source_urls=urls,
            status="completed",
        )
        return ProviderResult(value, request_id=value.response_id)

    def structured(self, prompt: str, schema: dict[str, Any]) -> ProviderResult:
        return ProviderResult(
            json.dumps({"candidates": self.candidates}),
            request_id="production-request-structured",
        )


class FakeExtractionProvider:
    def extract(self, source_text: str, source_ids: list[str]) -> ProviderResult:
        return ProviderResult({"source_ids": source_ids, "text": source_text[:500]})


class FakeDraftProvider:
    def draft(self, facts: dict[str, Any]) -> ProviderResult:
        return ProviderResult(facts)


class FakeEmailProvider:
    def __init__(self) -> None:
        self.sent: dict[str, dict[str, Any]] = {}
        self.events: list[dict[str, Any]] = []

    def send(
        self,
        raw_message: bytes,
        *,
        idempotency_key: str,
        envelope_recipients: list[str] | None = None,
    ) -> ProviderResult:
        message_id = hashlib.sha256(raw_message).hexdigest()[:16]
        value = {
            "provider_message_id": f"fake-{uuid.uuid4().hex[:10]}",
            "provider_thread_id": f"thread-{idempotency_key}",
            "rfc_message_id": message_id,
            "raw": raw_message,
            "envelope_recipients": envelope_recipients or [],
        }
        self.sent[idempotency_key] = value
        return ProviderResult(value, request_id=f"fake-request-{message_id}")

    def find_by_message_id(self, message_id: str) -> ProviderResult | None:
        for value in self.sent.values():
            if value["rfc_message_id"] == message_id or value.get("message_id") == message_id:
                return ProviderResult(value)
        return None

    def tracked_events(self, thread_ids: list[str]) -> list[dict[str, Any]]:
        return [event for event in self.events if event.get("thread_id") in thread_ids]

    def add_reply(self, thread_id: str, body: str, sender: str = "prospect@example.org") -> None:
        self.events.append(
            {
                "thread_id": thread_id,
                "provider_message_id": f"reply-{uuid.uuid4().hex}",
                "sender": sender,
                "body": body,
            }
        )


FakeGmailProvider = FakeEmailProvider
