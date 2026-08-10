"""Authenticated Namecheap Private Email SMTP/IMAP transport.

The implementation uses the Python standard library and accepts injected protocol
factories so tests never need a real mailbox.
"""

from __future__ import annotations

import email
import hashlib
import imaplib
import re
import smtplib
import ssl
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from email.utils import getaddresses, parsedate_to_datetime
from typing import Any

from ..config import ProviderSettings
from ..secrets import SecretStore, default_secret_store
from .base import MailTransportError, ProviderResult, TransportResult

SMTPFactory = Callable[..., Any]
IMAPFactory = Callable[..., Any]


def _password_or_error(username: str, secret_store: SecretStore) -> str:
    password = secret_store.get(username)
    if not password:
        raise MailTransportError(
            "Mailbox password is not present in the OS secret store. Run ./outreachctl secrets set-mail-password.",
            category="missing_secret",
            transient=False,
        )
    return password


def _rfc_id_from_bytes(raw_message: bytes) -> str:
    parsed = email.message_from_bytes(raw_message)
    value = parsed.get("Message-ID")
    if not value:
        raise MailTransportError(
            "Message-ID is required before SMTP transport",
            category="invalid_message",
            transient=False,
        )
    return value


def _quoted_search_value(client: Any, value: str) -> str:
    """Quote one IMAP search atom with imaplib's escaping rules."""
    quote = getattr(client, "_quote", None)
    if callable(quote):
        return str(quote(value))
    standard_quote = imaplib.IMAP4._quote  # type: ignore[attr-defined]
    return str(standard_quote(client, value))


def _message_body(message: Any) -> bytes:
    if message.is_multipart():
        parts: list[bytes] = []
        for part in message.walk():
            if part.get_content_type() == "text/plain":
                parts.append(part.get_payload(decode=True) or b"")
        return b"\n".join(parts)
    return message.get_payload(decode=True) or b""


def _smtp_error(exc: BaseException, *, during_data: bool = False) -> MailTransportError:
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return MailTransportError(
            "Private Email authentication failed. Verify the full mailbox username and OS-stored password. No message was sent.",
            category="authentication",
            transient=False,
        )
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        transient = any(int(code) < 500 for code, _ in exc.recipients.values())
        return MailTransportError(
            "SMTP recipient negotiation was rejected",
            category="transient_recipient" if transient else "permanent_recipient",
            transient=transient,
        )
    if isinstance(exc, smtplib.SMTPDataError):
        code = int(exc.smtp_code)
        return MailTransportError(
            "SMTP server rejected message data",
            category="transient_server" if code < 500 else "permanent_server",
            transient=code < 500,
        )
    if isinstance(exc, (smtplib.SMTPServerDisconnected, TimeoutError, OSError)):
        return MailTransportError(
            "Encrypted SMTP connection ended before delivery could be confirmed",
            category="uncertain_delivery" if during_data else "network",
            transient=True,
            uncertain=during_data,
        )
    return MailTransportError(
        "Unexpected SMTP transport failure",
        category="transport",
        transient=True,
        uncertain=during_data,
    )


@dataclass(frozen=True)
class MailboxFolders:
    inbox: str
    sent: str


