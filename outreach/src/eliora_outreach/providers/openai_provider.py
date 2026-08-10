from __future__ import annotations

import random
import time
from collections.abc import Callable
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

from ..prompts import SYSTEM_SAFETY
from .base import ProviderResult, ResearchProviderError, WebSearchResult


def _value(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _response_id(response: Any) -> str | None:
    return _value(response, "id") or _value(response, "_request_id")


def _usage(response: Any) -> tuple[int, int]:
    usage = _value(response, "usage")
    return (
        int(_value(usage, "input_tokens", 0) or 0),
        int(_value(usage, "output_tokens", 0) or 0),
    )


def _error_body(exc: Exception) -> dict[str, Any]:
    body = _value(exc, "body", {}) or {}
    if not isinstance(body, dict):
        return {}
    error = body.get("error", body)
    return error if isinstance(error, dict) else {}


def _error_headers(exc: Exception) -> dict[str, str]:
    response = _value(exc, "response")
    headers = _value(response, "headers", {}) or {}
    if hasattr(headers, "items"):
        return {str(key).lower(): str(value) for key, value in headers.items()}
    return {}


def _retry_after_seconds(exc: Exception) -> float | None:
    value = _error_headers(exc).get("retry-after")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


def _request_id_from_error(exc: Exception) -> str | None:
    headers = _error_headers(exc)
    return (
        str(_value(exc, "request_id") or _value(exc, "_request_id") or "")
        or headers.get("x-request-id")
        or None
    )


def _classify_error(exc: Exception) -> ResearchProviderError:
    status = _value(exc, "status_code") or _value(_value(exc, "response"), "status_code")
    body = _error_body(exc)
    code = str(
        body.get("code") or body.get("type") or _value(exc, "code") or _value(exc, "type") or ""
    ).lower()
    provider_message = str(body.get("message") or _value(exc, "message") or "").lower()
    name = type(exc).__name__.lower()
    request_id = _request_id_from_error(exc)
    retry_after = _retry_after_seconds(exc)
    rate_words = " ".join((code, provider_message, name))
    if code == "insufficient_quota" or "insufficient_quota" in rate_words:
        return ResearchProviderError(
            "OpenAI project quota is insufficient",
            category="insufficient_quota",
            request_id=request_id,
            error_code=code or "insufficient_quota",
            action="Check OpenAI project billing and usage limits.",
        )
    if code == "billing_hard_limit_reached" or "billing_hard_limit_reached" in rate_words:
        return ResearchProviderError(
            "OpenAI project billing hard limit reached",
            category="billing_hard_limit_reached",
            request_id=request_id,
            error_code=code or "billing_hard_limit_reached",
            action="Check OpenAI project billing and usage limits.",
        )
    request_limited = any(
        marker in rate_words
        for marker in ("rate_limit_exceeded", "requests per", "request limit", "rpm", "rps")
    ) or ("request" in code and "limit" in code)
    token_limited = any(
        marker in rate_words
        for marker in (
            "token limit",
            "token_limit",
            "tokens per",
            "tpm",
            "context length",
            "tokens",
        )
    ) or ("token" in code and "limit" in code)
    if status == 429 or "ratelimit" in name or request_limited or token_limited:
        category = "token_limit" if token_limited and not request_limited else "rate_limit_exceeded"
        return ResearchProviderError(
            f"OpenAI {category.replace('_', ' ')}",
            category=category,
            transient=True,
            request_id=request_id,
            retry_after_seconds=retry_after,
            error_code=code or category,
            action="Retry after the provider cooldown; reduce request or token rate if it persists.",
        )
    if isinstance(status, int) and status >= 500:
        return ResearchProviderError(
            "OpenAI service error",
            category="server_error",
            transient=True,
            request_id=request_id,
            retry_after_seconds=retry_after,
        )
    if "timeout" in name or "connection" in name:
        return ResearchProviderError(
            "OpenAI connection timeout",
            category="timeout",
            transient=True,
            request_id=request_id,
            retry_after_seconds=retry_after,
        )
    if status in {401, 403} or "authentication" in name:
        return ResearchProviderError(
            "OpenAI authentication failed", category="authentication", request_id=request_id
        )
    if status == 404 or "model" in str(exc).lower():
        return ResearchProviderError(
            "Configured OpenAI model is unavailable", category="model", request_id=request_id
        )
    if status in {400, 422}:
        return ResearchProviderError(
            "OpenAI request was rejected", category="invalid_request", request_id=request_id
        )
    return ResearchProviderError(
        "OpenAI research request failed", category="provider_error", request_id=request_id
    )


class OpenAIResponsesProvider:
    """Responses API provider retaining web-search provenance at the boundary."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-5.4-mini",
        client: Any | None = None,
        *,
        sleep_fn: Callable[[float], None] = time.sleep,
        random_fn: Callable[[], float] = random.random,
    ) -> None:
        if not api_key.strip() and client is None:
            raise ResearchProviderError("OpenAI API key is not configured", category="missing_key")
        if client is None:
            try:
                from openai import OpenAI

                client = OpenAI(api_key=api_key)
            except Exception as exc:  # pragma: no cover - SDK import is environment-specific
                raise ResearchProviderError(
                    "OpenAI provider could not be initialized", category="initialization"
                ) from exc
        self.client = client
        self.model = model
        self._sleep = sleep_fn
        self._random = random_fn

    def _create(self, kwargs: dict[str, Any]) -> Any:
        attempts = 3
        for attempt in range(attempts):
            try:
                return self.client.responses.create(**kwargs)
            except Exception as exc:
                error = _classify_error(exc)
                if not error.transient or attempt == attempts - 1:
                    raise error from exc
                # Immediate retries are bounded. A provider hint is retained on
                # the terminal error for the run-level cooldown, but cannot make
                # this process sleep for minutes or hours.
                base_delay = 0.2 * (2**attempt)
                hinted_delay = error.retry_after_seconds or 0.0
                delay = min(5.0, max(base_delay, hinted_delay))
                delay += self._random() * 0.25
                self._sleep(delay)
        raise AssertionError("unreachable")

    def _search_result(
        self,
        query: str,
        *,
        allowed_domains: list[str] | None = None,
        max_tool_calls: int = 1,
        search_context_size: str = "medium",
    ) -> ProviderResult:
        tool: dict[str, Any] = {
            "type": "web_search",
            "search_context_size": search_context_size,
        }
        if allowed_domains:
            tool["filters"] = {"allowed_domains": allowed_domains}
        response = self._create(
            {
                "model": self.model,
                "input": f"{SYSTEM_SAFETY}\n\n{query}",
                "tools": [tool],
                "max_tool_calls": max_tool_calls,
                "include": ["web_search_call.action.sources"],
                "store": False,
            }
        )
        input_tokens, output_tokens = _usage(response)
        result = self._parse_web_search_response(response, query=query)
        return ProviderResult(
            result,
            request_id=result.http_request_id or result.response_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def _parse_web_search_response(self, response: Any, *, query: str) -> WebSearchResult:
        output = _value(response, "output", []) or []
        queries: list[str] = []
        source_urls: list[str] = []
        citations: list[dict[str, str]] = []
        tool_calls = 0
        for item in output:
            item_type = _value(item, "type", "")
            if item_type == "web_search_call":
                tool_calls += 1
                action = _value(item, "action", {})
                for found_query in _value(action, "queries", []) or []:
                    if found_query not in queries:
                        queries.append(str(found_query))
                for source in _value(action, "sources", []) or []:
                    url = _value(source, "url")
                    if url and str(url) not in source_urls:
                        source_urls.append(str(url))
                    if url:
                        citations.append(
                            {
                                "url": str(url),
                                "title": str(_value(source, "title", "")),
                            }
                        )
            for content in _value(item, "content", []) or []:
                for annotation in _value(content, "annotations", []) or []:
                    url = _value(annotation, "url")
                    if url and str(url) not in source_urls:
                        source_urls.append(str(url))
                    if url:
                        citations.append(
                            {
                                "url": str(url),
                                "title": str(_value(annotation, "title", "")),
                            }
                        )
        if not queries:
            queries.append(query)
        return WebSearchResult(
            output_text=str(_value(response, "output_text", "") or ""),
            response_id=_response_id(response),
            http_request_id=_value(response, "_request_id"),
            model=str(_value(response, "model", self.model) or self.model),
            tool_calls=tool_calls,
            queries=tuple(queries),
            source_urls=tuple(dict.fromkeys(source_urls)),
            citations=tuple(citations),
            status=_value(response, "status"),
        )

    def search(
        self,
        query: str,
        *,
        allowed_domains: list[str] | None = None,
        max_tool_calls: int = 1,
        search_context_size: str = "medium",
    ) -> ProviderResult:
        return self._search_result(
            query,
            allowed_domains=allowed_domains,
            max_tool_calls=max_tool_calls,
            search_context_size=search_context_size,
        )

    def structured(self, prompt: str, schema: dict[str, Any]) -> ProviderResult:
        response = self._create(
            {
                "model": self.model,
                "input": f"{SYSTEM_SAFETY}\n\n{prompt}",
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "eliora_structured_result",
                        "schema": schema,
                        "strict": True,
                    }
                },
                "store": False,
            }
        )
        input_tokens, output_tokens = _usage(response)
        return ProviderResult(
            str(_value(response, "output_text", "") or ""),
            request_id=_value(response, "_request_id") or _value(response, "id"),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
