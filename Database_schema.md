# ChronoVault Database Schema

ChronoVault currently uses two separate SQLite databases, one per stage of the pipeline. They are intentionally kept separate: `located_files.db` is a disposable working inventory built by Indexer, while `archive_database.db` is the permanent record of what actually lives in the archive.

---

# 1. Located Files Database (`located_files.db`)

Created and maintained by **Indexer**. This database is the raw inventory of every matching file found across all the source locations you've scanned (old drives, USB keys, cloud folders, etc). It exists purely as working data to drive Importer — it does not represent the final archive.

**Table: `located_files`**

| Column              | Type    | Description                                                        |
|---------------------|---------|----------------------------------------------------------------------|
| `id`                | INTEGER | Auto-incrementing primary key.                                       |
| `file_path`         | TEXT    | Full source path to the file. Unique — prevents duplicate entries when Indexer is re-run over the same location. |
| `file_extension`    | TEXT    | File extension, e.g. `.jpg`, `.mp4`, `.thm`.                         |
| `file_size`         | INTEGER | File size in bytes, as found at index time.                          |
| `creation_date`     | TEXT    | File system creation timestamp.                                      |
| `modification_date` | TEXT    | File system last-modified timestamp.                                 |
| `status`            | TEXT    | Pipeline status. See below.                                          |
| `file_hash`         | TEXT    | SHA-256 hash of the file's contents. `NULL` until Duplicate Finder runs in `source` mode against this file — it isn't computed by Indexer. |

**Status values:**

| Status     | Meaning                                                                 |
|------------|---------------------------------------------------------------------------|
| `located`  | Found by Indexer, not yet processed by Importer.                          |
| `imported` | Successfully copied into the archive by Importer. Permanently done — never re-processed. |
| `excluded` | Did not pass one of Importer's filters (size, EXIF requirement, excluded path, thumbnail). **Re-evaluated on every Importer run**, since filters can change — not a permanent state. |

**Built by:** Indexer, incrementally, across one or more runs against different source locations. Rows are never deleted by the normal pipeline; only their `status` changes over time as Importer processes them. `file_hash` is added later, and only, by Duplicate Finder (`source` mode) — via `ALTER TABLE` the first time it runs, so this column exists even on older databases created before hashing was added.

---

# 2. Archive Database (`archive_database.db`)

Created and maintained by **Importer**, and lives *inside* the archive folder itself (`archive/archive_database.db`). This database represents ground truth for what is actually in the archive — every row corresponds to a real file sitting on disk, either under `archive/YYYY/MM/DD/` or, for files ChronoVault wasn't confident about, under `archive/_review_needed/` (see `date_uncertain` below — there's no separate column marking a file as "in review"; it's implied by that flag plus wherever `archive_path` actually points).

**Table: `archive_files`**

