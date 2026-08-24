# Assignment 5 Requirements Audit

Authoritative source: recovered S3 — **Assignment 5: The Polite Scraper**.

| S3 requirement | Current implementation / evidence | Status |
| --- | --- | --- |
| Books to Scrape practice target | `ScraperConfig` defaults to `https://books.toscrape.com/`; README classifies the target and scope | PASS |
| Inspect `robots.txt` | `PoliteFetcher._allowed()` checks the site's robots endpoint once per fetcher policy cache; live run recorded its actual HTTP 404 result | PASS |
| Ethical boundary documented | README includes the required statement about not reusing the scraper without checking another site's rules/terms | PASS |
| Honest identifying User-Agent | Default points to this actual public repository and is sent on every real request | PASS |
| Finite timeout | Default 10 s; config rejects non-positive values; propagation tested | PASS |
| Check HTTP status | Non-2xx responses become structured fetch failures; 403/404/5xx behavior is tested | PASS |
| Cache successful responses | Filesystem cache stores successful catalogue/detail bodies and provenance timestamp; warm live run had 63 target cache hits | PASS |
| Do not commit scraper cache | Root `cache/`, `output/`, and `verification/runs/` are ignored; previously committed generated run/cache directory was removed from the current tree | PASS |
| At least 500 ms between real requests | Config/fetcher enforce a 0.5 s minimum; live clean run minimum measured interval was 0.5000810039999948 s | PASS |
| Follow actual next link to exactly page 3 | Catalogue parser reads `<li class="next">`; live evidence shows index → page-2 → page-3 and then stops | PASS |
| Convert relative links to absolute URLs | `urljoin` plus fragment removal in `parse_catalogue()` | PASS |
| Discover 60 books / 60 unique URLs | Live clean run: discovered 60, unique 60 | PASS |
| Visit every discovered detail page | Live clean run: 60 attempted, 60 succeeded, 0 failed | PASS |
| Required raw/provenance fields | Pydantic `BookRecord`: `title`, `product_url`, `price_text`, `availability_text`, `rating_text`, `description`, `source_page`, `fetched_at` | PASS |
| Missing description becomes `null` | Detail parser leaves absent description as `None`; deterministic test covers this | PASS |
| Normalize numeric `price_gbp` while retaining raw price | Detail parser retains `price_text` and computes `price_gbp`; real sample committed | PASS |
| Canonical product URL is identity | Pipeline deduplicates discovered records by absolute canonical `product_url` | PASS |
| Pydantic or Zod schema | `BookRecord` is a strict Pydantic model with field validators | PASS |
| Valid records → `output/books.json` | `serialize_records()` writes `books.json`; live output verified | PASS |
| Invalid records → `errors.json` | Parse/validation/fetch failures are written to `errors.json`; invalid fixture is quarantined | PASS |
| Rerun remains 60, not 120 | Serializer overwrites output and canonical identity is deduplicated; deterministic rerun test and warm live run both remain 60 | PASS |
| One page failure does not terminate run | Detail failures are isolated; required fake URL left all 60 real records intact | PASS |
| Retry timeout once | Fetcher permits two total attempts; deterministic test proves exactly one retry | PASS |
| Retry 5xx once | Deterministic 503 test proves exactly one retry | PASS |
| Do not retry 404/403 | Deterministic tests prove one attempt; live fake 404 had retry count 0 | PASS |
| `run-report.json` with timing/fetch/cache/valid/invalid/failures | Pipeline writes the required hyphenated report with start, finish, duration, catalogue/detail, fetch/cache, retry, validation and failed-page data | PASS |
| Required broken-URL experiment | Live verifier appended one nonexistent detail URL: 61 attempted, 60 succeeded, 1 failed, 60 valid real records | PASS |
| Public repo | This repository is public | PASS |
| ≥7 meaningful commits | Existing repository history plus the staged S3 repair commits exceeds seven meaningful commits; history was not rewritten or fabricated | PASS |
| README target/install/schema/politeness/run report/limitation/ethical note/browser rationale | Current README contains all listed items and current observed checkpoint values | PASS |
| Reproducible run | `pip install -e .` then the documented CLI runs the fixed three-page scope; GitHub Actions independently executed the same project | PASS |

## Current acceptance evidence

GitHub Actions run `32701286479`:

- **16 deterministic tests passed**;
- clean live run: **3 catalogue pages, 60 discovered, 60 unique, 60 valid detail records**;
- warm run: **63 target cache hits, 0 target network fetches, still 60 records**;
- broken URL run: **60 valid real records + 1 recorded HTTP 404 failure with no retry**;
- uploaded evidence artifact ID: `9510604846`.

See [`VERIFICATION_EVIDENCE.md`](VERIFICATION_EVIDENCE.md), [`verification/observed_checkpoints.json`](verification/observed_checkpoints.json), and [`verification/sample-book.json`](verification/sample-book.json).

## Project-required AI Rematch

The S1/S4 AI Rematch comparison remains pending until the separate human-led Assignment 5 implementation is complete. That pending comparison does not invalidate the technical S3 acceptance of this isolated AI-generated repository, but the overall project assignment should not be marked fully complete until the rematch stage is performed.
