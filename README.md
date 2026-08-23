# FlyRank Backend Assignment 5 — Polite Scraper

An independent, standard-library-only Python scraper for the public [Books to Scrape](https://books.toscrape.com/) catalogue. The required live scope is catalogue pages **1, 2, and 3**: about 60 book records before validation or deduplication.

## What it does

The pipeline is deliberately explicit:

```text
fetch → parse → normalize → validate → deduplicate → serialize → report
```

- Checks `robots.txt` before a page request.
- Sends an identifying custom `User-Agent`.
- Applies a configurable delay with a hard minimum of 500 ms between network requests.
- Uses a finite timeout (10 seconds by default).
- Caches successful page bodies on disk; failed responses are never cached.
- Parses actual `article.product_pod` book records: title, GBP price, availability, rating, product URL, and source page.
- Preserves accepted records when another requested page fails.
- Writes accepted records to both JSON and CSV, plus a detailed `run_report.json`.

## Run it

From this directory:

```bash
python -m unittest discover -s tests -v
python -m polite_scraper.cli --pages 1 2 3 --cache-dir cache --output-dir output
```

The CLI returns exit code 0 when every requested page succeeds and exit code 2 when at least one page fails. A partial run still writes valid output and its report.

Useful options:

```bash
python -m polite_scraper.cli \
  --pages 1 2 3 \
  --timeout 10 \
  --min-delay 0.5 \
  --cache-dir cache \
  --output-dir output \
  --run-label catalogue-pages-1-3
```

The minimum delay and timeout are validated at startup. Use `python tools/live_verification.py` to run the three documented live checkpoints and regenerate the evidence files.

## Outputs

Each run produces:

- `accepted_books.json`
- `accepted_books.csv`
- `run_report.json`

The report includes requested page results and pages attempted/succeeded/failed, network fetches, cache hits, robots fetches, parsed/accepted/rejected records, duplicates, validation failures, and JSON/CSV/report artifact counts and byte sizes.

## Live verification

`tools/live_verification.py` runs:

1. Clean-cache pages 1–3.
2. An immediate warm-cache rerun of pages 1–3 using the first run's successful page cache.
3. A controlled partial-failure run requesting pages 1, 2, and live page 9999, which is expected to be unavailable while valid records from pages 1 and 2 remain.

The script writes observed JSON/CSV output under `verification/runs/` and generates `verification/observed_checkpoints.json` plus `verification/VERIFICATION_EVIDENCE.md`. It never turns a failed or unrun checkpoint into a success claim.