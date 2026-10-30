# condition_database

Runs between Indexer and Importer. For every file still sitting at status `'located'` in `located_files.db`, this:

1. Computes a SHA-256 hash of its contents.
2. Runs it through `analyze_date()` to get a date, confidence, source, and reasoning. Importer currently calls `analyze_date()` again instead of consuming these stored fields, so this is pre-import visibility rather than a computation cache for Importer.
3. Writes both back onto the row.

Before grouping, it checks cached source hashes against the current file size and nanosecond modification time. It rehashes missing, legacy, or stale cache entries, then groups all eligible hashes. Previously assigned `'duplicate'` rows are reconsidered on each run so a changed file cannot remain a duplicate solely because of its old hash. The first row returned by SQLite stays `'located'` and every later row in a repeated-hash group becomes `'duplicate'`. The query has no `ORDER BY`, so this is not a documented oldest/newest or best-evidence choice. Duplicate files are skipped from import but never deleted or hidden. Human duplicate-group review is not yet built (see `roadmap.md`).

## Why This Exists

Duplicate Finder already catches duplicates, but only *after* they've been copied into the archive — wasted disk space and wasted copy time for something that could have been caught up front. This closes that gap, and does the same for date determination: instead of only finding out a file's confidence at the moment Importer copies it, you can see the whole picture — every file's date, confidence, and duplicate status — before anything is actually moved.

## File-Type Independence

This is deliberately type-agnostic. Hashing works identically for a JPEG, MP3, PDF, Word document, or other file. `analyze_date` applies filename and containing-folder patterns to every type, then uses the filesystem timestamp as its weakest fallback; JPEG-family and TIFF files can additionally receive format-specific metadata signals. Audio/video-specific metadata and document metadata are not implemented.

## Processing Priority

Both source-hash refresh and date conditioning use the same deterministic order: image rows first, video rows second, and all other file types third. Images are `.jpg`, `.jpeg`, `.bmp`, `.tif`, `.tiff`, `.png`, `.gif`, `.webp`, `.thm`, `.raw`, `.cr2`, and `.arw`. Videos are `.mp4`, `.mov`, `.avi`, `.mkv`, `.mpeg`, `.mpg`, `.3gp`, `.mts`, and `.m2ts`. Extension matching is case-insensitive and ignores a leading dot. Within each category rows are ordered by inventory `id`, so a stopped run can resume with unfinished images ahead of videos and other files. This changes processing order only; it does not exclude or otherwise change handling for any type.

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
| `try_ocr` | `false` | Passed through to `analyze_date`. When true, OCR is attempted for every supported JPEG-family/TIFF file in this run, even when stronger metadata already exists. |

## New `located_files.db` Columns

Added automatically via repeatable `ALTER TABLE`-if-missing migrations: `confidence`, `date_reason`, `date_source`, `date_taken`, `file_hash`, `hash_file_size`, `hash_mtime_ns`, and `hash_computed_at`. The latter three fields store the size, nanosecond modification time, and UTC timestamp associated with a computed hash. Existing rows and hashes are preserved; old hashes without both fingerprint values are unknown and are rehashed before use.

`file_hash` is ensured here directly, the same way as the others — it does **not** depend on Duplicate Finder having run first (see "Bug Fixed" below for why that distinction matters).

## Idempotency

`confidence IS NULL` remains the not-yet-date-conditioned marker. Successfully date-processed rows are skipped on later runs; missing or failed date analyses remain eligible for retry. Hash freshness is checked independently for every `located` or Condition Database `duplicate` row, including when no date analysis is needed. Fresh hashes are reused; mismatched or unknown snapshots are recomputed.

Duplicate grouping runs on every invocation, including when no unconditioned rows need date analysis. Previously assigned `'duplicate'` rows remain excluded during hash and date work; the atomic regrouping transaction recalculates their status together with current `'located'` rows. Other statuses are not changed. A file that cannot be read stably after bounded retries has its cached hash and fingerprint cleared and is omitted from grouping until a later successful hash.

## Progress and stopping

