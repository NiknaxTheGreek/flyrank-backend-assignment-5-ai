from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import BookRecord


def serialize_records(
    records: list[BookRecord],
    errors: list[dict[str, Any]],
    output_dir: Path,
) -> dict[str, object]:
    """Write the required idempotent Assignment 5 JSON artifacts."""

    output_dir.mkdir(parents=True, exist_ok=True)
    books_path = output_dir / "books.json"
    errors_path = output_dir / "errors.json"

    books_path.write_text(
        json.dumps(
            [record.to_dict() for record in records],
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    errors_path.write_text(
        json.dumps(errors, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return {
        "books": str(books_path),
        "errors": str(errors_path),
        "book_records": len(records),
        "error_records": len(errors),
        "books_bytes": books_path.stat().st_size,
        "errors_bytes": errors_path.stat().st_size,
    }
