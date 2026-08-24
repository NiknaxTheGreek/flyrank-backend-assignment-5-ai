from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from polite_scraper.config import DEFAULT_BASE_URL, DEFAULT_USER_AGENT, ScraperConfig
from polite_scraper.pipeline import PoliteScraper


VERIFICATION_ROOT = ROOT / "verification"
BROKEN_URL = (
    "https://books.toscrape.com/catalogue/"
    "definitely-missing-flyrank-book/index.html"
)
REQUIRED_FIELDS = {
    "title",
    "product_url",
    "price_text",
    "price_gbp",
    "availability_text",
    "rating_text",
    "description",
    "source_page",
    "fetched_at",
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def summarize(name: str, report, output_dir: Path, *, expected: str) -> dict[str, object]:
    books = load_json(output_dir / "books.json")
    errors = load_json(output_dir / "errors.json")
    run_report = load_json(output_dir / "run-report.json")
    fields_ok = bool(books) and set(books[0]) == REQUIRED_FIELDS

    common = (
        report.catalogue_pages_succeeded == 3
        and report.catalogue_pages_failed == 0
        and report.discovered_books == 60
        and report.unique_book_urls == 60
        and report.valid_records == 60
        and report.invalid_records == 0
        and len(books) == 60
        and len({book["product_url"] for book in books}) == 60
        and fields_ok
        and Path(report.output_artifacts["books"]).name == "books.json"
        and Path(report.output_artifacts["errors"]).name == "errors.json"
        and Path(report.output_artifacts["run_report"]).name == "run-report.json"
    )

    if expected == "clean":
        passed = (
            common
            and report.detail_pages_attempted == 60
            and report.detail_pages_succeeded == 60
            and report.detail_pages_failed == 0
            and errors == []
            and report.throttle_floor_observed is True
        )
    elif expected == "warm":
        passed = (
            common
            and report.detail_pages_attempted == 60
            and report.detail_pages_succeeded == 60
            and report.detail_pages_failed == 0
            and errors == []
            and report.cache_hits >= 63
            and report.network_fetches == 0
        )
    elif expected == "broken":
        passed = (
            common
            and report.detail_pages_attempted == 61
            and report.detail_pages_succeeded == 60
            and report.detail_pages_failed == 1
            and len(errors) == 1
            and errors[0]["url"] == BROKEN_URL
            and errors[0]["stage"] == "fetch_detail"
            and "HTTP 404" in errors[0]["error"]
        )
    else:
        raise ValueError(expected)

    return {
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "catalogue_pages": report.catalogue_pages,
        "catalogue_pages_succeeded": report.catalogue_pages_succeeded,
        "discovered_books": report.discovered_books,
        "unique_book_urls": report.unique_book_urls,
        "detail_pages_attempted": report.detail_pages_attempted,
        "detail_pages_succeeded": report.detail_pages_succeeded,
        "detail_pages_failed": report.detail_pages_failed,
        "valid_records": report.valid_records,
        "invalid_records": report.invalid_records,
        "cache_hits": report.cache_hits,
        "network_fetches": report.network_fetches,
        "network_fetch_attempts": report.network_fetch_attempts,
        "retry_attempts": report.retry_attempts,
        "minimum_throttle_seconds": report.minimum_throttle_seconds,
        "minimum_measured_inter_network_fetch_seconds": report.minimum_measured_inter_network_fetch_seconds,
        "throttle_floor_observed": report.throttle_floor_observed,
        "failed_pages": report.failed_pages,
        "output_files": sorted(path.name for path in output_dir.iterdir() if path.is_file()),
        "output_field_names": sorted(books[0].keys()) if books else [],
        "run_report_duration_seconds": run_report["duration_seconds"],
    }


def main() -> int:
    runs = VERIFICATION_ROOT / "runs"
    if runs.exists():
        shutil.rmtree(runs)
    shared_cache = runs / "shared-cache"

    clean_output = runs / "clean" / "output"
    clean = PoliteScraper(
        ScraperConfig(
            base_url=DEFAULT_BASE_URL,
            user_agent=DEFAULT_USER_AGENT,
            timeout_seconds=10,
            min_delay_seconds=0.5,
            cache_dir=shared_cache,
            output_dir=clean_output,
        )
    ).run(run_label="clean-first-three-pages")
    clean_summary = summarize("clean", clean, clean_output, expected="clean")

    warm_output = runs / "warm" / "output"
    warm = PoliteScraper(
        ScraperConfig(
            base_url=DEFAULT_BASE_URL,
            user_agent=DEFAULT_USER_AGENT,
            timeout_seconds=10,
            min_delay_seconds=0.5,
            cache_dir=shared_cache,
            output_dir=warm_output,
        )
    ).run(run_label="warm-cache-rerun")
    warm_summary = summarize("warm", warm, warm_output, expected="warm")

    broken_output = runs / "broken" / "output"
    broken = PoliteScraper(
        ScraperConfig(
            base_url=DEFAULT_BASE_URL,
            user_agent=DEFAULT_USER_AGENT,
            timeout_seconds=10,
            min_delay_seconds=0.5,
            cache_dir=shared_cache,
            output_dir=broken_output,
        )
    ).run(
        run_label="sixty-real-plus-one-broken",
        extra_detail_urls=[BROKEN_URL],
    )
    broken_summary = summarize("broken", broken, broken_output, expected="broken")

    evidence = {
        "target": DEFAULT_BASE_URL,
        "user_agent": DEFAULT_USER_AGENT,
        "run_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
        "checkpoints": [clean_summary, warm_summary, broken_summary],
    }
    VERIFICATION_ROOT.mkdir(parents=True, exist_ok=True)
    (VERIFICATION_ROOT / "observed_checkpoints.json").write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    shutil.copy2(clean_output / "run-report.json", VERIFICATION_ROOT / "clean-run-report.json")
    shutil.copy2(broken_output / "run-report.json", VERIFICATION_ROOT / "broken-run-report.json")
    sample = load_json(clean_output / "books.json")[0]
    (VERIFICATION_ROOT / "sample-book.json").write_text(
        json.dumps(sample, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return 0 if all(item["status"] == "PASS" for item in evidence["checkpoints"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
