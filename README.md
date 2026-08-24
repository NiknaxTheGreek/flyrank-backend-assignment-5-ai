# FlyRank Backend Assignment 5 — The Polite Scraper

A deterministic Python scraper for the assignment's designated practice target, [Books to Scrape](https://books.toscrape.com/). It follows the site's actual pagination through **exactly the first three catalogue pages**, discovers **60 unique books**, visits every book detail page, validates the required fields, writes clean JSON, and reports failures without discarding good records.

## Target classification and ethical boundary

Books to Scrape is a public sandbox created for scraping practice, which makes it appropriate for this assignment. The implementation is intentionally scoped to the first three catalogue pages and their 60 discovered detail pages. It identifies itself, uses a finite timeout, checks HTTP status, applies at least 500 ms pacing between real requests, checks `robots.txt`, and caches successful responses during development.

**I will not reuse this code on another site without checking its rules and terms first.**

The live verification observed that `https://books.toscrape.com/robots.txt` returned HTTP 404. That observation is recorded rather than represented as an explicit allow rule; the scraper continues only because Books to Scrape is the assignment's designated practice target.

## Pipeline

```text
classify → fetch catalogue → follow next links → discover/deduplicate URLs
→ fetch detail pages → extract → normalize → validate → store → report
```

The scraper:

- follows the real `next` link from page 1 to page 2 and page 2 to page 3, then stops;
- uses canonical absolute product URLs as record identity;
- visits all discovered book detail pages;
- keeps raw source text while also normalizing the numeric GBP price;
- represents a missing description as `null` rather than inventing content;
- validates output with a Pydantic schema;
- retries a timeout or HTTP 5xx **once**;
- does **not** retry HTTP 403 or 404;
- isolates an individual broken detail page instead of terminating the whole run;
- overwrites run outputs rather than appending duplicates, so rerunning still produces 60 records;
- never commits the scraper cache.

## Required output schema

Each valid book in `output/books.json` contains:

| Field | Meaning |
| --- | --- |
| `title` | Detail-page book title |
| `product_url` | Canonical absolute detail URL and record identity |
| `price_text` | Raw displayed GBP price text |
| `price_gbp` | Normalized numeric GBP price |
| `availability_text` | Raw displayed availability text |
| `rating_text` | Raw closed rating word: One–Five |
| `description` | Detail-page description, or `null` if absent |
| `source_page` | Catalogue page 1–3 where the book was discovered |
| `fetched_at` | ISO-8601 provenance timestamp for the successful detail fetch |

Invalid/unusable records and page failures are written to `output/errors.json` rather than being fabricated into valid records.

## Install and run

Python 3.11+ is required.

```bash
python -m pip install -e .
python -m polite_scraper.cli --cache-dir cache --output-dir output
```

The normal command always uses the required first-three-page scope. Successful output is:

- `output/books.json`
- `output/errors.json`
- `output/run-report.json`

The run report includes start/finish time, duration, catalogue/detail counts, cache/network counts, retries, validation counts, failed pages, robots observations, timeout/throttle configuration, measured pacing, and artifact references.

## Tests

```bash
python -m unittest discover -s tests -v
```

The deterministic suite covers robots denial, identifying User-Agent, finite timeout, the 500 ms throttle floor, successful-response caching, timeout retry, 5xx retry, no retry for 403/404, actual-next-link parsing, detail extraction, nullable description, Pydantic validation, 60-URL traversal, idempotent reruns, invalid-record quarantine, and the isolated broken-URL path.

## Live verification

```bash
python tools/live_verification.py
```

The current GitHub Actions checkpoint (`32701286479`) passed all three live stages on 2026-08-24:

1. **Clean cache:** 3 catalogue pages, 60 discovered books, 60 unique URLs, 60/60 detail pages successful, 60 valid records, 0 invalid records. There were 63 successful target fetches (3 catalogue + 60 detail), and the minimum measured interval was `0.5000810039999948 s` against the required `0.5 s` floor.
2. **Warm cache:** the same 60 records were reproduced with 63 target cache hits and 0 successful target network fetches.
3. **Required failure experiment:** one deliberately nonexistent detail URL returned HTTP 404, was not retried, and was recorded while all 60 genuine books remained valid.

The CI job also ran **16 deterministic tests successfully**. Current observed values are in [`verification/observed_checkpoints.json`](verification/observed_checkpoints.json), and [`verification/sample-book.json`](verification/sample-book.json) contains one real output record. See [`VERIFICATION_EVIDENCE.md`](VERIFICATION_EVIDENCE.md) for the acceptance summary.

## Controlled broken-URL experiment

The verification harness uses this nonexistent URL only after discovering all 60 genuine books:

```text
https://books.toscrape.com/catalogue/definitely-missing-flyrank-book/index.html
```

The expected result is **60 valid real records plus one recorded failed page**. The 404 is deliberately not retried.

## Why browser automation is unnecessary

Books to Scrape serves the catalogue, pagination links, and product fields directly in static HTML. A headless browser would add startup cost and complexity without exposing data that is otherwise unavailable, so ordinary HTTP requests and HTML parsing are the smaller and more appropriate solution.

## Limitations

- The parser intentionally targets the known Books to Scrape HTML structure; it is not a generic web crawler.
- The cache stores successful HTML responses locally and therefore can become stale until it is cleared.
- The site currently returns 404 for `robots.txt`; that fact is logged as an unavailable policy rather than silently rewritten as a successful robots response.
- Network availability can make the live verification fail even when deterministic tests still pass; such a failure must be reported rather than hidden.

## Evidence and requirement mapping

- [`REQUIREMENTS_AUDIT.md`](REQUIREMENTS_AUDIT.md) maps the recovered S3 requirements to code and current evidence.
- [`VERIFICATION_EVIDENCE.md`](VERIFICATION_EVIDENCE.md) records the successful current live checkpoint.
- `.github/workflows/assignment-5-s3.yml` reruns deterministic and live verification on pull requests and relevant changes.

The AI-generated repository is independent from the separate human-led implementation. The project-required AI Rematch comparison remains a separate later stage after the human version exists.