| Column                     | Type    | Description                                                              |
|----------------------------|---------|------------------------------------------------------------------------------|
| `id`                       | INTEGER | Auto-incrementing primary key.                                               |
| `archive_path`             | TEXT    | Final path of the file inside the archive. Unique. Either a `YYYY/MM/DD/` date folder, or `_review_needed/` for low-confidence files. |
| `source_path`              | TEXT    | Original path the file was copied from (for traceability/auditing).         |
| `file_extension`           | TEXT    | File extension.                                                              |
| `file_size`                | INTEGER | File size in bytes.                                                         |
| `date_taken`                | TEXT    | The date `analyze_date` chose for this file. Used to build the archive folder path when confidence is high enough; otherwise the file still records this date, it's just not trusted enough to file by. |
| `date_source`               | TEXT    | Where the chosen date came from: `exif_original`, `exif_digitized`, or `filesystem_fallback`. |
| `filesystem_creation_date`  | TEXT    | The file's filesystem creation date, recorded regardless of whether it was the date actually used — kept for cross-checking. |
| `date_uncertain`            | INTEGER | `0` or `1`. `1` means `analyze_date`'s confidence was below its uncertainty threshold (currently confidence < 50) — these files are routed to `_review_needed/` instead of a date folder. Derived from `confidence`, kept as a simple flag for convenience. |
| `confidence`                | INTEGER | `analyze_date`'s confidence score for the chosen date, 0–100. Added after the date-analysis rework — see `analyze_date/analyze_date.py` for exactly how it's calculated (base score by source, adjusted for agreement/disagreement between signals, capped low for implausible dates). |
| `date_reason`               | TEXT    | Short human-readable explanation from `analyze_date` for why this date and confidence were chosen, e.g. `"EXIF (DateTimeOriginal) -- confirmed by filesystem creation date"`. Useful for a future GUI review screen, and for spot-checking results in the meantime. |
| `date_added`                | TEXT    | Timestamp of when the file was actually copied into the archive.             |
| `camera_make`                | TEXT    | Camera manufacturer, from EXIF, if present.                                 |
| `camera_model`               | TEXT    | Camera model, from EXIF, if present.                                        |
| `gps_latitude`               | REAL    | Decimal-degree latitude, converted from EXIF GPS data, if present.          |
| `gps_longitude`              | REAL    | Decimal-degree longitude, converted from EXIF GPS data, if present.         |
| `aperture`                   | TEXT    | f-stop, from EXIF, if present (e.g. `f/2.8`).                               |
| `iso_speed`                  | TEXT    | ISO speed rating, from EXIF, if present.                                    |
| `focal_length_mm`            | TEXT    | Focal length in mm, from EXIF, if present.                                  |
| `file_hash`                  | TEXT    | SHA-256 hash of the file's contents. `NULL` until Audit Archive runs and caches it for every matched (on-disk + in-database) file — not computed by Importer itself. |

**Built by:** Importer, one row per file, at the moment it's successfully copied — including `confidence`, `date_reason`, and `date_uncertain` from `analyze_date`'s output. `file_hash` is filled in later by Audit Archive, which caches hashes for every file it can match against the database (mainly so Duplicate Finder doesn't need to re-hash them). Both `confidence`/`date_reason` and `file_hash` were added after the table already existed in earlier versions of the archive; all three are added automatically via `ALTER TABLE` the first time the relevant tool runs, so older `archive_database.db` files are upgraded in place rather than needing to be rebuilt.

---

# 3. Future Schema — Labels (Not Yet Implemented)

Once an AI labeling agent (or manual tagging) is introduced, archived media will need to support labels like people, places, and things — e.g. "Japan," "uncle Andre," "vacation." A single file can have several labels, and a single label applies to many files, so this is modeled as a many-to-many relationship using two additional tables inside `archive_database.db`.

**Proposed table: `labels`**

| Column        | Type    | Description                                                    |
|---------------|---------|--------------------------------------------------------------------|
| `id`          | INTEGER | Auto-incrementing primary key.                                     |
| `label_name`  | TEXT    | The label itself, e.g. `"uncle Andre"`, `"Japan"`, `"beach"`. Unique. |
| `category`    | TEXT    | Optional grouping — e.g. `person`, `place`, `thing`.                |

**Proposed table: `file_labels`** (the join table)

| Column       | Type    | Description                                              |
|--------------|---------|--------------------------------------------------------------|
| `file_id`    | INTEGER | References `archive_files.id`.                                |
| `label_id`   | INTEGER | References `labels.id`.                                       |
| `source`     | TEXT    | How the label was applied — e.g. `ai`, `user` — so AI-suggested and user-confirmed labels can be told apart later. |

This design means:

- A photo can carry any number of labels without changing its row in `archive_files`.
- Renaming a label (e.g. correcting a misspelled name) updates one row in `labels`, not every photo that uses it.
- Searching "show me everything labeled Japan" becomes a simple join across `file_labels` and `archive_files`.
- Distinguishing AI-suggested labels from confirmed/manual ones is possible from day one, without a schema change later.

A future AI labeler is expected to follow the same "hand it evidence, get back a scored answer" shape as `analyze_date` — so however many labels or confidence scores it produces per file, they'd land in these two tables without needing `archive_files` itself to change.

This section is a design placeholder — these tables are not created by any current tool. They'll be implemented when the AI labeling phase of the project begins.
