# Assignment 5 Verification Evidence

This file records current observed results for the S3-compliant polite scraper. It does not reuse the older catalogue-only verification as acceptance evidence.

## Automated and live gate

GitHub Actions run `32701286479` executed the current scraper on Ubuntu 24.04 with Python 3.13.

- Deterministic contract tests: **PASS — 16 tests**.
- Live Books to Scrape verification: **PASS**.
- Uploaded evidence artifact: `assignment-5-s3-evidence`, artifact ID `9510604846`.
- Live run timestamp recorded by the verifier: `2026-08-24T07:24:20.127110+00:00`.
- User-Agent: `FlyRank-PoliteScraper/1.0 (+https://github.com/NiknaxTheGreek/flyrank-backend-assignment-5-ai)`.

## Clean-cache checkpoint

Observed against the real site:

- catalogue pages followed: `index.html` → `catalogue/page-2.html` → `catalogue/page-3.html`;
- catalogue pages succeeded: **3**;
- books discovered: **60**;
- unique canonical book URLs: **60**;
- detail pages attempted/succeeded/failed: **60 / 60 / 0**;
- valid/invalid records: **60 / 0**;
- successful target network fetches: **63** (3 catalogue + 60 detail pages);
- total network attempts: **64** because `robots.txt` returned HTTP 404 and was recorded separately;
- retry attempts: **0**;
- configured throttle floor: **0.5 s**;
- minimum measured interval between real network starts: **0.5000810039999948 s**;
- throttle-floor observation: **true**;
- duration: **31.887 s**;
- generated files: `books.json`, `errors.json`, `run-report.json`.

The 60 output records contain exactly the required fields plus normalized price:

`title`, `product_url`, `price_text`, `price_gbp`, `availability_text`, `rating_text`, `description`, `source_page`, `fetched_at`.

A real sample record is committed at [`verification/sample-book.json`](verification/sample-book.json).

## Warm-cache checkpoint

The immediate rerun used the same successful-response cache:

- catalogue pages succeeded: **3**;
- unique book URLs: **60**;
- valid records: **60**;
- cache hits: **63**;
- successful target network fetches: **0**;
- total network attempts: **1**, the separate `robots.txt` check, which again returned HTTP 404;
- duration: **0.399 s**.

This proves catalogue and detail-page cache reuse while preserving the same 60-record result.

## Required broken-URL experiment

The verifier then appended one deliberately nonexistent detail URL without replacing any real discovered book:

`https://books.toscrape.com/catalogue/definitely-missing-flyrank-book/index.html`

Observed:

- real valid records retained: **60**;
- detail pages attempted/succeeded/failed: **61 / 60 / 1**;
- failed URL status: **HTTP 404**;
- retry attempts: **0**, confirming 404 is not retried;
- the failure was recorded in `errors.json` / `failed_pages`;
- the run continued and completed normally.

## Retry-policy evidence

The deterministic suite separately verifies:

- timeout → exactly one retry;
- HTTP 5xx → exactly one retry;
- HTTP 403 → no retry;
- HTTP 404 → no retry;
- failed responses are not written as successful cache entries;
- the configured finite timeout and identifying User-Agent are passed to requests.

## Evidence files

- [`verification/observed_checkpoints.json`](verification/observed_checkpoints.json) is the committed current live summary.
- [`verification/sample-book.json`](verification/sample-book.json) is a real detail-page output record from the successful run.
- GitHub Actions artifact `9510604846` retains the full generated run reports and live output for run `32701286479`.

The scraper cache itself is ignored and is not retained as submission material.
