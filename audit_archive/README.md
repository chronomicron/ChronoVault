# Audit Archive

Audit Archive is a **read-only** reconciliation tool. It compares what's actually sitting in the `archive/` folder on disk against what `archive_database.db` thinks is there, and reports the differences. It never moves, renames, or deletes anything, and it never touches `date_taken`, `archive_path`, or any other data field — the only thing it ever writes is a cached file hash (see **Hashing**, below).

## What It Checks

Three kinds of discrepancy:

1. **Undocumented** — a file exists on disk but has no matching row in `archive_database.db`. Usually means something was copied into the archive by hand, outside of Importer.
2. **Missing** — a row exists in the database but the file it points to is no longer on disk. Usually means something was deleted or moved outside of ChronoVault.
3. **Misplaced** — the file is in *both* places (a "matched" file), but it isn't sitting in the date folder its own recorded `date_taken` says it should be in.

Misplacement is checked two different ways, because the information available differs:

- **Matched files** — compared against their own `date_taken` value already stored in the database (the date Importer originally decided on).
- **Undocumented files** — there's no stored date to compare against, so Audit Archive reads EXIF fresh (falling back to the filesystem date, same priority Importer uses) to work out where the file *should* be, then compares that to where it actually is. This is why an undocumented file can be flagged as misplaced too — it's a separate check from the matched-file one, with its own count in the report (`undocumented_misplaced_count`).

## Hashing

While Audit Archive is already walking every matched file, it also computes and caches a SHA-256 hash for each one into `archive_files.file_hash` — purely so Duplicate Finder doesn't have to re-hash the whole archive itself every time it runs.

A few specifics worth knowing:

- **Only matched files get cached.** Undocumented files have no database row to cache a hash *into*, so their hashes aren't stored here — Duplicate Finder hashes those itself, fresh, each time it runs.
- **Already-cached files are skipped.** If `file_hash` is already set for a row, Audit Archive won't recompute it — the "Newly hashed: X, already cached: Y" line in the output reflects this.
- **Large files show live progress.** Same convention as Importer and Duplicate Finder: files ≥20MB are hashed in 4MB chunks with a `hashing: X / Y (Z%)` progress readout, so a multi-gigabyte video doesn't look frozen.
- **The `file_hash` column is added automatically.** It didn't exist in the original `archive_files` schema — Audit Archive adds it via `ALTER TABLE` the first time it runs, so older archives are upgraded in place, not left broken.
- **This is caching, not "fixing."** Filling in a hash is the one piece of data Audit Archive is allowed to write, specifically because it's inert metadata — it doesn't change what a file *is*, where it sits, or what Importer decided about it. Everything else stays purely reported, never altered.

## Bugs Caught During Development

Worth keeping on record, since both were subtle enough to slip past an initial implementation:

1. **Undocumented misplacement was computed but silently dropped.** An early version worked out whether an undocumented file was in the "wrong" folder for its EXIF/filesystem date, but never actually printed it or counted it anywhere in the summary — the number was calculated and then discarded. Fixed by adding a dedicated "Undocumented files ALSO in the wrong folder" section and an `undocumented_misplaced_count` field, so this class of discrepancy is now visible.
2. **A refactor deleted a function its own code still depended on.** `get_date_from_exif()` got removed during a cleanup pass, but `get_expected_date()` still called it — a `NameError` at runtime. Restored. A reminder that "unused-looking" helper functions are worth double-checking before removing, especially in a file that's been edited many times.

Both were caught by running Audit Archive against real, deliberately-messed-up test data (a renamed file plus several manual copies into other date folders) and checking the reported numbers against what was actually done to the files — not just by reading the code.

## Known Limitation (By Design, For Now)

Misplacement checking only ever compares a file to *its own* recorded date — it has no concept of "this file is identical to another file sitting in a different folder, and they disagree." If the exact same photo or video ends up copied into two different date folders (say, once with solid EXIF landing correctly, and once via a path where only a weaker fallback date was available), Audit Archive will consider *both* placements individually "correct," since each one matches its own stored date.

Catching that requires cross-referencing Duplicate Finder's output against Audit's — which is intentionally deferred to the planned GUI review step (see the root `README.md` roadmap), where a person can look at both copies and decide which date is actually right.

## Usage

```
python3 audit_archive/audit_archive.py audit_archive/config.json
```

**config.json:**

| Option         | Default              | Description                                                          |
|----------------|-----------------------|------------------------------------------------------------------------|
| `archive_root` | *(required)*          | Path to the archive folder to audit.                                  |
| `extensions`   | `[]` (all files)      | Optional list of extensions to restrict the scan to, e.g. `["jpg", "mp4"]`. |
| `output_path`  | `audit_result.json`   | Where to write the JSON report.                                       |

## Output

Prints a summary to the terminal, and writes a full report to `output_path`:

```json
{
    "audit_timestamp": "...",
    "archive_root": "archive",
    "summary": {
        "on_disk": 0,
        "in_database": 0,
        "undocumented_count": 0,
        "missing_count": 0,
        "misplaced_count": 0,
        "undocumented_misplaced_count": 0,
        "in_sync": true
    },
    "undocumented_files": [ /* path, file_size, modified_date, date_source, correctly_placed, +expected/actual_folder if misplaced */ ],
    "missing_files": [ /* the full original database row for each missing file */ ],
    "misplaced_files": [ /* archive_path, expected_relative_path, actual_folder, expected_folder, date_taken */ ]
}
```

`in_sync` is `true` only when all four counts (`undocumented`, `missing`, `misplaced`, `undocumented_misplaced`) are zero.
