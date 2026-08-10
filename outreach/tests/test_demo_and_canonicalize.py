from pathlib import Path

from eliora_outreach.db import Database
from eliora_outreach.pipeline import run_synthetic_demo
from eliora_outreach.research.canonicalize import (
    canonicalize_url,
    is_private_ip,
    registrable_domain,
)


def test_canonicalization_and_ssrf_guards() -> None:
    assert (
        canonicalize_url("HTTPS://Example.com/path/?utm_source=x&b=2")
        == "https://example.com/path?b=2"
    )
    assert registrable_domain("careers.example.co.uk") == "example.co.uk"
    assert is_private_ip("127.0.0.1") and is_private_ip("169.254.169.254")


def test_offline_end_to_end(tmp_path: Path) -> None:
    database = Database(tmp_path / "demo.sqlite3")
    result = run_synthetic_demo(database)
    assert result["offline"] is True
    assert result["draft_guardrails"] is True
    assert result["reply"] == "unsubscribe"
