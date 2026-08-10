from __future__ import annotations

from datetime import datetime, timezone
from email.message import EmailMessage

import pytest

from eliora_outreach.config import ProviderSettings
from eliora_outreach.providers.base import MailTransportError, TransportResult
from eliora_outreach.providers.private_email_provider import (
    PrivateEmailIMAPProvider,
    PrivateEmailSMTPProvider,
)
from eliora_outreach.secrets import MemorySecretStore


def settings(**overrides: object) -> ProviderSettings:
    return ProviderSettings(**overrides)


def test_private_email_defaults_and_security_pairs() -> None:
    defaults = settings()
    assert defaults.mail_provider == "namecheap_private_email"
    assert (defaults.smtp_host, defaults.smtp_port, defaults.smtp_security) == (
        "mail.privateemail.com",
        465,
        "ssl",
    )
    assert (defaults.imap_host, defaults.imap_port, defaults.imap_security) == (
        "mail.privateemail.com",
        993,
        "ssl",
    )
    with pytest.raises(ValueError):
        settings(smtp_security="ssl", smtp_port=587)
    with pytest.raises(ValueError):
        settings(imap_security="starttls", imap_port=993)


def raw_message() -> bytes:
    message = EmailMessage()
    message["From"] = "owner@eliora.example"
    message["To"] = "prospect@customer.example"
    message["Message-ID"] = "<transport-test@eliora.example>"
    message["Subject"] = "Transport test"
    message.set_content("Test")
    return message.as_bytes()


class FakeSMTP:
    instances: list[FakeSMTP] = []
    fail_login = False
    fail_data = False

    def __init__(self, host: str, port: int, **kwargs: object) -> None:
        self.host = host
        self.port = port
        self.kwargs = kwargs
        self.envelope: tuple[str, list[str], bytes] | None = None
        self.login_args: tuple[str, str] | None = None
        self.__class__.instances.append(self)

    def ehlo(self) -> None:
        pass

    def starttls(self, **kwargs: object) -> None:
        pass

    def login(self, username: str, password: str) -> None:
        self.login_args = (username, password)
        if self.fail_login:
            import smtplib

            raise smtplib.SMTPAuthenticationError(535, b"bad credentials")

    def sendmail(
        self, sender: str, recipients: list[str], raw: bytes
    ) -> dict[str, tuple[int, bytes]]:
        if self.fail_data:
            import smtplib

            raise smtplib.SMTPServerDisconnected("connection lost")
        self.envelope = (sender, recipients, raw)
        return {}

    def quit(self) -> None:
        pass

    def close(self) -> None:
        pass


def test_smtp_uses_os_secret_and_envelope_bcc_without_header() -> None:
    FakeSMTP.instances.clear()
    store = MemorySecretStore()
    store.set("owner@eliora.example", "secret-never-in-config")
    provider = PrivateEmailSMTPProvider(
        settings(),
        username="owner@eliora.example",
        secret_store=store,
        smtp_factory=FakeSMTP,
    )

    result = provider.send(
        raw_message(),
        idempotency_key="company:1:contact:1",
        envelope_recipients=["prospect@customer.example", "owner@eliora.example"],
    )

    assert isinstance(result.value, TransportResult)
    smtp = FakeSMTP.instances[-1]
    assert smtp.login_args == ("owner@eliora.example", "secret-never-in-config")
    assert smtp.envelope is not None
    assert smtp.envelope[1] == ["prospect@customer.example", "owner@eliora.example"]
    assert b"Bcc:" not in smtp.envelope[2]
    assert b"To: prospect@customer.example" in smtp.envelope[2]
    assert "secret-never-in-config" not in smtp.envelope[2].decode()


