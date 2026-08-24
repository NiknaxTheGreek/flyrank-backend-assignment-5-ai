from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class BookLink:
    """A canonical product URL discovered on one of the three catalogue pages."""

    product_url: str
    source_page: int


class BookRecord(BaseModel):
    """Validated Assignment 5 output schema for one book detail page."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    product_url: str
    price_text: str = Field(min_length=1)
    price_gbp: float = Field(ge=0)
    availability_text: str = Field(min_length=1)
    rating_text: Literal["One", "Two", "Three", "Four", "Five"]
    description: str | None = None
    source_page: int = Field(ge=1, le=3)
    fetched_at: str

    @field_validator("title", "price_text", "availability_text")
    @classmethod
    def required_text_must_not_be_blank(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("field must contain non-whitespace characters")
        return cleaned

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None

    @field_validator("product_url")
    @classmethod
    def product_url_must_be_absolute_http(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("product_url must be an absolute HTTP(S) URL")
        return value

    @field_validator("fetched_at")
    @classmethod
    def fetched_at_must_be_iso_datetime(cls, value: str) -> str:
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("fetched_at must be an ISO-8601 datetime") from exc
        return value

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


@dataclass
class PageResult:
    kind: Literal["catalogue", "detail"]
    url: str
    succeeded: bool
    source_page: int | None = None
    records: int = 0
    cache_hit: bool = False
    network_fetch: bool = False
    network_attempted: bool = False
    retries: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RunReport:
    run_label: str
    started_at: str
    finished_at: str = ""
    duration_seconds: float = 0.0
    catalogue_pages_attempted: int = 0
    catalogue_pages_succeeded: int = 0
    catalogue_pages_failed: int = 0
    catalogue_pages: list[str] = field(default_factory=list)
    discovered_books: int = 0
    unique_book_urls: int = 0
    detail_pages_attempted: int = 0
    detail_pages_succeeded: int = 0
    detail_pages_failed: int = 0
    valid_records: int = 0
    invalid_records: int = 0
    duplicates: int = 0
    failed_pages: list[dict[str, Any]] = field(default_factory=list)
    network_fetches: int = 0
    cache_hits: int = 0
    network_fetch_attempts: int = 0
    retry_attempts: int = 0
    robots_fetches: int = 0
    robots_cache_hits: int = 0
    robots_decisions: list[dict[str, Any]] = field(default_factory=list)
    request_timeout_seconds: float = 0.0
    minimum_throttle_seconds: float = 0.0
    measured_inter_network_fetch_seconds: list[float] = field(default_factory=list)
    minimum_measured_inter_network_fetch_seconds: float | None = None
    throttle_floor_observed: bool | None = None
    output_artifacts: dict[str, Any] = field(default_factory=dict)
    page_results: list[PageResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["page_results"] = [page.to_dict() for page in self.page_results]
        return result