class PrivateEmailSMTPProvider:
    def __init__(
        self,
        settings: ProviderSettings,
        *,
        username: str,
        secret_store: SecretStore | None = None,
        password: str | None = None,
        smtp_factory: SMTPFactory | None = None,
    ) -> None:
        self.settings = settings
        self.username = username
        self.secret_store = secret_store or default_secret_store()
        self._password = password
        self.smtp_factory = smtp_factory
        self.authenticated = False

    def _client(self) -> Any:
        context = ssl.create_default_context()
        password = self._password or _password_or_error(self.username, self.secret_store)
        client: Any = None
        try:
            if self.settings.smtp_security == "ssl":
                factory = self.smtp_factory or smtplib.SMTP_SSL
                client = factory(
                    self.settings.smtp_host,
                    self.settings.smtp_port,
                    timeout=self.settings.mail_timeout_seconds,
                    context=context,
                )
            else:
                factory = self.smtp_factory or smtplib.SMTP
                client = factory(
                    self.settings.smtp_host,
                    self.settings.smtp_port,
                    timeout=self.settings.mail_timeout_seconds,
                )
                client.ehlo()
                client.starttls(context=context)
                client.ehlo()
            client.ehlo()
            client.login(
                self.username,
                password,
            )
            self.authenticated = True
            return client
        except MailTransportError:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
            raise
        except Exception as exc:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
            raise _smtp_error(exc) from None

    def authenticate(self) -> bool:
        client = self._client()
        try:
            client.quit()
        except Exception:
            try:
                client.close()
            except Exception:
                pass
        return True

    def send(
        self,
        raw_message: bytes,
        *,
        idempotency_key: str,
        envelope_recipients: list[str] | None = None,
    ) -> ProviderResult:
        rfc_message_id = _rfc_id_from_bytes(raw_message)
        recipients = envelope_recipients or self._headers_to_recipients(raw_message)
        if not recipients:
            raise MailTransportError(
                "SMTP envelope has no recipients",
                category="invalid_message",
                transient=False,
            )
        sender = email.message_from_bytes(raw_message).get("From", "")
        sender_address = re.search(r"<([^>]+)>", sender)
        envelope_sender = sender_address.group(1) if sender_address else sender
        client = self._client()
        try:
            result = client.sendmail(envelope_sender, recipients, raw_message)
            if result:
                codes = [int(code) for code, _detail in result.values()]
                transient = any(code < 500 for code in codes)
                raise MailTransportError(
                    "SMTP server rejected one or more envelope recipients",
                    category="transient_recipient" if transient else "permanent_recipient",
                    transient=transient,
                )
            transport = TransportResult(
                accepted=True,
                provider_message_id=None,
                provider_thread_id=None,
                rfc_message_id=rfc_message_id,
                metadata={
                    "transport": "smtp",
                    "idempotency_key_hash": hashlib.sha256(idempotency_key.encode()).hexdigest()[
                        :16
                    ],
                },
            )
            return ProviderResult(transport, request_id=idempotency_key[:16])
        except MailTransportError:
            raise
        except Exception as exc:
            raise _smtp_error(exc, during_data=True) from None
        finally:
            try:
                client.quit()
            except Exception:
                try:
                    client.close()
                except Exception:
                    pass

    @staticmethod
    def _headers_to_recipients(raw_message: bytes) -> list[str]:
        parsed = email.message_from_bytes(raw_message)
        values = [parsed.get("To", ""), parsed.get("Cc", "")]
        from email.utils import getaddresses

        return [address for _, address in getaddresses(values) if address]


