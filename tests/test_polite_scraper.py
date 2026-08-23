from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request

from polite_scraper.config import ScraperConfig
from polite_scraper.fetch import FetchError, FetchResponse, PoliteFetcher, RobotsDeniedError
from polite_scraper.models import BookRecord
from polite_scraper.pipeline import PoliteScraper
from polite_scraper.serialize import serialize_records
from polite_scraper.validate import validate_record


HTML = """
<html><body>
<article class="product_pod">
  <h3><a href="../book/a_1/index.html" title=" A book  "> A book </a></h3>
  <p class="price_color">£12.34</p>
  <p class="star-rating Three"></p>
  <p class="instock availability"> In stock </p>
</article>
</body></html>
"""


class Response:
    def __init__(self, body: str):
        self.body = body

    def read(self) -> bytes:
        return self.body.encode("utf-8")


class PoliteFetcherTests(unittest.TestCase):
    def make_fetcher(self, opener, **kwargs) -> tuple[PoliteFetcher, tempfile.TemporaryDirectory]:
        temp = tempfile.TemporaryDirectory()
        options = {
            "user_agent": "Test-Agent/1.0",
            "timeout_seconds": 3.5,
            "min_delay_seconds": 0.5,
            "cache_dir": Path(temp.name) / "cache",
            "opener": opener,
            "robots_checker": kwargs.get("robots_checker", lambda _url: True),
        }
        if kwargs.get("sleep_fn") is not None:
            options["sleep_fn"] = kwargs["sleep_fn"]
        if kwargs.get("clock_fn") is not None:
            options["clock_fn"] = kwargs["clock_fn"]
        fetcher = PoliteFetcher(
            **options,
        )
        return fetcher, temp

    def test_robots_denial_stops_page_fetch(self) -> None:
        calls: list[Request] = []

        def opener(request: Request, timeout: float) -> Response:
            calls.append(request)
            return Response(HTML)

        fetcher, temp = self.make_fetcher(opener, robots_checker=lambda _url: False)
        self.addCleanup(temp.cleanup)
        with self.assertRaises(RobotsDeniedError):
            fetcher.fetch("https://books.test/index.html")
        self.assertEqual(calls, [])

    def test_identifying_user_agent_is_propagated(self) -> None:
        headers: list[str | None] = []

        def opener(request: Request, timeout: float) -> Response:
            headers.append(request.get_header("User-agent"))
            return Response(HTML)

        fetcher, temp = self.make_fetcher(opener)
        self.addCleanup(temp.cleanup)
        fetcher.fetch("https://books.test/index.html")
        self.assertEqual(headers, ["Test-Agent/1.0"])

    def test_throttle_never_sleeps_less_than_floor(self) -> None:
        now = [0.0]
        sleeps: list[float] = []

        def sleep(seconds: float) -> None:
            sleeps.append(seconds)
            now[0] += seconds

        def opener(request: Request, timeout: float) -> Response:
            return Response(HTML)

        fetcher, temp = self.make_fetcher(
            opener,
            sleep_fn=sleep,
            clock_fn=lambda: now[0],
        )
        self.addCleanup(temp.cleanup)
        fetcher.fetch("https://books.test/page-1.html")
        fetcher.fetch("https://books.test/page-2.html")
        self.assertEqual(len(sleeps), 1)
        self.assertGreaterEqual(sleeps[0], 0.5)
        self.assertEqual(fetcher.network_intervals_seconds, [0.5])

    def test_timeout_is_finite_and_reported(self) -> None:
        seen_timeouts: list[float] = []

        def opener(request: Request, timeout: float) -> Response:
            seen_timeouts.append(timeout)
            raise TimeoutError("socket timeout")

        fetcher, temp = self.make_fetcher(opener)
        self.addCleanup(temp.cleanup)
        with self.assertRaisesRegex(FetchError, "timed out"):
            fetcher.fetch("https://books.test/index.html")
        self.assertEqual(seen_timeouts, [3.5])

    def test_successful_responses_are_cached_and_warm_cache_skips_network(self) -> None:
        calls = [0]

        def opener(request: Request, timeout: float) -> Response:
            calls[0] += 1
            return Response(HTML)

        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        cache_dir = Path(temp.name) / "cache"
        first = PoliteFetcher(
            user_agent="Test-Agent/1.0",
            timeout_seconds=3,
            min_delay_seconds=0.5,
            cache_dir=cache_dir,
            opener=opener,
            robots_checker=lambda _url: True,
        )
        first_result = first.fetch("https://books.test/index.html")
        second_result = first.fetch("https://books.test/index.html")
        second = PoliteFetcher(
            user_agent="Test-Agent/1.0",
            timeout_seconds=3,
            min_delay_seconds=0.5,
            cache_dir=cache_dir,
            opener=opener,
            robots_checker=lambda _url: True,
        )
        warm_result = second.fetch("https://books.test/index.html")
        self.assertFalse(first_result.cache_hit)
        self.assertTrue(second_result.cache_hit)
        self.assertTrue(warm_result.cache_hit)
        self.assertEqual(calls[0], 1)


