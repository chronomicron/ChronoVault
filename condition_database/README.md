# condition_database

Runs between Indexer and Importer. For every file still sitting at status `'located'` in `located_files.db`, this:

1. Computes a SHA-256 hash of its contents.
2. Runs it through `analyze_date()` to get a date, confidence, and reasoning — the same call Importer makes, just earlier, so Importer never has to recompute it.
3. Writes both back onto the row.

Once every file has been hashed, it groups files by identical hash and marks duplicates: the first file in each group stays `'located'` (so Importer will copy it normally); every other file in that group is marked `'duplicate'` — skipped from import, but never deleted or hidden. Nothing about *which* copy is "correct" is decided beyond that default pick; a person can review and override it later (see `ROADMAP.md`'s note on duplicate-group review, not yet built).

## Why This Exists

Duplicate Finder already catches duplicates, but only *after* they've been copied into the archive — wasted disk space and wasted copy time for something that could have been caught up front. This closes that gap, and does the same for date determination: instead of only finding out a file's confidence at the moment Importer copies it, you can see the whole picture — every file's date, confidence, and duplicate status — before anything is actually moved.

## File-Type Independence

This is deliberately type-agnostic. Hashing works identically for any file — a JPEG, an MP3, a PDF, a Word document. Date determination already gracefully falls back to the filesystem date for any type `analyze_date` doesn't have a smart signal for yet, so pointing this at a folder of documents or audio files works today; it's just not as confident about the date as it is for JPEG/TIFF until `audio_tools`/a future `document_tools` exist. Confirmed directly: a plain `.txt` file processes with zero errors, correct hash, correct (filesystem-fallback) date.

## Usage

```
python3 condition_database/condition_database.py condition_database/config.json
```

**config.json:**

| Option | Default | Description |
|---|:---:|---|
| `database_path` | *(required)* | Path to `located_files.db`. |
| `output_report_path` | `condition_report.json` | Where to write the JSON summary report. |
| `mismatch_threshold_days` | `1` | Passed through to `analyze_date`. |
| `try_ocr` | `false` | Passed through to `analyze_date` — whether to attempt (slow) OCR corner-stamp scanning for files with weak or no other evidence. |

## New `located_files.db` Columns

Added automatically via the same `ALTER TABLE`-if-missing pattern used everywhere else in the project: `confidence`, `date_reason`, `date_source`, `date_taken`, and `file_hash`.

`file_hash` is ensured here directly, the same way as the others — it does **not** depend on Duplicate Finder having run first (see "Bug Fixed" below for why that distinction matters).

## Idempotency

Safe to re-run. `confidence IS NULL` is what marks a file as not-yet-conditioned — once a file has been processed, re-running the tool skips it automatically, without needing a separate flag column. Confirmed directly: a second run against an already-conditioned database finds nothing left to do.

## Bug Fixed

Worth keeping on record, same spirit as `audit_archive/README.md`'s own bug log — this one was real and would hit anyone running the tools in their documented order:

**`file_hash` column was read and written throughout this script, but never `ensure_column`'d.** The original assumption — noted in an earlier version of this README — was that `file_hash` would already exist by the time Condition Database runs, "added earlier by Duplicate Finder's source mode." That assumption doesn't hold: in the documented pipeline order (Indexer → Condition Database → Importer → Audit Archive → Duplicate Finder), Duplicate Finder runs *last*. So the very first time Condition Database runs — right after Indexer, exactly as intended — the column has never been created.

What actually happened without the fix: every per-file `row['file_hash']` access was wrapped in a broad `try/except`, so each file silently failed there (printed as `FAILED: ...`, easy to miss in a long run). The final duplicate-detection query, which references `file_hash` directly in raw SQL *outside* that `try/except`, then crashed outright with `sqlite3.OperationalError: no such column: file_hash` — this is the point where it was actually caught, via a real end-to-end run (generate test data → Indexer → Condition Database) rather than by reading the code.

Fixed by adding `ensure_column(conn, 'located_files', 'file_hash', 'TEXT')` alongside the other four `ensure_column` calls, so it's created on first use regardless of what's run before it.

## Known Limitation

Duplicate detection here only compares files *against each other* within `located_files.db` — it doesn't check whether a file's hash already exists in the *archive* (`archive_database.db`), meaning a file that was already imported in a previous session could still get re-copied if indexed again from a different source location. Tracked in `ROADMAP.md` as a real, not-yet-closed gap.
