from __future__ import annotations

import os
import sys
from pathlib import Path

from platformdirs import user_config_dir, user_data_dir, user_log_dir

APP_NAME = "eliora-outreach"
APP_AUTHOR = "EliOra"


class AppPaths:
    """All mutable state is outside the repository and can be relocated for cloud use."""

    def __init__(self, root: Path | None = None) -> None:
        if root is not None:
            base = root.expanduser().resolve()
            self.data = base / "data"
            self.config = base / "config"
            self.logs = base / "logs"
        else:
            self.data = Path(
                os.environ.get("ELIORA_OUTREACH_DATA_DIR", user_data_dir(APP_NAME, APP_AUTHOR))
            )
            self.config = Path(
                os.environ.get("ELIORA_OUTREACH_CONFIG_DIR", user_config_dir(APP_NAME, APP_AUTHOR))
            )
            self.logs = Path(
                os.environ.get("ELIORA_OUTREACH_LOG_DIR", user_log_dir(APP_NAME, APP_AUTHOR))
            )
        self.db = self.data / "outreach.sqlite3"
        self.runtime = self.data / "runtime"
        self.cache = self.data / "cache"
        self.exports = self.data / "exports"
        self.config_file = self.config / "config.yml"
        self.legacy_gmail_token = self.config / "gmail-token.json"
        self.legacy_gmail_credentials = self.config / "gmail-credentials.json"
        self.pause_file = self.runtime / "PAUSED"
        self.lock_file = self.runtime / "application.lock"

    def ensure(self) -> None:
        for path in (self.data, self.config, self.logs, self.runtime, self.cache, self.exports):
            path.mkdir(parents=True, exist_ok=True)
        for path in (self.config_file, self.legacy_gmail_token, self.legacy_gmail_credentials):
            if path.exists() and sys.platform != "win32":
                path.chmod(0o600)

    def assert_private(self, repository_root: Path) -> None:
        """Fail closed if a caller accidentally points mutable state into the repo."""
        repo = repository_root.resolve()
        for path in (
            self.data,
            self.config,
            self.logs,
            self.db,
            self.cache,
            self.legacy_gmail_token,
        ):
            try:
                path.resolve().relative_to(repo)
            except ValueError:
                continue
            raise ValueError(f"Private outreach path must be outside repository: {path}")


def default_paths() -> AppPaths:
    paths = AppPaths()
    paths.ensure()
    return paths
