from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock, Timeout


@contextmanager
def application_lock(path: Path, timeout: float = 0) -> Iterator[bool]:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(path))
    try:
        lock.acquire(timeout=timeout)
    except Timeout:
        yield False
        return
    try:
        yield True
    finally:
        lock.release()
