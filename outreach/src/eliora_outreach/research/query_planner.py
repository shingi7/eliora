from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class QueryPlan:
    vertical: str
    intent: str
    query: str


VERTICALS = {
    "healthcare": ["healthcare administration", "healthtech provider operations"],
    "financial_services": ["financial services", "fintech insurance operations"],
    "operational_business": ["B2B SaaS operations", "professional services logistics"],
    "sports": ["sports organization league athletic department"],
}

INTENTS = [
    "hiring reporting analyst BI data quality",
    "ERP CRM EHR platform migration integration",
    "operations expansion new locations analytics",
    "AI pilot data governance workflow",
    "revenue operations forecast data hygiene FP&A collections",
    "support operations SLA backlog analytics",
    "compliance audit reporting modernization",
    "new CFO finance transformation margin forecasting",
    "RevOps CRM migration pipeline forecasting",
    "data engineering API integration legacy modernization",
    "prior authorization revenue cycle analytics",
    "multi-site practice acquisition quality reporting",
    "sports front office scouting roster analytics",
]


def plan_queries(
    day: date,
    *,
    max_queries: int = 8,
    offset: int = 0,
    geography: str = "US",
    vertical_weights: dict[str, int] | None = None,
) -> list[QueryPlan]:
    plans: list[QueryPlan] = []
    weights = vertical_weights or {
        "healthcare": 35,
        "financial_services": 25,
        "operational_business": 30,
        "sports": 10,
    }
    weighted: list[str] = []
    for name, weight in weights.items():
        if name in VERTICALS:
            weighted.extend([name] * max(0, weight))
    if not weighted:
        weighted = list(VERTICALS)
    for index in range(max_queries):
        vertical = weighted[(index * 17 + day.toordinal() + offset) % len(weighted)]
        intent = INTENTS[(index * 2 + day.toordinal() + offset) % len(INTENTS)]
        plans.append(
            QueryPlan(vertical, intent, f"{geography} {VERTICALS[vertical][0]} {intent} {day.year}")
        )
    return plans