class PipelineTests(unittest.TestCase):
    def test_validation_rejects_invalid_record(self) -> None:
        invalid = BookRecord("", -1, "", 6, "not-a-url", 0)
        failures = validate_record(invalid)
        self.assertEqual(len(failures), 6)

    def test_parser_reads_real_book_fields_and_normalizes_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = ScraperConfig(
                base_url="https://books.test/",
                cache_dir=Path(directory) / "cache",
                output_dir=Path(directory) / "output",
            )
            fetcher = StaticFetcher({"https://books.test/index.html": HTML})
            report = PoliteScraper(config, fetcher=fetcher).run([1])
            output = json.loads(
                (Path(directory) / "output" / "accepted_books.json").read_text(
                    encoding="utf-8"
                )
            )
        self.assertEqual(report.parsed_records, 1)
        self.assertEqual(report.accepted_records, 1)
        self.assertEqual(output[0]["title"], "A book")
        self.assertEqual(output[0]["price_gbp"], 12.34)
        self.assertEqual(output[0]["rating"], 3)
        self.assertEqual(
            output[0]["product_url"], "https://books.test/book/a_1/index.html"
        )

    def test_deduplication_keeps_first_valid_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = ScraperConfig(
                base_url="https://books.test/",
                cache_dir=Path(directory) / "cache",
                output_dir=Path(directory) / "output",
            )
            duplicate = BookRecord("Same", 5, "In stock", 4, "https://books.test/book/same", 1)
            fetcher = StaticFetcher(
                {
                    "https://books.test/index.html": HTML,
                    "https://books.test/catalogue/page-2.html": HTML,
                }
            )
            parser = lambda _html, page, _base: [duplicate] if page == 2 else [duplicate]
            report = PoliteScraper(config, fetcher=fetcher, parser=parser).run([1, 2])
        self.assertEqual(report.accepted_records, 1)
        self.assertEqual(report.duplicates, 1)

    def test_partial_failure_preserves_valid_results(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = ScraperConfig(
                base_url="https://books.test/",
                cache_dir=Path(directory) / "cache",
                output_dir=Path(directory) / "output",
            )
            fetcher = StaticFetcher(
                {"https://books.test/index.html": HTML},
                failures={"https://books.test/catalogue/page-2.html": FetchError("unavailable")},
            )
            report = PoliteScraper(config, fetcher=fetcher).run([1, 2])
        self.assertEqual(report.pages_succeeded, 1)
        self.assertEqual(report.pages_failed, 1)
        self.assertEqual(report.accepted_records, 1)
        self.assertTrue(report.output_artifacts["json"])
        self.assertEqual(report.request_timeout_seconds, 10.0)
        self.assertEqual(report.minimum_throttle_seconds, 0.5)
        self.assertEqual(
            report.robots_decisions,
            [
                {
                    "page": 1,
                    "url": "https://books.test/index.html",
                    "robots_url": None,
                    "policy_source": "test_fixture",
                    "robots_fetch_error": None,
                    "allowed": True,
                },
                {
                    "page": 2,
                    "url": "https://books.test/catalogue/page-2.html",
                    "robots_url": None,
                    "policy_source": "test_fixture",
                    "robots_fetch_error": None,
                    "allowed": True,
                },
            ],
        )
        self.assertEqual(report.network_fetch_attempts, 2)

    def test_json_and_csv_serialization(self) -> None:
        record = BookRecord("A book", 12.34, "In stock", 3, "https://books.test/book/a", 1)
        with tempfile.TemporaryDirectory() as directory:
            artifacts = serialize_records([record], Path(directory))
            data = json.loads(Path(artifacts["json"]).read_text(encoding="utf-8"))
            with Path(artifacts["csv"]).open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
        self.assertEqual(data[0]["title"], "A book")
        self.assertEqual(rows[0]["product_url"], "https://books.test/book/a")
        self.assertEqual(artifacts["json_records"], 1)
        self.assertEqual(artifacts["csv_records"], 1)


class StaticFetcher:
    def __init__(self, pages: dict[str, str], failures: dict[str, Exception] | None = None):
        self.pages = pages
        self.failures = failures or {}
        self.robots_fetches = 0
        self.robots_cache_hits = 0
        self.robots_decisions: dict[str, bool] = {}
        self.robots_decision_details: dict[str, dict[str, str | bool | None]] = {}
        self.network_fetch_attempts = 0
        self.network_intervals_seconds: list[float] = []

    def fetch(self, url: str) -> FetchResponse:
        if url in self.failures:
            self.robots_decisions[url] = True
            self.robots_decision_details[url] = {
                "robots_url": None,
                "policy_source": "test_fixture",
                "robots_fetch_error": None,
                "allowed": True,
            }
            self.network_fetch_attempts += 1
            raise self.failures[url]
        self.robots_decisions[url] = True
        self.robots_decision_details[url] = {
            "robots_url": None,
            "policy_source": "test_fixture",
            "robots_fetch_error": None,
            "allowed": True,
        }
        self.network_fetch_attempts += 1
        return FetchResponse(
            url,
            self.pages[url],
            cache_hit=False,
            network_fetch=True,
            robots_allowed=True,
        )


if __name__ == "__main__":
    unittest.main()