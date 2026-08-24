from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request

from pydantic import ValidationError

from polite_scraper.config import DEFAULT_USER_AGENT, ScraperConfig
from polite_scraper.fetch import FetchError, FetchResponse, PoliteFetcher, RobotsDeniedError
from polite_scraper.models import BookRecord
from polite_scraper.parse import parse_catalogue, parse_detail
from polite_scraper.pipeline import PoliteScraper


FETCHED_AT = "2026-08-24T07:00:00+00:00"
DETAIL_HTML = """
<html><body>
<div class="product_main">
  <h1> A book </h1>
  <p class="price_color">£12.34</p>
  <p class="star-rating Three"></p>
  <p class="instock availability"> In stock (7 available) </p>
</div>
<div id="product_description"><h2>Product Description</h2></div>
<p> A useful description. </p>
</body></html>
"""
DETAIL_HTML_NO_DESCRIPTION = """
<html><body>
<div class="product_main">
  <h1>No description</h1>
  <p class="price_color">£9.99</p>
  <p class="star-rating Five"></p>
  <p class="instock availability">In stock</p>
</div>
</body></html>
"""


class Response:
    def __init__(self, body: str, status: int = 200):
        self.body = body
        self.status = status

    def read(self) -> bytes:
        return self.body.encode("utf-8")


class PoliteFetcherTests(unittest.TestCase):
    def make_fetcher(self, opener, **kwargs):
        temp = tempfile.TemporaryDirectory()
        options = {
            "user_agent": "Test-Agent/1.0",
            "timeout_seconds": 3.5,
            "min_delay_seconds": 0.5,
            "cache_dir": Path(temp.name) / "cache",
            "opener": opener,
            "robots_checker": kwargs.get("robots_checker", lambda _url: True),
        }
        if "sleep_fn" in kwargs:
            options["sleep_fn"] = kwargs["sleep_fn"]
        if "clock_fn" in kwargs:
            options["clock_fn"] = kwargs["clock_fn"]
        return PoliteFetcher(**options), temp

    def test_robots_denial_stops_page_fetch(self) -> None:
        calls: list[Request] = []

        def opener(request: Request, timeout: float) -> Response:
            calls.append(request)
            return Response("ok")

        fetcher, temp = self.make_fetcher(opener, robots_checker=lambda _url: False)
        self.addCleanup(temp.cleanup)
        with self.assertRaises(RobotsDeniedError):
            fetcher.fetch("https://books.test/index.html")
        self.assertEqual(calls, [])

    def test_identifying_user_agent_and_timeout_are_propagated(self) -> None:
        headers: list[str | None] = []
        timeouts: list[float] = []

        def opener(request: Request, timeout: float) -> Response:
            headers.append(request.get_header("User-agent"))
            timeouts.append(timeout)
            return Response("ok")

        fetcher, temp = self.make_fetcher(opener)
        self.addCleanup(temp.cleanup)
        fetcher.fetch("https://books.test/index.html")
        self.assertEqual(headers, ["Test-Agent/1.0"])
        self.assertEqual(timeouts, [3.5])

    def test_throttle_keeps_network_starts_at_least_half_second_apart(self) -> None:
        now = [0.0]
        sleeps: list[float] = []

        def sleep(seconds: float) -> None:
            sleeps.append(seconds)
            now[0] += seconds

        fetcher, temp = self.make_fetcher(
            lambda _request, _timeout: Response("ok"),
            sleep_fn=sleep,
            clock_fn=lambda: now[0],
        )
        self.addCleanup(temp.cleanup)
        fetcher.fetch("https://books.test/one")
        fetcher.fetch("https://books.test/two")
        self.assertEqual(sleeps, [0.5])
        self.assertEqual(fetcher.network_intervals_seconds, [0.5])

    def test_timeout_is_retried_exactly_once(self) -> None:
        calls = [0]

        def opener(_request: Request, _timeout: float) -> Response:
            calls[0] += 1
            if calls[0] == 1:
                raise TimeoutError("socket timeout")
            return Response("ok")

        fetcher, temp = self.make_fetcher(opener)
        self.addCleanup(temp.cleanup)
        response = fetcher.fetch("https://books.test/retry-timeout")
        self.assertEqual(calls[0], 2)
        self.assertEqual(response.retries, 1)
        self.assertEqual(fetcher.retry_attempts, 1)

    def test_5xx_is_retried_exactly_once(self) -> None:
        calls = [0]

        def opener(request: Request, _timeout: float) -> Response:
            calls[0] += 1
            if calls[0] == 1:
                raise HTTPError(request.full_url, 503, "unavailable", {}, None)
            return Response("ok")

        fetcher, temp = self.make_fetcher(opener)
        self.addCleanup(temp.cleanup)
        response = fetcher.fetch("https://books.test/retry-5xx")
        self.assertEqual(calls[0], 2)
        self.assertEqual(response.retries, 1)

    def test_404_and_403_are_not_retried(self) -> None:
        for status in (403, 404):
            with self.subTest(status=status):
                calls = [0]

                def opener(request: Request, _timeout: float, code=status) -> Response:
                    calls[0] += 1
                    raise HTTPError(request.full_url, code, "blocked", {}, None)

                fetcher, temp = self.make_fetcher(opener)
                self.addCleanup(temp.cleanup)
                with self.assertRaises(FetchError) as raised:
                    fetcher.fetch(f"https://books.test/{status}")
                self.assertEqual(raised.exception.status_code, status)
                self.assertEqual(calls[0], 1)
                self.assertEqual(fetcher.retry_attempts, 0)

    def test_successful_response_cache_prevents_second_network_request(self) -> None:
        calls = [0]

        def opener(_request: Request, _timeout: float) -> Response:
            calls[0] += 1
            return Response("cached body")

        fetcher, temp = self.make_fetcher(opener)
        self.addCleanup(temp.cleanup)
        first = fetcher.fetch("https://books.test/cached")
        second = fetcher.fetch("https://books.test/cached")
        self.assertFalse(first.cache_hit)
        self.assertTrue(second.cache_hit)
        self.assertEqual(first.fetched_at, second.fetched_at)
        self.assertEqual(calls[0], 1)


