from __future__ import annotations

import secrets


def session_token(session: dict[str, str]) -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def validate_token(session: dict[str, str], supplied: str | None) -> bool:
    expected = session.get("csrf_token")
    return bool(expected and supplied and secrets.compare_digest(expected, supplied))
