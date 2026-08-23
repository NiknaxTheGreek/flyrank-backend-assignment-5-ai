# Requirements Audit

| Requirement | Implementation / evidence |
| --- | --- |
| Standalone Python project | `pyproject.toml`, `polite_scraper/`, and `tests/`; runtime dependencies are empty. |
| Books to Scrape, pages 1–3 | `ScraperConfig.page_url()` and the CLI default `[1, 2, 3]`; live checkpoint 1 requests exactly those pages. |
| About 60 real books before validation/deduplication | `CatalogueParser` parses real `article.product_pod` records; `parsed_records` is reported. |
| Fetch → parse → normalize → validate → deduplicate → serialize → report | `PoliteScraper.run()` coordinates the complete sequence. |
| Respect robots.txt | `PoliteFetcher._allowed()` loads and evaluates `robots.txt` before every requested page decision; denial is tested and each live report records its allow/deny decision, policy source, and any robots retrieval error. |
| Identifying custom User-Agent | `ScraperConfig.user_agent` default and `Request` header propagation; tested. |
| Minimum 500 ms delay | Config and fetcher reject lower values; injected-clock test asserts the throttle sleep floor, and live reports record the configured floor plus measured inter-network-fetch intervals. |
| Finite configurable timeouts | `--timeout` / `ScraperConfig.timeout_seconds`; timeout propagation and failure test, with the configured timeout recorded in every live report. |
| Cache successful page fetches | `FileCache` writes only after a successful response; cache and warm-cache tests. |
| Validation | `validate_record()` checks title, price, availability, rating, URL, and source page; invalid-record test. |
| Deduplication | Accepted records are keyed by canonical `product_url`; duplicate count and behavior are tested. |
| Preserve valid results on page failure | Each page is isolated in `PoliteScraper.run()`; partial-failure test and live checkpoint 3. |
| JSON and CSV serialization | `serialize_records()` writes both formats; serialization test and live output directories. |
| Detailed metrics | `RunReport` includes page, fetch, cache, robots decisions, configured timeout/throttle, measured fetch intervals, parse, validation, duplicate, and artifact counters. |
| Automated coverage requested | Tests cover robots denial, User-Agent, throttle, timeout, caching, warm cache, parsing/validation, deduplication, serialization, and partial failure. |
| Three genuine live checkpoints | `tools/live_verification.py` performs live requests and records observed status/results without synthetic success claims. |
| No human-created Assignment 5 implementation inspected | This project uses only the public Books to Scrape site and its own source/test fixtures. |