class PrivateEmailIMAPProvider:
    def __init__(
        self,
        settings: ProviderSettings,
        *,
        username: str,
        secret_store: SecretStore | None = None,
        password: str | None = None,
        imap_factory: IMAPFactory | None = None,
    ) -> None:
        self.settings = settings
        self.username = username
        self.secret_store = secret_store or default_secret_store()
        self._password = password
        self.imap_factory = imap_factory
        self.authenticated = False
        self.folders = MailboxFolders("INBOX", "Sent")
        self.uid_checkpoint = 0

    def _client(self) -> Any:
        context = ssl.create_default_context()
        password = self._password or _password_or_error(self.username, self.secret_store)
        client: Any = None
        try:
            if self.settings.imap_security == "ssl":
                factory = self.imap_factory or imaplib.IMAP4_SSL
                client = factory(
                    self.settings.imap_host,
                    self.settings.imap_port,
                    timeout=self.settings.mail_timeout_seconds,
                    ssl_context=context,
                )
            else:
                factory = self.imap_factory or imaplib.IMAP4
                client = factory(
                    self.settings.imap_host,
                    self.settings.imap_port,
                    timeout=self.settings.mail_timeout_seconds,
                )
                client.ehlo()
                client.starttls(ssl_context=context)
                client.ehlo()
            result, _ = client.login(self.username, password)
            if result != "OK":
                raise MailTransportError(
                    "Private Email IMAP authentication failed",
                    category="authentication",
                    transient=False,
                )
            self.authenticated = True
            self.folders = self.discover_folders(client)
            return client
        except MailTransportError:
            if client is not None:
                try:
                    client.logout()
                except Exception:
                    pass
            raise
        except Exception as exc:
            if client is not None:
                try:
                    client.logout()
                except Exception:
                    pass
            category = "authentication" if isinstance(exc, imaplib.IMAP4.error) else "network"
            raise MailTransportError(
                "Could not authenticate to encrypted Private Email IMAP",
                category=category,
                transient=category == "network",
            ) from None

    def authenticate(self) -> bool:
        client = self._client()
        try:
            client.logout()
        except Exception:
            pass
        return True

    @staticmethod
    def discover_folders(client: Any) -> MailboxFolders:
        _status, rows = client.list()
        inbox = "INBOX"
        sent = "Sent"
        for row in rows or []:
            value = row.decode(errors="replace") if isinstance(row, bytes) else str(row)
            match = re.search(r'\(([^)]*)\).*?"([^"]+)"$', value)
            if not match:
                continue
            flags, name = match.groups()
            if "\\Sent" in flags or name.lower() in {"sent", "sent mail", "sent items"}:
                sent = name
            if name.lower() == "inbox":
                inbox = name
        return MailboxFolders(inbox, sent)

    def find_sent_by_message_id(self, rfc_message_id: str) -> str | None:
        client = self._client()
        try:
            client.select(self.folders.sent, readonly=True)
            _status, data = client.uid("search", None, "HEADER", "Message-ID", rfc_message_id)
            values = (data or [b""])[0].decode(errors="replace").split()
            return values[0] if values else None
        finally:
            try:
                client.logout()
            except Exception:
                pass

    def find_recent_sent(
        self,
        *,
        recipient: str,
        subject: str,
        sent_at: datetime,
        window_minutes: int = 180,
    ) -> dict[str, str] | None:
        """Find one exact recent message in the provider's Sent folder.

        The server-side search is narrowed by a bounded date range and quoted
        recipient.  Subject is deliberately verified locally because this
        Private Email IMAP server rejects unquoted spaced SUBJECT arguments.
        Zero or multiple exact matches are intentionally treated as no match.
        """
        if sent_at.tzinfo is None:
            raise ValueError("sent_at must include a timezone")
        target = sent_at.astimezone(timezone.utc)
        start = target - timedelta(minutes=window_minutes)
        end = target + timedelta(minutes=window_minutes)
        wanted_recipient = recipient.strip().casefold()
        wanted_subject = subject.strip().casefold()
        client = self._client()
        candidates: list[dict[str, str]] = []
        try:
            client.select(self.folders.sent, readonly=True)
            _status, data = client.uid(
                "search",
                None,
                "SINCE",
                start.strftime("%d-%b-%Y"),
                "BEFORE",
                (end + timedelta(days=1)).strftime("%d-%b-%Y"),
                "HEADER",
                "TO",
                _quoted_search_value(client, recipient),
            )
            uids = [value for value in (data or [b""])[0].decode(errors="replace").split()]
            for uid in uids[:25]:
                _fetch_status, fetched = client.uid("fetch", uid, "(RFC822.HEADER)")
                raw = b"".join(
                    part[1] for part in fetched or [] if isinstance(part, tuple) and len(part) > 1
                )
                if not raw:
                    continue
                message = email.message_from_bytes(raw)
                addresses = [
                    address.casefold()
                    for _name, address in getaddresses(
                        message.get_all("To", []) + message.get_all("Cc", [])
                    )
                    if address
                ]
                decoded_subject = str(make_header(decode_header(str(message.get("Subject", "")))))
                date_header = message.get("Date")
                if not date_header:
                    continue
                try:
                    message_time = parsedate_to_datetime(str(date_header))
                except (TypeError, ValueError, IndexError):
                    continue
                if message_time.tzinfo is None:
                    message_time = message_time.replace(tzinfo=timezone.utc)
                message_time = message_time.astimezone(timezone.utc)
                if (
                    wanted_recipient not in addresses
                    or decoded_subject.casefold() != wanted_subject
                    or not (start <= message_time <= end)
                ):
                    continue
                rfc_message_id = str(message.get("Message-ID", "")).strip() or None
                provider_message_id = str(message.get("X-Provider-Message-ID", "")).strip() or None
                provider_thread_id = next(
                    (
                        str(message.get(name, "")).strip()
                        for name in ("X-EliOra-Thread-ID", "X-Thread-ID", "X-GM-THRID")
                        if message.get(name)
                    ),
                    None,
                )
                candidate = {
                    "mailbox_uid": uid,
                    "recipient": recipient,
                    "subject": decoded_subject,
                    "sent_at": message_time.isoformat(),
                }
                if rfc_message_id:
                    candidate["rfc_message_id"] = rfc_message_id
                if provider_message_id:
                    candidate["provider_message_id"] = provider_message_id
                if provider_thread_id:
                    candidate["provider_thread_id"] = provider_thread_id
                candidates.append(candidate)
            return candidates[0] if len(candidates) == 1 else None
        finally:
            try:
                client.logout()
            except Exception:
                pass

    def append_sent_if_missing(self, raw_message: bytes, rfc_message_id: str) -> str | None:
        existing = self.find_sent_by_message_id(rfc_message_id)
        if existing:
            return existing
        client = self._client()
        try:
            internal_date = imaplib.Time2Internaldate(datetime.now(timezone.utc))
            status, data = client.append(self.folders.sent, "\\Seen", internal_date, raw_message)
            if status != "OK":
                return None
        finally:
            try:
                client.logout()
            except Exception:
                pass
        return self.find_sent_by_message_id(rfc_message_id)

    def tracked_events(self, thread_ids: list[str]) -> list[dict[str, Any]]:
        """Fetch only messages newer than the in-memory UID checkpoint.

        A worker persists this checkpoint with its run state; keeping it on the
        provider also makes repeated hourly calls bounded in the local process.
        """
        client = self._client()
        events: list[dict[str, Any]] = []
        try:
            client.select(self.folders.inbox, readonly=True)
            _status, data = client.uid("search", None, "UID", f"{self.uid_checkpoint + 1}:*")
            uids = [int(value) for value in (data or [b""])[0].split()]
            for uid in uids:
                _status, fetched = client.uid("fetch", str(uid), "(RFC822.HEADER BODY.PEEK[TEXT])")
                raw = b"".join(part[1] for part in fetched or [] if isinstance(part, tuple))
                message = email.message_from_bytes(raw)
                headers = {key.lower(): str(value) for key, value in message.items()}
                references = f"{headers.get('in-reply-to', '')} {headers.get('references', '')}"
                if thread_ids and any(thread_id in references for thread_id in thread_ids):
                    events.append(
                        {
                            "mailbox_uid": str(uid),
                            "headers": headers,
                            "body": _message_body(message),
                        }
                    )
                self.uid_checkpoint = max(self.uid_checkpoint, uid)
            return events
        finally:
            try:
                client.logout()
            except Exception:
                pass