Condition Database handles `SIGINT` and `SIGTERM` cooperatively. It checks for a stop between inventory rows, during source hashing, after date analysis, and while recalculating duplicate groups. A hash interrupted during reading is discarded and will be retried on the next run. Completed hash snapshots and date results are committed per row so a rerun can reuse them.

Duplicate statuses are recalculated inside one SQLite transaction. If a stop arrives during that update, the transaction is rolled back, leaving previously identified duplicates excluded from Importer. A stop exits with code `2` and emits a final `stopped` event; successful completion exits with code `0`. The GUI's **Stop conditioning** control sends `SIGTERM` and reports the stopped result separately from success and failure.

The tool writes one-line JSON events to stdout with the `CHRONOVAULT_PROGRESS ` prefix. Version 1 progress events have this shape:

```json
{"version":1,"event":"progress","tool":"condition_database","stage":"date_conditioning","completed":12,"total":120,"file_path":"/path/to/file.jpg","result":"conditioned"}
```

Stages are `hash_refresh`, `date_conditioning`, and `duplicate_regrouping`. `completed` and `total` count inventory rows handled in that stage. Hash events may additionally include `file_bytes_completed` and `file_bytes_total` for the file currently being read; the row remains incomplete until its hash is committed. Zero-row stages report `0/0`. Final events use `"event":"status"` with `"status":"completed"` or `"stopped"` and the matching `exit_code` (`0` or `2`). Human-readable terminal output remains available alongside these machine-readable lines.

## Bug Fixed

Worth keeping on record, same spirit as `audit_archive/README.md`'s own bug log — this one was real and would hit anyone running the tools in their documented order:

**`file_hash` column was read and written throughout this script, but never `ensure_column`'d.** The original assumption — noted in an earlier version of this README — was that `file_hash` would already exist by the time Condition Database runs, "added earlier by Duplicate Finder's source mode." That assumption doesn't hold: in the documented pipeline order (Indexer → Condition Database → Importer → Audit Archive → Duplicate Finder), Duplicate Finder runs *last*. So the very first time Condition Database runs — right after Indexer, exactly as intended — the column has never been created.

What actually happened without the fix: every per-file `row['file_hash']` access was wrapped in a broad `try/except`, so each file silently failed there (printed as `FAILED: ...`, easy to miss in a long run). The final duplicate-detection query, which references `file_hash` directly in raw SQL *outside* that `try/except`, then crashed outright with `sqlite3.OperationalError: no such column: file_hash` — this is the point where it was actually caught, via a real end-to-end run (generate test data → Indexer → Condition Database) rather than by reading the code.

Fixed by ensuring `file_hash` at startup regardless of tool order. The current shared `source_inventory_hash.py` migration ensures the hash and freshness columns together, so Condition Database can still run immediately after Indexer.

## Operational Notes and Known Limitation

- Run Indexer first. A nonexistent `database_path` may be created as an empty SQLite file, after which schema alteration fails because `located_files` does not exist.
- Relative database and report paths are resolved from the process working directory. Hash and date results are committed per row; duplicate status changes are applied as one transaction.
- Hashing uses SHA-256 in 4 MiB chunks through the shared `source_inventory_hash.py` helper. It compares current size and `st_mtime_ns` to the stored snapshot and retries a changing file twice after the initial attempt. Metadata-based freshness cannot detect content changes that preserve both size and modification time. Date analysis behavior is unchanged. Pillow is needed for JPEG-family EXIF; OCR additionally needs its optional dependencies described in `analyze_date/image_tools/README.md`.
- The report contains processed/failed counts plus each duplicate hash, retained path, and paths marked duplicate. Individual non-duplicate failures are counted and printed but are not listed in the JSON report.

### Archive cross-check gap

Duplicate detection here only compares files *against each other* within `located_files.db` — it doesn't check whether a file's hash already exists in the *archive* (`archive_database.db`), meaning a file that was already imported in a previous session could still get re-copied if indexed again from a different source location. Tracked in `ROADMAP.md` as a real, not-yet-closed gap.
