from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import DEFAULT_BASE_URL, DEFAULT_USER_AGENT, ScraperConfig
from .pipeline import PoliteScraper


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Politely scrape exactly the first three Books to Scrape catalogue "
            "pages and visit every discovered book detail page."
        ),
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--min-delay", type=float, default=0.5)
    parser.add_argument("--cache-dir", type=Path, default=Path("cache"))
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--run-label", default="cli-run")
    parser.add_argument(
        "--extra-detail-url",
        action="append",
        default=[],
        help="Optional controlled failure URL; real discovered books are never replaced.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = ScraperConfig(
        base_url=args.base_url,
        user_agent=args.user_agent,
        timeout_seconds=args.timeout,
        min_delay_seconds=args.min_delay,
        cache_dir=args.cache_dir,
        output_dir=args.output_dir,
    )
    report = PoliteScraper(config).run(
        run_label=args.run_label,
        extra_detail_urls=args.extra_detail_url,
    )
    print(json.dumps(report.to_dict(), indent=2))
    failed = (
        report.catalogue_pages_failed
        or report.detail_pages_failed
        or report.invalid_records
    )
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