class PrivateEmailProvider:
    """Combined provider facade used by connectivity checks and workers."""

    def __init__(
        self,
        settings: ProviderSettings,
        *,
        username: str,
        secret_store: SecretStore | None = None,
        password: str | None = None,
        smtp_factory: SMTPFactory | None = None,
        imap_factory: IMAPFactory | None = None,
    ) -> None:
        self.smtp = PrivateEmailSMTPProvider(
            settings,
            username=username,
            secret_store=secret_store,
            password=password,
            smtp_factory=smtp_factory,
        )
        self.imap = PrivateEmailIMAPProvider(
            settings,
            username=username,
            secret_store=secret_store,
            password=password,
            imap_factory=imap_factory,
        )

    def connectivity_check(self) -> dict[str, Any]:
        self.smtp.authenticate()
        self.imap.authenticate()
        return {
            "smtp": True,
            "imap": True,
            "inbox": self.imap.folders.inbox,
            "sent": self.imap.folders.sent,
        }

    def send(
        self,
        raw_message: bytes,
        *,
        idempotency_key: str,
        envelope_recipients: list[str] | None = None,
    ) -> ProviderResult:
        result = self.smtp.send(
            raw_message, idempotency_key=idempotency_key, envelope_recipients=envelope_recipients
        )
        if not isinstance(result.value, TransportResult):
            return result
        try:
            mailbox_uid = self.imap.append_sent_if_missing(raw_message, result.value.rfc_message_id)
        except Exception:
            # SMTP DATA was accepted. Preserve that fact even if the optional
            # Sent-copy reconciliation is temporarily unavailable.
            return result
        return ProviderResult(
            replace(result.value, mailbox_uid=mailbox_uid), request_id=result.request_id
        )

    def find_by_message_id(self, message_id: str) -> ProviderResult | None:
        uid = self.imap.find_sent_by_message_id(message_id)
        return ProviderResult({"mailbox_uid": uid}) if uid else None

    def find_recent_sent(
        self,
        *,
        recipient: str,
        subject: str,
        sent_at: datetime,
        window_minutes: int = 180,
    ) -> dict[str, str] | None:
        return self.imap.find_recent_sent(
            recipient=recipient,
            subject=subject,
            sent_at=sent_at,
            window_minutes=window_minutes,
        )

    def tracked_events(self, thread_ids: list[str]) -> list[dict[str, Any]]:
        return self.imap.tracked_events(thread_ids)

    @property
    def uid_checkpoint(self) -> int:
        return self.imap.uid_checkpoint

    @uid_checkpoint.setter
    def uid_checkpoint(self, value: int) -> None:
        self.imap.uid_checkpoint = value
