from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from .canonicalize import validate_public_url
from .extraction import clean_public_text
from .robots import allowed_by_robots


@dataclass(frozen=True)
class FetchedPage:
    url: str
    title: str
    text: str
    status_code: int
    content_type: str
    retrieved_at: datetime
    robots_allowed: bool
    raw_html: str = ""


class CrawlerBudgetExceeded(RuntimeError):
    """Raised when a bounded crawler operation reaches its HTTP request budget."""


class SafeCrawler:
    def __init__(
        self,
        *,
        user_agent: str,
        max_html_bytes: int = 2_000_000,
        max_text_chars: int = 60_000,
        timeout: float = 15.0,
        max_requests: int = 80,
        max_pages_per_domain: int = 8,
        client: httpx.Client | None = None,
    ) -> None:
        self.user_agent = user_agent
        self.max_html_bytes = max_html_bytes
        self.max_text_chars = max_text_chars
        self.timeout = timeout
        self.max_requests = max_requests
        self.max_pages_per_domain = max_pages_per_domain
        self.client = client or httpx.Client(
            follow_redirects=False,
            timeout=timeout,
            headers={"User-Agent": user_agent},
        )
        self._last_domain_fetch: dict[str, float] = {}
        self._domain_pages: dict[str, int] = {}
        self._requests = 0

    def fetch(self, url: str) -> FetchedPage:
        canonical = validate_public_url(url)
        domain = (urlparse(canonical).hostname or "").lower()
        if self._requests >= self.max_requests:
            raise CrawlerBudgetExceeded("HTTP research request budget exhausted")
        if self._domain_pages.get(domain, 0) >= self.max_pages_per_domain:
            raise CrawlerBudgetExceeded("HTTP research per-domain page budget exhausted")
        now = time.monotonic()
        elapsed = now - self._last_domain_fetch.get(domain, 0)
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        if not allowed_by_robots(canonical, self.user_agent):
            raise PermissionError("robots.txt denied this public page")
        current = canonical
        response: httpx.Response | None = None
        for _ in range(6):
            self._requests += 1
            if self._requests > self.max_requests:
                raise CrawlerBudgetExceeded("HTTP research request budget exhausted")
            response = self.client.get(current)
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise ValueError("Redirect response has no destination")
                current = validate_public_url(str(httpx.URL(current).join(location)))
                continue
            validate_public_url(str(response.url))
            break
        if response is None or response.is_redirect:
            raise ValueError("Too many public-page redirects")
        if urlparse(current).hostname != urlparse(canonical).hostname and not allowed_by_robots(
            current, self.user_agent
        ):
            raise PermissionError("robots.txt denied the public redirect destination")
        self._last_domain_fetch[domain] = time.monotonic()
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        if content_type not in {"text/html", "application/xhtml+xml"}:
            raise ValueError(f"Unsupported public content type: {content_type or 'unknown'}")
        if len(response.content) > self.max_html_bytes:
            raise ValueError("Public page exceeds configured size limit")
        self._domain_pages[domain] = self._domain_pages.get(domain, 0) + 1
        return FetchedPage(
            current,
            self._title(response.text),
            clean_public_text(response.text, self.max_text_chars),
            response.status_code,
            content_type,
            datetime.now(timezone.utc),
            True,
            response.text,
        )

    @staticmethod
    def _title(html: str) -> str:
        from bs4 import BeautifulSoup

        title = BeautifulSoup(html, "html.parser").title
        return title.get_text(" ", strip=True)[:500] if title else "Untitled public page"
