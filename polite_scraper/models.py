from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class BookRecord:
    """A normalized catalogue record from a Books to Scrape listing page."""

    title: str
    price_gbp: float
    availability: str
    rating: int
    product_url: str
    source_page: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PageResult:
    page: int
    url: str
    succeeded: bool
    records: int = 0
    cache_hit: bool = False
    network_fetch: bool = False
    network_attempted: bool = False
    robots_allowed: bool | None = None
    robots_policy_source: str | None = None
    robots_fetch_error: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RunReport:
    run_label: str
    started_at: str
    finished_at: str = ""
    pages_attempted: int = 0
    pages_succeeded: int = 0
    pages_failed: int = 0
    network_fetches: int = 0
    cache_hits: int = 0
    robots_fetches: int = 0
    robots_cache_hits: int = 0
    robots_decisions: list[dict[str, object]] = field(default_factory=list)
    request_timeout_seconds: float = 0.0
    minimum_throttle_seconds: float = 0.0
    network_fetch_attempts: int = 0
    measured_inter_network_fetch_seconds: list[float] = field(default_factory=list)
    minimum_measured_inter_network_fetch_seconds: float | None = None
    throttle_floor_observed: bool | None = None
    parsed_records: int = 0
    accepted_records: int = 0
    rejected_records: int = 0
    duplicates: int = 0
    validation_failures: int = 0
    output_artifacts: dict[str, Any] = field(default_factory=dict)
    page_results: list[PageResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["page_results"] = [page.to_dict() for page in self.page_results]
        return result