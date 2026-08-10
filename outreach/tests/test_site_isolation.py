from pathlib import Path


def test_outreach_private_artifacts_are_not_in_docs() -> None:
    root = Path(__file__).resolve().parents[2]
    docs = root / "docs"
    forbidden = (".sqlite", "token.json", "credentials.json", "client_secret", "api_key")
    assert not any(
        path.is_file() and any(token in path.name.lower() for token in forbidden)
        for path in docs.rglob("*")
    )
