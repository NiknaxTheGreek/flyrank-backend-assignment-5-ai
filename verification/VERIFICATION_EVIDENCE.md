# Assignment 5 Verification Evidence

Current authoritative checkpoint: GitHub Actions run `32701286479`.

## Results

- Deterministic contract tests: **16 passed**.
- Live verification: **PASS**.
- Target: `https://books.toscrape.com/`.
- User-Agent: `FlyRank-PoliteScraper/1.0 (+https://github.com/NiknaxTheGreek/flyrank-backend-assignment-5-ai)`.
- Evidence artifact: `assignment-5-s3-evidence` (ID `9510604846`).

### Clean run

- first three catalogue pages followed through their actual `next` links;
- discovered books: **60**;
- unique canonical URLs: **60**;
- detail pages: **60 attempted / 60 succeeded / 0 failed**;
- valid records: **60**;
- invalid records: **0**;
- target network fetches: **63**;
- minimum measured interval: **0.5000810039999948 s** against a **0.5 s** floor;
- generated files: `books.json`, `errors.json`, `run-report.json`.

### Warm-cache rerun

- valid records: **60**;
- cache hits: **63**;
- target network fetches: **0**;
- same unique-record count: **60**.

### Broken URL experiment

One deliberately nonexistent detail URL was appended after the 60 genuine discovered books.

- detail pages: **61 attempted / 60 succeeded / 1 failed**;
- valid real records retained: **60**;
- failure: **HTTP 404**;
- retries for the 404: **0**;
- failure recorded while the run continued.

The full observed values are committed in [`observed_checkpoints.json`](observed_checkpoints.json). A real output sample is committed in [`sample-book.json`](sample-book.json).

`robots.txt` returned HTTP 404 during the live checkpoint; the scraper recorded that retrieval result and did not pretend an allow rule had been received. The target was still treated as the designated practice site under the assignment's explicit scope.
