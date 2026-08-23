from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Callable

from .config import ScraperConfig
from .fetch import FetchError, PoliteFetcher
from .models import BookRecord, PageResult, RunReport, utc_now
from .parse import parse_catalogue
from .serialize import serialize_records
from .validate import validate_records


class PoliteScraper:
    """Coordinates fetch → parse → normalize → validate → deduplicate → serialize → report."""

    def __init__(
        self,
        config: ScraperConfig,
        *,
        fetcher: PoliteFetcher | None = None,
        parser: Callable[[str, int, str], list[BookRecord]] | None = None,
    ):
        self.config = config
        self.fetcher = fetcher or PoliteFetcher(
            user_agent=config.user_agent,
            timeout_seconds=config.timeout_seconds,
            min_delay_seconds=config.min_delay_seconds,
            cache_dir=config.cache_dir,
        )
        self.parser = parser or (
            lambda html, page, base_url: parse_catalogue(
                html, page=page, base_url=base_url
            )
        )

    def run(self, pages: Sequence[int], *, run_label: str = "run") -> RunReport:
        report = RunReport(
            run_label=run_label,
            started_at=utc_now(),
            request_timeout_seconds=self.config.timeout_seconds,
            minimum_throttle_seconds=self.config.min_delay_seconds,
        )
        accepted: list[BookRecord] = []
        seen_urls: set[str] = set()
        for page in pages:
            url = self.config.page_url(page)
            report.pages_attempted += 1
            attempts_before = getattr(self.fetcher, "network_fetch_attempts", 0)
            try:
                response = self.fetcher.fetch(url)
                report.cache_hits += int(response.cache_hit)
                report.network_fetches += int(response.network_fetch)
                robots_allowed = response.robots_allowed
                robots_detail = getattr(
                    self.fetcher, "robots_decision_details", {}
                ).get(url, {})
                records = self.parser(response.body, page, self.config.base_url)
                report.parsed_records += len(records)
                valid_records, validation_failures = validate_records(records)
                report.validation_failures += validation_failures
                report.rejected_records += len(records) - len(valid_records)
                unique_records: list[BookRecord] = []
                for record in valid_records:
                    if record.product_url in seen_urls:
                        report.duplicates += 1
                    else:
                        seen_urls.add(record.product_url)
                        unique_records.append(record)
                accepted.extend(unique_records)
                report.pages_succeeded += 1
                report.page_results.append(
                    PageResult(
                        page=page,
                        url=url,
                        succeeded=True,
                        records=len(records),
                        cache_hit=response.cache_hit,
                        network_fetch=response.network_fetch,
                        network_attempted=(
                            getattr(self.fetcher, "network_fetch_attempts", 0)
                            > attempts_before
                        ),
                        robots_allowed=robots_allowed,
                        robots_policy_source=robots_detail.get("policy_source"),
                        robots_fetch_error=robots_detail.get("robots_fetch_error"),
                    )
                )
            except FetchError as exc:
                report.pages_failed += 1
                robots_allowed = getattr(self.fetcher, "robots_decisions", {}).get(url)
                robots_detail = getattr(
                    self.fetcher, "robots_decision_details", {}
                ).get(url, {})
                report.page_results.append(
                    PageResult(
                        page=page,
                        url=url,
                        succeeded=False,
                        network_attempted=(
                            getattr(self.fetcher, "network_fetch_attempts", 0)
                            > attempts_before
                        ),
                        robots_allowed=robots_allowed,
                        robots_policy_source=robots_detail.get("policy_source"),
                        robots_fetch_error=robots_detail.get("robots_fetch_error"),
                        error=str(exc),
                    )
                )
            report.robots_decisions.append(
                {
                    "page": page,
                    "url": url,
                    "allowed": robots_allowed,
                    **robots_detail,
                }
            )
        report.accepted_records = len(accepted)
        report.output_artifacts = serialize_records(accepted, self.config.output_dir)
        report.robots_fetches = self.fetcher.robots_fetches
        report.robots_cache_hits = getattr(self.fetcher, "robots_cache_hits", 0)
        report.network_fetch_attempts = getattr(
            self.fetcher, "network_fetch_attempts", 0
        )
        report.measured_inter_network_fetch_seconds = list(
            getattr(self.fetcher, "network_intervals_seconds", [])
        )
        if report.measured_inter_network_fetch_seconds:
            report.minimum_measured_inter_network_fetch_seconds = min(
                report.measured_inter_network_fetch_seconds
            )
            report.throttle_floor_observed = all(
                interval >= report.minimum_throttle_seconds
                for interval in report.measured_inter_network_fetch_seconds
            )
        report.finished_at = utc_now()
        report_path = Path(self.config.output_dir) / "run_report.json"
        report_path.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
        report.output_artifacts["report"] = str(report_path)
        report_path.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
        return report