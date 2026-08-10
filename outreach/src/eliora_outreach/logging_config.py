from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

_SECRET_PATTERNS = (
    re.compile(
        r"(?i)(api[_ -]?key|access[_ -]?token|refresh[_ -]?token|client[_ -]?secret|password)\s*[:=]\s*[^\s,;]+"
    ),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]+\b"),
)


def sanitize_log_message(value: object, *, limit: int = 500) -> str:
    """Return a short diagnostic safe for the local audit log and CLI."""
    message = str(value or "")
    for pattern in _SECRET_PATTERNS:
        message = pattern.sub("[redacted]", message)
    return message[:limit]


class SecretSafeFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = sanitize_log_message(record.getMessage(), limit=2_000)
        record.msg = message
        record.args = ()
        return True


def configure_logging(log_dir: Path, *, verbose: bool = False) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("eliora_outreach")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.propagate = False
    log_path = (log_dir / "outreach.log").resolve()
    matching = [
        handler
        for handler in logger.handlers
        if getattr(handler, "_eliora_log_path", None) == str(log_path)
    ]
    if not matching:
        for handler in list(logger.handlers):
            if getattr(handler, "_eliora_handler", False):
                logger.removeHandler(handler)
                handler.close()
        handler = RotatingFileHandler(
            log_path, maxBytes=1_000_000, backupCount=5, encoding="utf-8", delay=True
        )
        handler._eliora_handler = True  # type: ignore[attr-defined]
        handler._eliora_log_path = str(log_path)  # type: ignore[attr-defined]
        handler.addFilter(SecretSafeFilter())
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)
    if log_path.exists():
        log_path.chmod(0o600)
    return logger
