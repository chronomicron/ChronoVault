# write_data

`write_data` is the mutating twin of `retrieve_data` — the only module in ChronoVault allowed to move a file out of the review bucket and update its record based on a person's decision. It's kept deliberately separate from `retrieve_data` so that anything only needing to *read* archive data can do so with zero risk of accidentally triggering a write.

## Why It's a Separate Module

Importing `retrieve_data` alone gives a caller no ability whatsoever to change anything — it's pure read access. Importing `write_data` is an explicit opt-in to that ability. A list view or detail panel in a future GUI only ever needs `retrieve_data`; only the specific screen that actually applies a correction needs `write_data` too. This split is intentional, not accidental — the same instinct behind Audit Archive being read-only by design.

Like `retrieve_data`, this module does no "asking" of its own. It only accepts already-decided, structured input (a file id and a `datetime`) and reports back what it did, as a plain dict — no Qt, no HTML, nothing UI-specific anywhere in it. Whatever collects the actual correction from a person (a Qt date picker, a web form) is responsible for that; `write_data` only acts on the answer.

## Usage

```python
from write_data.write_data import apply_date_correction
from datetime import datetime

result = apply_date_correction("archive", file_id=12, corrected_date=datetime(2019, 6, 15))
# {'success': True, 'new_archive_path': 'archive/2019/06/15/photo.jpg', 'error': None}
```

## `apply_date_correction(archive_root, file_id, corrected_date)`

Given a file id and a corrected date, this:

1. Checks the file is actually eligible to be corrected (see **The Uncertainty Guardrail**, below).
2. Confirms the file still exists on disk.
3. Moves it into the normal `archive/YYYY/MM/DD/` folder that `corrected_date` implies, using the same collision-avoidance convention as Importer — a filename that's already taken gets ` (1)`, ` (2)`, etc. appended rather than silently overwritten.
4. Updates the database: `archive_path` to the new location, `user_corrected_date` and `corrected_at` to record the correction, and `date_uncertain` flipped to `0`.

Returns `{'success': bool, 'new_archive_path': str or None, 'error': str or None}` for missing IDs, guardrail rejection, missing media, and move failures. Setup, schema, path-creation, invalid-input, and database-update errors can still raise exceptions.

### What's Deliberately Left Untouched

The original algorithmic evidence — `date_taken`, `date_source`, `confidence`, `date_reason` — is never modified by a correction. It's kept as a permanent record of what `analyze_date` originally concluded, sitting alongside the correction rather than being overwritten by it. If those original fields are ever worth re-examining later (e.g. once new evidence sources like filename or `.THM` parsing exist), they're still there.

## The Uncertainty Guardrail

`apply_date_correction()` will refuse to touch a file unless **either**:

- it is currently marked uncertain (`date_uncertain = 1`), **or**
- it's already been manually corrected once before (`user_corrected_date` is set).

A file the algorithm was already confident about — solid EXIF, filesystem date agreeing — is protected by default. The reasoning: when the computer's own date signals already agree with each other, they're more likely to be correct than an accidental or mistaken correction is to be deliberate. Files with no reliable evidence at all (no EXIF, nothing to cross-check) are exactly the case a manual correction exists for, since a person's own knowledge (a remembered birthday, an event) may be the *only* evidence available at all.

The second condition exists so this guardrail doesn't lock someone out of fixing their *own* earlier correction — only the algorithm's confident output is protected, not a person's prior decision.

## Known Behavior and Limitations

A few implementation details matter when using this mutating API:

- **Only the latest correction is kept.** Correcting an already-corrected file overwrites `user_corrected_date`/`corrected_at` with the new values — there's no history of earlier corrections. Confirmed working (a file can be corrected, then corrected again, cleanly) but by design there's no audit trail of *how many* times or *what* the previous corrected value was.
- **Empty folders aren't cleaned up.** Moving a file out of a date folder can leave that folder empty behind it. This is cosmetic only — Audit Archive and Duplicate Finder only ever look at files, not folder structure, so an empty leftover folder has no functional effect. Not yet addressed.
- **The flag is the guardrail, not the folder path.** The function does not verify that an uncertain file currently lives under `_review_needed/`; it uses the database row's `date_uncertain` value.
- **Path resolution follows the process working directory.** A relative `archive_path` stored by Importer is wrapped in `Path(...)` directly. Calling this API from a different working directory can make an existing file appear missing.
- **Move and database update are not atomic.** The file is moved first, then the row is updated and committed. If the SQL update/commit fails (including a unique-path conflict with a stale row), the file remains at the new location while the database retains the old path.
- **Collision checks inspect disk only.** They do not check whether `archive_database.db` already contains the candidate path. Correcting a file again to the same date also sees its current filename as occupied and renames it with ` (1)`, even though it is the same file.
- **Dates are not range-validated.** Any object providing `strftime()` and `isoformat()` can supply a year/month/day destination, including dates outside `analyze_date`'s plausibility range.
- **Audit compatibility depends on precedence.** Audit Archive currently treats `user_corrected_date` as authoritative over preserved `date_taken`; changing that precedence would make valid corrections appear misplaced.

The module has no CLI or config file. `archive_root` must contain an existing `archive_database.db`. `_ensure_correction_columns()` runs before row lookup, so even a request for a nonexistent ID can migrate the schema.

## Database Columns

Adds two columns to `archive_files`, via `ALTER TABLE` the first time it runs against a database that doesn't already have them (same automatic-migration pattern used everywhere else in the project):

| Column                | Type | Description |
|------------------------|------|--------------|
| `user_corrected_date`  | TEXT | The corrected date, as an ISO string. `NULL` if the file has never been manually corrected. |
| `corrected_at`          | TEXT | Timestamp of when the correction was applied. `NULL` if never corrected. |

See `Database_schema.md` at the project root for the full `archive_files` schema.
