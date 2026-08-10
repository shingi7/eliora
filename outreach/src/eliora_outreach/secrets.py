"""OS credential-store access with injectable fakes for deterministic tests."""

from __future__ import annotations

from typing import Protocol

SERVICE_NAME = "com.elioratechsolutions.outreach"
MAIL_PASSWORD_KEY = "mail-password"
OPENAI_ACCOUNT = "openai"
OPENAI_API_KEY = "openai-api-key"


class SecretStore(Protocol):
    def get(self, account: str, key: str = MAIL_PASSWORD_KEY) -> str | None: ...
    def set(self, account: str, value: str, key: str = MAIL_PASSWORD_KEY) -> None: ...
    def delete(self, account: str, key: str = MAIL_PASSWORD_KEY) -> None: ...


class KeyringSecretStore:
    def __init__(self, service_name: str = SERVICE_NAME) -> None:
        self.service_name = service_name

    def get(self, account: str, key: str = MAIL_PASSWORD_KEY) -> str | None:
        import keyring

        return keyring.get_password(f"{self.service_name}:{key}", account)

    def set(self, account: str, value: str, key: str = MAIL_PASSWORD_KEY) -> None:
        import keyring

        keyring.set_password(f"{self.service_name}:{key}", account, value)

    def delete(self, account: str, key: str = MAIL_PASSWORD_KEY) -> None:
        import keyring

        try:
            keyring.delete_password(f"{self.service_name}:{key}", account)
        except Exception as exc:
            if type(exc).__name__ not in {"PasswordDeleteError", "ItemNotFoundException"}:
                raise


class MemorySecretStore:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def get(self, account: str, key: str = MAIL_PASSWORD_KEY) -> str | None:
        return self.values.get((account, key))

    def set(self, account: str, value: str, key: str = MAIL_PASSWORD_KEY) -> None:
        self.values[(account, key)] = value

    def delete(self, account: str, key: str = MAIL_PASSWORD_KEY) -> None:
        self.values.pop((account, key), None)


def default_secret_store() -> SecretStore:
    return KeyringSecretStore()
