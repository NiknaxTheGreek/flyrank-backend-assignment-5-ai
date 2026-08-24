from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from .models import BookRecord


def validate_payload(payload: dict[str, Any]) -> tuple[BookRecord | None, list[str]]:
    """Validate an extracted payload without fabricating missing values."""

    try:
        return BookRecord.model_validate(payload), []
    except ValidationError as exc:
        return None, [error["msg"] for error in exc.errors()]


def validate_record(record: BookRecord) -> list[str]:
    """Compatibility helper: a constructed BookRecord has already passed Pydantic."""

    BookRecord.model_validate(record.model_dump())
    return []
