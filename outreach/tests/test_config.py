from pathlib import Path

import pytest
import yaml
from pydantic import SecretStr
from typer.testing import CliRunner

from eliora_outreach import cli
from eliora_outreach.config import (
    PRIVATE_EMAIL_POLICY_VERSION,
    SenderSettings,
    Settings,
    is_placeholder_email,
    mask_email,
    write_settings,
)
from eliora_outreach.paths import AppPaths


def test_placeholder_rejected() -> None:
    with pytest.raises(ValueError):
        Settings(sender={"email": "your@email.com"})
    with pytest.raises(ValueError):
        Settings(sender={"postal_address": "123 Main Street"})
    assert is_placeholder_email("person@example.com")


def test_secret_safe_mask_and_private_config(tmp_path: Path) -> None:
    paths = AppPaths(tmp_path / "state")
    settings = Settings(
        sender={
            "email": "sender@eliora.example",
            "reply_to": "owner@eliora.example",
            "owner_bcc": "owner@eliora.example",
            "postal_address": "100 Demo Way",
        }
    )
    path = write_settings(settings, paths=paths)
    assert path.stat().st_mode & 0o077 == 0
    assert "sender@" not in mask_email(settings.sender.email)
    paths.assert_private(Path("/tmp/unrelated-repository"))


def test_eliora_defaults_and_safe_secret_serialization(tmp_path: Path) -> None:
    settings = Settings(providers={"openai_api_key": SecretStr("sk-test-only")})
    assert settings.company.legal_name == "EliOra Tech Solutions LLC"
    assert settings.company.website == "https://elioratechsolutions.com"
    assert settings.sender.title == "Lead Data Engineer"
    assert settings.sender.email == "shingai@elioratechsolutions.com"
    assert settings.sender.postal_address == ""
    assert settings.sender.meeting_link == ""
    assert settings.schedule.research_time == "09:00"
    assert settings.schedule.send_start == "07:00"
    assert settings.schedule.send_end == "19:00"
    assert settings.limits.recommended_daily_initials == 5
    assert settings.limits.recommended_daily_followups == 1
    assert settings.limits.hard_daily_prospect_messages == 10
    path = write_settings(settings, paths=AppPaths(tmp_path / "state"))
    text = path.read_text(encoding="utf-8")
    assert "openai_api_key" not in text
    assert "sk-test-only" not in text


def test_existing_yaml_openai_secret_is_preserved_without_being_echoed(tmp_path: Path) -> None:
    config = tmp_path / "config.yml"
    config.write_text(
        yaml.safe_dump({"config_version": 3, "providers": {"openai_api_key": "sk-existing-fake"}}),
        encoding="utf-8",
    )
    settings = cli.load_settings(path=config, paths=AppPaths(tmp_path / "state"))
    cli.write_settings(settings, path=config, paths=AppPaths(tmp_path / "state"))
    assert "openai_api_key: sk-existing-fake" in config.read_text(encoding="utf-8")


def test_meeting_link_is_optional_but_https_only() -> None:
    assert SenderSettings(meeting_link="").meeting_link == ""
    assert SenderSettings(meeting_link="https://calendar.example.com/book").meeting_link
    with pytest.raises(ValueError):
        SenderSettings(meeting_link="http://calendar.example.com/book")


def test_normal_setup_only_asks_for_missing_private_fields(tmp_path: Path, monkeypatch) -> None:
    paths = AppPaths(tmp_path / "state")
    monkeypatch.setattr(cli, "default_paths", lambda: paths)
    prompts = iter(["100 Demo Way, Albany, NY 12207", ""])
    monkeypatch.setattr(cli.typer, "prompt", lambda *args, **kwargs: next(prompts))
    confirmations = iter([True, True])
    monkeypatch.setattr(cli.typer, "confirm", lambda *args, **kwargs: next(confirmations))

    result = CliRunner().invoke(cli.app, ["setup"])

    assert result.exit_code == 0, result.stdout
    saved = cli.load_settings(paths=paths)
    assert saved.sender.postal_address == "100 Demo Way, Albany, NY 12207"
    assert saved.sender.meeting_link == ""
    assert saved.providers.mailbox_username == saved.sender.email
    assert saved.providers.permission_policy_version == PRIVATE_EMAIL_POLICY_VERSION
    assert saved.live.enabled is False
    assert paths.config_file.stat().st_mode & 0o077 == 0


def test_setup_preserves_existing_live_state_and_meeting_link(tmp_path: Path, monkeypatch) -> None:
    paths = AppPaths(tmp_path / "state")
    existing = Settings(
        sender={
            "email": "owner@eliora.example",
            "reply_to": "owner@eliora.example",
            "owner_bcc": "owner@eliora.example",
            "postal_address": "100 Demo Way",
            "meeting_link": "https://calendar.example.com/book",
        },
        providers={
            "mailbox_username": "owner@eliora.example",
            "permission_policy_acknowledged": True,
            "permission_policy_version": PRIVATE_EMAIL_POLICY_VERSION,
        },
        live={"enabled": True},
    )
    write_settings(existing, paths=paths)
    monkeypatch.setattr(cli, "default_paths", lambda: paths)
    monkeypatch.setattr(
        cli.typer, "prompt", lambda *args, **kwargs: pytest.fail("unexpected prompt")
    )

    result = CliRunner().invoke(cli.app, ["setup"])

    assert result.exit_code == 0, result.stdout
    saved = cli.load_settings(paths=paths)
    assert saved.live.enabled is True
    assert saved.sender.meeting_link == "https://calendar.example.com/book"
    assert saved.sender.postal_address == "100 Demo Way"


def test_invalid_setup_keeps_previous_config_intact(tmp_path: Path, monkeypatch) -> None:
    paths = AppPaths(tmp_path / "state")
    write_settings(
        Settings(
            sender={
                "email": "owner@eliora.example",
                "reply_to": "owner@eliora.example",
                "owner_bcc": "owner@eliora.example",
                "postal_address": "100 Demo Way",
            },
            providers={
                "mailbox_username": "owner@eliora.example",
                "permission_policy_acknowledged": True,
            },
        ),
        paths=paths,
    )
    before = paths.config_file.read_bytes()
    monkeypatch.setattr(cli, "default_paths", lambda: paths)
    monkeypatch.setattr(cli.typer, "prompt", lambda *args, **kwargs: "http://not-https.example")

    result = CliRunner().invoke(cli.app, ["setup"])

    assert result.exit_code != 0
    assert paths.config_file.read_bytes() == before


def test_config_show_redacts_private_postal_address(tmp_path: Path, monkeypatch) -> None:
    paths = AppPaths(tmp_path / "state")
    write_settings(
        Settings(sender={"postal_address": "100 Demo Way"}),
        paths=paths,
    )
    monkeypatch.setattr(cli, "default_paths", lambda: paths)
    monkeypatch.setattr(cli, "_mail_password_present", lambda settings: (False, "missing"))
    monkeypatch.setattr(cli, "_keychain_secret_present", lambda account, key: (False, "no"))
    monkeypatch.setattr(cli, "_scheduler_state", lambda: "not installed")

    result = CliRunner().invoke(cli.app, ["config", "show"])

    assert result.exit_code == 0, result.stdout
    assert "postal_address=configured privately" in result.stdout
    assert "100 Demo Way" not in result.stdout
    assert "live=disabled" in result.stdout
