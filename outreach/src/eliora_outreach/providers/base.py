from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ProviderResult:
    value: Any
    request_id: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class WebSearchResult:
    """The small, provider-neutral subset of a Responses web-search result we retain."""

    output_text: str
    response_id: str | None = None
    http_request_id: str | None = None
    model: str | None = None
    tool_calls: int = 0
    queries: tuple[str, ...] = ()
    source_urls: tuple[str, ...] = ()
    citations: tuple[dict[str, str], ...] = ()
    status: str | None = None
    raw_output: dict[str, Any] | None = None


class ResearchProviderError(RuntimeError):
    """A categorized research failure safe to show in a run audit."""

    def __init__(
        self,
        message: str,
        *,
        category: str,
        transient: bool = False,
        retryable: bool | None = None,
        retry_after_seconds: float | None = None,
        request_id: str | None = None,
        error_code: str | None = None,
        action: str | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.transient = transient
        self.retryable = transient if retryable is None else retryable
        self.retry_after_seconds = retry_after_seconds
        self.request_id = request_id
        self.error_code = error_code
        self.action = action


@dataclass(frozen=True)
class TransportResult:
    accepted: bool
    provider_message_id: str | None
    provider_thread_id: str | None
    rfc_message_id: str
    mailbox_uid: str | None = None
    metadata: dict[str, str] | None = None


class MailTransportError(RuntimeError):
    def __init__(
        self, message: str, *, category: str, transient: bool, uncertain: bool = False
    ) -> None:
        super().__init__(message)
        self.category = category
        self.transient = transient
        self.uncertain = uncertain


class ResearchProvider(Protocol):
    def search(
        self,
        query: str,
        *,
        allowed_domains: list[str] | None = None,
        max_tool_calls: int = 1,
        search_context_size: str = "medium",
    ) -> ProviderResult: ...

    def structured(self, prompt: str, schema: dict[str, Any]) -> ProviderResult: ...


class ExtractionProvider(Protocol):
    def extract(self, source_text: str, source_ids: list[str]) -> ProviderResult: ...


class DraftProvider(Protocol):
    def draft(self, facts: dict[str, Any]) -> ProviderResult: ...


class EmailProvider(Protocol):
    def send(
        self,
        raw_message: bytes,
        *,
        idempotency_key: str,
        envelope_recipients: list[str] | None = None,
    ) -> ProviderResult: ...

    def find_by_message_id(self, message_id: str) -> ProviderResult | None: ...


class MailboxProvider(Protocol):
    def tracked_events(self, thread_ids: list[str]) -> list[dict[str, Any]]: ...

    def find_recent_sent(
        self,
        *,
        recipient: str,
        subject: str,
        sent_at: Any,
        window_minutes: int = 180,
    ) -> dict[str, str] | None: ...