class ParserTests(unittest.TestCase):
    def test_catalogue_parser_discovers_absolute_url_and_real_next_link(self) -> None:
        html = """
        <article class="product_pod"><h3><a href="book-1/index.html">Book</a></h3></article>
        <li class="next"><a href="page-3.html">next</a></li>
        """
        parsed = parse_catalogue(
            html,
            source_page=2,
            page_url="https://books.test/catalogue/page-2.html",
        )
        self.assertEqual(parsed.links[0].product_url, "https://books.test/catalogue/book-1/index.html")
        self.assertEqual(parsed.links[0].source_page, 2)
        self.assertEqual(parsed.next_url, "https://books.test/catalogue/page-3.html")

    def test_detail_parser_keeps_raw_text_and_normalized_price(self) -> None:
        record = parse_detail(
            DETAIL_HTML,
            product_url="https://books.test/catalogue/book/index.html",
            source_page=1,
            fetched_at=FETCHED_AT,
        )
        self.assertEqual(record.title, "A book")
        self.assertEqual(record.price_text, "£12.34")
        self.assertEqual(record.price_gbp, 12.34)
        self.assertEqual(record.availability_text, "In stock (7 available)")
        self.assertEqual(record.rating_text, "Three")
        self.assertEqual(record.description, "A useful description.")
        self.assertEqual(record.fetched_at, FETCHED_AT)

    def test_missing_description_is_null_not_invented(self) -> None:
        record = parse_detail(
            DETAIL_HTML_NO_DESCRIPTION,
            product_url="https://books.test/catalogue/book/index.html",
            source_page=3,
            fetched_at=FETCHED_AT,
        )
        self.assertIsNone(record.description)

    def test_pydantic_schema_rejects_invalid_rating(self) -> None:
        with self.assertRaises(ValidationError):
            BookRecord(
                title="Book",
                product_url="https://books.test/book",
                price_text="£1.00",
                price_gbp=1.0,
                availability_text="In stock",
                rating_text="Six",
                description=None,
                source_page=1,
                fetched_at=FETCHED_AT,
            )


class StaticFetcher:
    def __init__(self, pages: dict[str, str], failures: dict[str, Exception] | None = None):
        self.pages = pages
        self.failures = failures or {}
        self.robots_fetches = 0
        self.robots_cache_hits = 0
        self.robots_decision_details: dict[str, dict[str, str | bool | None]] = {}
        self.network_fetch_attempts = 0
        self.network_intervals_seconds: list[float] = []
        self.retry_attempts = 0

    def fetch(self, url: str) -> FetchResponse:
        self.network_fetch_attempts += 1
        self.robots_decision_details[url] = {
            "robots_url": "https://books.test/robots.txt",
            "policy_source": "test_fixture",
            "robots_fetch_error": None,
            "allowed": True,
        }
        if url in self.failures:
            raise self.failures[url]
        return FetchResponse(
            url=url,
            body=self.pages[url],
            fetched_at=FETCHED_AT,
            cache_hit=False,
            network_fetch=True,
            robots_allowed=True,
            retries=0,
        )


def catalogue_html(start: int, end: int, next_href: str | None) -> str:
    books = "".join(
        f'<article class="product_pod"><h3><a href="book-{number}/index.html">Book</a></h3></article>'
        for number in range(start, end + 1)
    )
    next_link = f'<li class="next"><a href="{next_href}">next</a></li>' if next_href else ""
    return f"<html><body>{books}{next_link}</body></html>"


