from __future__ import annotations

from urllib.parse import urlparse

from .models import BookRecord


def validate_record(record: BookRecord) -> list[str]:
    failures: list[str] = []
    if not record.title.strip():
        failures.append("title is empty")
    if record.price_gbp < 0:
        failures.append("price_gbp must be non-negative")
    if not record.availability.strip():
        failures.append("availability is empty")
    if record.rating not in range(1, 6):
        failures.append("rating must be an integer from 1 to 5")
    parsed_url = urlparse(record.product_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        failures.append("product_url must be an absolute HTTP(S) URL")
    if record.source_page < 1:
        failures.append("source_page must be at least 1")
    return failures


def validate_records(records: list[BookRecord]) -> tuple[list[BookRecord], int]:
    accepted: list[BookRecord] = []
    failures = 0
    for record in records:
        errors = validate_record(record)
        if errors:
            failures += len(errors)
        else:
            accepted.append(record)
    return accepted, failures