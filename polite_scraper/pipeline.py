from __future__ import annotations

import json
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .config import ScraperConfig
from .fetch import FetchError, PoliteFetcher
from .models import BookLink, BookRecord, PageResult, RunReport, utc_now
from .parse import parse_catalogue, parse_detail
from .serialize import serialize_records


class PoliteScraper:
    """Discover 60 books, fetch each detail page, validate, store and report."""

    def __init__(
        self,
        config: ScraperConfig,
        *,
        fetcher: PoliteFetcher | None = None,
    ):
        self.config = config
        self.fetcher = fetcher or PoliteFetcher(
            user_agent=config.user_agent,
            timeout_seconds=config.timeout_seconds,
            min_delay_seconds=config.min_delay_seconds,
            cache_dir=config.cache_dir,
        )

    @staticmethod
    def _error(
        *,
        url: str,
        stage: str,
        message: str,
        source_page: int | None,
    ) -> dict[str, Any]:
        return {
            "url": url,
            "stage": stage,
            "error": message,
            "source_page": source_page,
        }

    def _record_fetch(self, report: RunReport, response) -> None:
        report.cache_hits += int(response.cache_hit)
        report.network_fetches += int(response.network_fetch)

    def run(
        self,
        *,
        run_label: str = "run",
        extra_detail_urls: Sequence[str] = (),
    ) -> RunReport:
        started_clock = time.monotonic()
        report = RunReport(
            run_label=run_label,
            started_at=utc_now(),
            request_timeout_seconds=self.config.timeout_seconds,
            minimum_throttle_seconds=self.config.min_delay_seconds,
        )
        errors: list[dict[str, Any]] = []
        discovered: list[BookLink] = []

        # Stage 1: follow the site's actual next link from page 1 through page 3.
        current_url = self.config.first_catalogue_url
        for source_page in range(1, 4):
            report.catalogue_pages_attempted += 1
            report.catalogue_pages.append(current_url)
            attempts_before = self.fetcher.network_fetch_attempts
            retries_before = self.fetcher.retry_attempts
            try:
                response = self.fetcher.fetch(current_url)
                self._record_fetch(report, response)
                parsed = parse_catalogue(
                    response.body,
                    source_page=source_page,
                    page_url=current_url,
                )
                if source_page < 3 and not parsed.next_url:
                    raise ValueError(
                        f"catalogue page {source_page} did not expose a next link"
                    )
                discovered.extend(parsed.links)
                report.discovered_books += len(parsed.links)
                report.catalogue_pages_succeeded += 1
                report.page_results.append(
                    PageResult(
                        kind="catalogue",
                        url=current_url,
                        source_page=source_page,
                        succeeded=True,
                        records=len(parsed.links),
                        cache_hit=response.cache_hit,
                        network_fetch=response.network_fetch,
                        network_attempted=(
                            self.fetcher.network_fetch_attempts > attempts_before
                        ),
                        retries=self.fetcher.retry_attempts - retries_before,
                    )
                )
                if source_page < 3:
                    current_url = parsed.next_url or current_url
            except (FetchError, ValueError) as exc:
                report.catalogue_pages_failed += 1
                error = self._error(
                    url=current_url,
                    stage="catalogue",
                    message=str(exc),
                    source_page=source_page,
                )
                errors.append(error)
                report.failed_pages.append(error)
                report.page_results.append(
                    PageResult(
                        kind="catalogue",
                        url=current_url,
                        source_page=source_page,
                        succeeded=False,
                        network_attempted=(
                            self.fetcher.network_fetch_attempts > attempts_before
                        ),
                        retries=self.fetcher.retry_attempts - retries_before,
                        error=str(exc),
                    )
                )
                break

        # Canonical product URL is the identity. Keep the first discovery page.
        unique_links: list[BookLink] = []
        seen_urls: set[str] = set()
        for link in discovered:
            if link.product_url in seen_urls:
                report.duplicates += 1
                continue
            seen_urls.add(link.product_url)
            unique_links.append(link)
        report.unique_book_urls = len(unique_links)

        # The verification harness may append one deliberately broken URL after
        # all real discovered books. It is never used to pad or replace records.
        detail_links = list(unique_links)
        detail_links.extend(BookLink(url, 3) for url in extra_detail_urls)

        records: list[BookRecord] = []
        for link in detail_links:
            report.detail_pages_attempted += 1
            attempts_before = self.fetcher.network_fetch_attempts
            retries_before = self.fetcher.retry_attempts
            try:
                response = self.fetcher.fetch(link.product_url)
                self._record_fetch(report, response)
            except FetchError as exc:
                report.detail_pages_failed += 1
                error = self._error(
                    url=link.product_url,
                    stage="fetch_detail",
                    message=str(exc),
                    source_page=link.source_page,
                )
                errors.append(error)
                report.failed_pages.append(error)
                report.page_results.append(
                    PageResult(
                        kind="detail",
                        url=link.product_url,
                        source_page=link.source_page,
                        succeeded=False,
                        network_attempted=(
                            self.fetcher.network_fetch_attempts > attempts_before
                        ),
                        retries=self.fetcher.retry_attempts - retries_before,
                        error=str(exc),
                    )
                )
                continue

            try:
                record = parse_detail(
                    response.body,
                    product_url=link.product_url,
                    source_page=link.source_page,
                    fetched_at=response.fetched_at,
                )
            except (ValidationError, ValueError) as exc:
                report.invalid_records += 1
                error = self._error(
                    url=link.product_url,
                    stage="validate_detail",
                    message=str(exc),
                    source_page=link.source_page,
                )
                errors.append(error)
                report.page_results.append(
                    PageResult(
                        kind="detail",
                        url=link.product_url,
                        source_page=link.source_page,
                        succeeded=False,
                        cache_hit=response.cache_hit,
                        network_fetch=response.network_fetch,
                        network_attempted=(
                            self.fetcher.network_fetch_attempts > attempts_before
                        ),
                        retries=self.fetcher.retry_attempts - retries_before,
                        error=str(exc),
                    )
                )
                continue

            records.append(record)
            report.detail_pages_succeeded += 1
            report.page_results.append(
                PageResult(
                    kind="detail",
                    url=link.product_url,
                    source_page=link.source_page,
                    succeeded=True,
                    records=1,
                    cache_hit=response.cache_hit,
                    network_fetch=response.network_fetch,
                    network_attempted=(
                        self.fetcher.network_fetch_attempts > attempts_before
                    ),
                    retries=self.fetcher.retry_attempts - retries_before,
                )
            )

        # A rerun overwrites deterministic artifacts rather than appending rows.
        report.valid_records = len(records)
        report.output_artifacts = serialize_records(
            records,
            errors,
            self.config.output_dir,
        )

        report.network_fetch_attempts = self.fetcher.network_fetch_attempts
        report.retry_attempts = self.fetcher.retry_attempts
        report.robots_fetches = self.fetcher.robots_fetches
        report.robots_cache_hits = self.fetcher.robots_cache_hits
        report.robots_decisions = [
            {"url": url, **detail}
            for url, detail in self.fetcher.robots_decision_details.items()
        ]
        report.measured_inter_network_fetch_seconds = list(
            self.fetcher.network_intervals_seconds
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
        report.duration_seconds = round(time.monotonic() - started_clock, 3)
        report_path = Path(self.config.output_dir) / "run-report.json"
        report.output_artifacts["run_report"] = str(report_path)
        report_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return report
