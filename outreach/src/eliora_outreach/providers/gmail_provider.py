from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from .base import ProviderResult

SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
READ_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


class GmailProvider:
    def __init__(
        self, credentials_path: Path, token_path: Path, *, interactive: bool = False
    ) -> None:
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.interactive = interactive
        self.service = self._authorize()

    def _authorize(self) -> Any:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        scopes = [SEND_SCOPE, READ_SCOPE]
        credentials = (
            Credentials.from_authorized_user_file(str(self.token_path), scopes)
            if self.token_path.exists()
            else None
        )
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        if not credentials or not credentials.valid:
            if not self.interactive:
                raise RuntimeError("Gmail OAuth token is missing or expired; run auth gmail")
            flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_path), scopes)
            credentials = flow.run_local_server(port=0)
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            self.token_path.write_text(credentials.to_json(), encoding="utf-8")
            if self.token_path.stat().st_mode & 0o777 and self.token_path != Path("NUL"):
                self.token_path.chmod(0o600)
        return build("gmail", "v1", credentials=credentials, cache_discovery=False)

    def profile(self) -> dict[str, Any]:
        return self.service.users().getProfile(userId="me").execute()

    def send(self, raw_message: bytes, *, idempotency_key: str) -> ProviderResult:
        encoded = base64.urlsafe_b64encode(raw_message).decode().rstrip("=")
        result = self.service.users().messages().send(userId="me", body={"raw": encoded}).execute()
        return ProviderResult(result, request_id=result.get("id"))

    def find_by_message_id(self, message_id: str) -> ProviderResult | None:
        query = f'"{message_id}"'
        result = self.service.users().messages().list(userId="me", q=query, maxResults=5).execute()
        messages = result.get("messages", [])
        if not messages:
            return None
        return ProviderResult(messages[0])

    def tracked_events(self, thread_ids: list[str]) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for thread_id in thread_ids:
            thread = (
                self.service.users()
                .threads()
                .get(userId="me", id=thread_id, format="metadata")
                .execute()
            )
            for message in thread.get("messages", []):
                events.append(message)
        return events