def test_smtp_authentication_and_uncertain_delivery_are_classified() -> None:
    store = MemorySecretStore()
    store.set("owner@eliora.example", "pw")
    FakeSMTP.fail_login = True
    try:
        provider = PrivateEmailSMTPProvider(
            settings(),
            username="owner@eliora.example",
            secret_store=store,
            smtp_factory=FakeSMTP,
        )
        with pytest.raises(MailTransportError, match="authentication failed") as auth_error:
            provider.send(raw_message(), idempotency_key="auth")
        assert auth_error.value.category == "authentication"
        assert not auth_error.value.uncertain
    finally:
        FakeSMTP.fail_login = False

    FakeSMTP.fail_data = True
    try:
        provider = PrivateEmailSMTPProvider(
            settings(),
            username="owner@eliora.example",
            secret_store=store,
            smtp_factory=FakeSMTP,
        )
        with pytest.raises(MailTransportError) as delivery_error:
            provider.send(raw_message(), idempotency_key="uncertain")
        assert delivery_error.value.category == "uncertain_delivery"
        assert delivery_error.value.uncertain
    finally:
        FakeSMTP.fail_data = False


def test_missing_secret_fails_before_sending() -> None:
    provider = PrivateEmailSMTPProvider(
        settings(),
        username="owner@eliora.example",
        secret_store=MemorySecretStore(),
        smtp_factory=FakeSMTP,
    )
    with pytest.raises(MailTransportError, match="OS secret store") as error:
        provider.send(raw_message(), idempotency_key="missing")
    assert error.value.category == "missing_secret"


class FakeIMAP:
    state = {"sent": False, "uid": "42"}

    def __init__(self, host: str, port: int, **kwargs: object) -> None:
        self.selected = ""

    def starttls(self, **kwargs: object) -> None:
        pass

    def login(self, username: str, password: str) -> tuple[str, list[bytes]]:
        return "OK", [b"logged in"]

    def list(self) -> tuple[str, list[bytes]]:
        return "OK", [b'(\\HasNoChildren \\Sent) "/" "Sent"', b'(\\HasNoChildren) "/" "INBOX"']

    def select(self, folder: str, readonly: bool = False) -> tuple[str, list[bytes]]:
        self.selected = folder
        return "OK", [b"1"]

    def uid(self, command: str, *args: str) -> tuple[str, list[bytes] | list[tuple[bytes, bytes]]]:
        if command.lower() == "search":
            if args[2] == "Message-ID":
                return "OK", [self.state["uid"].encode() if self.state["sent"] else b""]
            return "OK", [b"7"]
        if command.lower() == "fetch":
            message = EmailMessage()
            message["Message-ID"] = "<reply@customer.example>"
            message["In-Reply-To"] = "<thread-1@eliora.example>"
            message["Subject"] = "Re: test"
            message["From"] = "prospect@customer.example"
            message.set_content("No thanks")
            return "OK", [(b"body", message.as_bytes())]
        raise AssertionError(command)

    def append(
        self, folder: str, flags: str, internal_date: str, raw: bytes
    ) -> tuple[str, list[bytes]]:
        self.state["sent"] = True
        return "OK", [b"42"]

    def logout(self) -> tuple[str, list[bytes]]:
        return "BYE", [b""]


def test_imap_sent_reconciliation_and_uid_checkpoint() -> None:
    FakeIMAP.state = {"sent": False, "uid": "42"}
    store = MemorySecretStore()
    store.set("owner@eliora.example", "pw")
    provider = PrivateEmailIMAPProvider(
        settings(),
        username="owner@eliora.example",
        secret_store=store,
        imap_factory=FakeIMAP,
    )

    assert provider.find_sent_by_message_id("<transport-test@eliora.example>") is None
    assert provider.append_sent_if_missing(raw_message(), "<transport-test@eliora.example>") == "42"
    assert provider.append_sent_if_missing(raw_message(), "<transport-test@eliora.example>") == "42"
    events = provider.tracked_events(["thread-1"])
    assert events[0]["mailbox_uid"] == "7"
    assert provider.uid_checkpoint == 7