def fixture_pages() -> dict[str, str]:
    pages = {
        "https://books.test/index.html": catalogue_html(1, 20, "catalogue/page-2.html"),
        "https://books.test/catalogue/page-2.html": catalogue_html(21, 40, "page-3.html"),
        "https://books.test/catalogue/page-3.html": catalogue_html(41, 60, None),
    }
    for number in range(1, 61):
        pages[f"https://books.test/catalogue/book-{number}/index.html"] = DETAIL_HTML
    return pages


class PipelineTests(unittest.TestCase):
    def make_config(self, directory: str) -> ScraperConfig:
        return ScraperConfig(
            base_url="https://books.test/",
            cache_dir=Path(directory) / "cache",
            output_dir=Path(directory) / "output",
        )

    def test_pipeline_follows_three_pages_and_fetches_sixty_details(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = PoliteScraper(
                self.make_config(directory), fetcher=StaticFetcher(fixture_pages())
            ).run(run_label="fixture")
            output_dir = Path(directory) / "output"
            books = json.loads((output_dir / "books.json").read_text(encoding="utf-8"))
            errors = json.loads((output_dir / "errors.json").read_text(encoding="utf-8"))
            run_report = json.loads((output_dir / "run-report.json").read_text(encoding="utf-8"))

        self.assertEqual(report.catalogue_pages_succeeded, 3)
        self.assertEqual(report.discovered_books, 60)
        self.assertEqual(report.unique_book_urls, 60)
        self.assertEqual(report.detail_pages_attempted, 60)
        self.assertEqual(report.detail_pages_succeeded, 60)
        self.assertEqual(report.valid_records, 60)
        self.assertEqual(report.invalid_records, 0)
        self.assertEqual(len(books), 60)
        self.assertEqual(errors, [])
        self.assertEqual(run_report["valid_records"], 60)
        self.assertEqual(set(books[0]), {
            "title", "product_url", "price_text", "price_gbp", "availability_text",
            "rating_text", "description", "source_page", "fetched_at"
        })

    def test_rerun_overwrites_outputs_instead_of_duplicating_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self.make_config(directory)
            PoliteScraper(config, fetcher=StaticFetcher(fixture_pages())).run(run_label="first")
            PoliteScraper(config, fetcher=StaticFetcher(fixture_pages())).run(run_label="second")
            books = json.loads(
                (Path(directory) / "output" / "books.json").read_text(encoding="utf-8")
            )
        self.assertEqual(len(books), 60)
        self.assertEqual(len({book["product_url"] for book in books}), 60)

    def test_one_broken_detail_url_is_isolated_after_sixty_real_records(self) -> None:
        fake_url = "https://books.test/catalogue/definitely-missing/index.html"
        pages = fixture_pages()
        fetcher = StaticFetcher(
            pages,
            failures={fake_url: FetchError("HTTP 404 for fake URL", status_code=404)},
        )
        with tempfile.TemporaryDirectory() as directory:
            report = PoliteScraper(self.make_config(directory), fetcher=fetcher).run(
                run_label="broken-url",
                extra_detail_urls=[fake_url],
            )
            errors = json.loads(
                (Path(directory) / "output" / "errors.json").read_text(encoding="utf-8")
            )
        self.assertEqual(report.valid_records, 60)
        self.assertEqual(report.detail_pages_failed, 1)
        self.assertEqual(report.detail_pages_attempted, 61)
        self.assertEqual(errors[0]["url"], fake_url)
        self.assertEqual(errors[0]["stage"], "fetch_detail")

    def test_invalid_detail_is_quarantined_without_fabrication(self) -> None:
        pages = fixture_pages()
        bad_url = "https://books.test/catalogue/book-10/index.html"
        pages[bad_url] = "<h1>Broken</h1><p class='price_color'>£1.00</p>"
        with tempfile.TemporaryDirectory() as directory:
            report = PoliteScraper(
                self.make_config(directory), fetcher=StaticFetcher(pages)
            ).run(run_label="invalid")
            errors = json.loads(
                (Path(directory) / "output" / "errors.json").read_text(encoding="utf-8")
            )
        self.assertEqual(report.valid_records, 59)
        self.assertEqual(report.invalid_records, 1)
        self.assertEqual(errors[0]["url"], bad_url)
        self.assertEqual(errors[0]["stage"], "validate_detail")

    def test_default_user_agent_points_to_actual_submission_repo(self) -> None:
        self.assertIn("NiknaxTheGreek/flyrank-backend-assignment-5-ai", DEFAULT_USER_AGENT)


if __name__ == "__main__":
    unittest.main()
