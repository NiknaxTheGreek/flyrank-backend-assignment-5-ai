from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import DEFAULT_BASE_URL, DEFAULT_USER_AGENT, ScraperConfig
from .pipeline import PoliteScraper


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Polite Books to Scrape catalogue scraper",
    )
    parser.add_argument("--pages", nargs="+", type=int, default=[1, 2, 3])
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--min-delay", type=float, default=0.5)
    parser.add_argument("--cache-dir", type=Path, default=Path("cache"))
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--run-label", default="cli-run")
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
    report = PoliteScraper(config).run(args.pages, run_label=args.run_label)
    print(json.dumps(report.to_dict(), indent=2))
    return 0 if report.pages_failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())