class RecentSentIMAP(FakeIMAP):
    message_subject = "Manual subject"
    last_search_args: tuple[object, ...] = ()

    def uid(self, command: str, *args: str):
        if command.lower() == "search":
            self.__class__.last_search_args = args
            return "OK", [b"42 43"]
        if command.lower() == "fetch":
            uid = args[0]
            message = EmailMessage()
            message["From"] = "owner@eliora.example"
            message["To"] = "prospect@customer.example" if uid == "42" else "other@example.com"
            message["Message-ID"] = f"<recent-{uid}@eliora.example>"
            message["Subject"] = self.message_subject if uid == "42" else "Unrelated"
            message["Date"] = "Mon, 10 Aug 2026 15:30:00 +0000"
            return "OK", [(b"header", message.as_bytes())]
        return super().uid(command, *args)


def test_narrow_recent_sent_lookup_requires_exact_recipient_subject_and_time() -> None:
    provider = PrivateEmailIMAPProvider(
        settings(),
        username="owner@eliora.example",
        password="pw",
        imap_factory=RecentSentIMAP,
    )
    found = provider.find_recent_sent(
        recipient="prospect@customer.example",
        subject="Manual subject",
        sent_at=datetime(2026, 8, 10, 15, 30, tzinfo=timezone.utc),
        window_minutes=30,
    )
    assert found is not None
    assert found["mailbox_uid"] == "42"
    assert "SUBJECT" not in {str(value).upper() for value in RecentSentIMAP.last_search_args}
    unrelated = provider.find_recent_sent(
        recipient="other@example.com",
        subject="Manual subject",
        sent_at=datetime(2026, 8, 10, 15, 30, tzinfo=timezone.utc),
        window_minutes=30,
    )
    assert unrelated is None

    class OnlyMatchingIMAP(RecentSentIMAP):
        def uid(self, command: str, *args: str):
            if command.lower() == "search":
                return "OK", [b"42"]
            return super().uid(command, *args)

    provider = PrivateEmailIMAPProvider(
        settings(),
        username="owner@eliora.example",
        password="pw",
        imap_factory=OnlyMatchingIMAP,
    )
    found = provider.find_recent_sent(
        recipient="prospect@customer.example",
        subject="Manual subject",
        sent_at=datetime(2026, 8, 10, 15, 30, tzinfo=timezone.utc),
        window_minutes=30,
    )
    assert found == {
        "mailbox_uid": "42",
        "recipient": "prospect@customer.example",
        "subject": "Manual subject",
        "sent_at": "2026-08-10T15:30:00+00:00",
        "rfc_message_id": "<recent-42@eliora.example>",
    }


@pytest.mark.parametrize(
    "subject",
    [
        "Helping streamline RevOps as Hauler Hero grows",
        "Idea: RevOps, reporting & handoffs!",
        'Owner\'s "practical" reporting idea',
        "运营 reporting idea — Q3",
    ],
)
def test_recent_sent_header_matching_handles_subject_special_characters(subject: str) -> None:
    class SubjectIMAP(RecentSentIMAP):
        message_subject = subject

        def uid(self, command: str, *args: str):
            if command.lower() == "search":
                self.__class__.last_search_args = args
                return "OK", [b"42"]
            return super().uid(command, *args)

    provider = PrivateEmailIMAPProvider(
        settings(),
        username="owner@eliora.example",
        password="pw",
        imap_factory=SubjectIMAP,
    )
    found = provider.find_recent_sent(
        recipient="prospect@customer.example",
        subject=subject,
        sent_at=datetime(2026, 8, 10, 15, 30, tzinfo=timezone.utc),
        window_minutes=30,
    )
    assert found is not None
    assert found["rfc_message_id"] == "<recent-42@eliora.example>"
    assert "SUBJECT" not in {str(value).upper() for value in SubjectIMAP.last_search_args}
