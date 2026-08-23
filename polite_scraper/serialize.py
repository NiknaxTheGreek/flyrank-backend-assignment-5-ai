from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import BookRecord


FIELDS = ["title", "price_gbp", "availability", "rating", "product_url", "source_page"]


def serialize_records(records: list[BookRecord], output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "accepted_books.json"
    csv_path = output_dir / "accepted_books.csv"
    json_path.write_text(
        json.dumps([record.to_dict() for record in records], indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(record.to_dict() for record in records)
    return {
        "json": str(json_path),
        "csv": str(csv_path),
        "json_records": len(records),
        "csv_records": len(records),
        "json_bytes": json_path.stat().st_size,
        "csv_bytes": csv_path.stat().st_size,
    }