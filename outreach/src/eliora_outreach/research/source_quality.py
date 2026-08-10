from __future__ import annotations

from ..enums import SourceType
from .canonicalize import registrable_domain


def source_quality(
    source_type: SourceType | str, *, official: bool, fresh: bool, directory_only: bool = False
) -> float:
    source_type = SourceType(source_type)
    if directory_only or source_type is SourceType.DIRECTORY_HINT:
        return 0.15
    value = 0.6
    if official:
        value += 0.25
    if fresh:
        value += 0.15
    if source_type in {SourceType.OFFICIAL_JOB, SourceType.OFFICIAL_PRESS, SourceType.FILING}:
        value += 0.05
    return min(1.0, value)


def is_official_source(company_domain: str, source_url: str) -> bool:
    return registrable_domain(company_domain) == registrable_domain(source_url)
