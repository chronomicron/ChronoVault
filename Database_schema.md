# ChronoVault Database Schema

ChronoVault uses two independent SQLite databases:

- `located_files.db` is the disposable source inventory. Indexer creates its base tables; Classify Media, Condition Database, Duplicate Finder, and Importer enrich or update its rows.
- `archive_database.db` lives inside the archive root and is the persistent record of files Importer copied. Importer creates its base table; Audit Archive, Duplicate Finder, and `write_data` add or update later fields.

There are no foreign keys between these databases, no schema-version table, and no explicit application-created indexes. SQLite creates implicit indexes for the declared primary keys and `UNIQUE` path constraints. Cross-database relationships such as `located_files.file_path` → `archive_files.source_path` are conventions, not enforced references.

SQLite's dynamic typing also means the declared types below are affinities rather than strict validation. Statuses, source names, confidence ranges, booleans, and date formats have no `CHECK` constraints.

---

# 1. Source Inventory (`located_files.db`)

## 1.1 `located_files`

Indexer creates this table. It uses `INSERT OR IGNORE` keyed by `file_path`, so an already-known path is not refreshed when its size, timestamps, contents, or status change. Paths are stored as strings produced from the supplied search path; they are not forced to be absolute.

### Base columns created by Indexer

| Column | Declared type / constraint | Meaning |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY AUTOINCREMENT` | Inventory row identifier. |
| `file_path` | `TEXT UNIQUE NOT NULL` | Source path. String identity is the deduplication key. |
| `file_extension` | `TEXT` | Lowercase final suffix from `Path.suffix`, including the dot. |
| `file_size` | `INTEGER` | Size observed at index time. |
| `creation_date` | `TEXT` | ISO datetime derived from `st_ctime`; on typical Linux filesystems this is metadata-change time, not true creation time. |
| `modification_date` | `TEXT` | ISO datetime derived from `st_mtime`. |
| `status` | `TEXT DEFAULT 'located'` | Shared pipeline status; values currently used are described below. |

### Columns added later with `ALTER TABLE`

| Column | Declared type | Added/written by | Meaning |
|---|---|---|---|
| `media_score` | `INTEGER` | Classify Media | Personal-media likelihood score, normally 0–100. |
| `media_category` | `TEXT` | Classify Media | `certain_yes`, `likely_yes`, `unknown`, `likely_not`, or `certain_not`. `NULL` is the normal “not classified yet” marker. |
| `media_reason` | `TEXT` | Classify Media | Human-readable classification evidence. |
| `media_excluded` | `INTEGER DEFAULT 0` | Classify Media | `1` when Classify Media itself set the row to `excluded`; used by forced reclassification to distinguish its own exclusions. Importer does not honor this ownership distinction. |
| `confidence` | `INTEGER` | Condition Database | Date-analysis confidence. `NULL` is used as the “not conditioned yet” marker. |
| `date_reason` | `TEXT` | Condition Database | Explanation returned by `analyze_date`. |
| `date_source` | `TEXT` | Condition Database | Primary signal source returned by `analyze_date`. |
| `date_taken` | `TEXT` | Condition Database | Chosen datetime serialized with `datetime.isoformat()`, or `NULL`. |
| `file_hash` | `TEXT` | Condition Database or Duplicate Finder source mode | Cached SHA-256 digest. No uniqueness constraint and no size/mtime invalidation metadata. |

Classify Media and Condition Database add their columns only when they run. A newly created Indexer database therefore does not initially contain these fields.

### Current `status` values

| Status | Writers and behavior |
|---|---|
| `located` | Initial Indexer value. Classify Media also sets this for accepted/non-excluded results. Condition Database processes only `located` rows with `confidence IS NULL`; Importer considers `located` eligible. |
| `excluded` | Classify Media uses it for configured excluded categories; Importer uses the same value for its independent size/path/EXIF/thumbnail filters. Importer re-evaluates **all** excluded rows and does not check `media_excluded`, so a classifier exclusion is not currently durable across Importer. |
| `duplicate` | Condition Database assigns this to all but one row in an in-inventory SHA-256 group. Importer does not select these rows. Selection of the retained row has no `ORDER BY` guarantee. |
| `imported` | Importer assigns this after a successful file copy. It updates the source status before inserting the corresponding archive row, so this status does not by itself prove that `archive_files` was safely recorded. |

No database constraint limits `status` to these values. The proposed `candidate` status described later is not implemented.

### Implemented date-source names

Condition Database can persist any primary source currently returned by `analyze_date`:

`exif_gps`, `exif_original`, `exif_digitized`, `tiff_datetime`, `xmp_create_date`, `xmp_modify_date`, `filename_pattern`, `path_folder_pattern`, `ocr_corner_stamp`, `filesystem_fallback`, or `NULL` when no signal exists.

`ocr_corner_stamp` appears only when Condition Database is configured with `try_ocr: true`. Some low-base-confidence sources may be gathered without becoming the stored primary source.

## 1.2 `located_archives`

Indexer creates and owns this table for compressed files and disc images found on source media. It is distinct from `archive_files`: a row here represents an archive container discovered during scanning, not a media file copied into ChronoVault's destination archive.

| Column | Declared type / constraint | Meaning |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY AUTOINCREMENT` | Row identifier. |
| `archive_path` | `TEXT UNIQUE NOT NULL` | Container path, not forced absolute. |
| `archive_type` | `TEXT` | `zip`, `tar`, `targz`, `iso`, or `unknown`. |
| `archive_size` | `INTEGER` | Size observed during the latest row update; can be `NULL` if stat fails. |
| `contents_listed` | `INTEGER DEFAULT 0` | `1` after a successful listing, including a successful listing with no matching members; `0` if not attempted or unsuccessful. |
| `matching_file_count` | `INTEGER` | Number of retained matching names. Listing stops at 500, so this is capped rather than a true total for larger archives. `NULL` when listing was not successful. |
| `matching_files` | `TEXT` | JSON array of retained member names, capped at 500; `NULL` when listing was not successful. |
| `note` | `TEXT` | Missing dependency, unsupported/corrupt archive, or truncation note. A later run with archive listing disabled can clear a previous failure note. |

Archive contents are never extracted by current code. Turning listing on later updates rows only for archive paths encountered during another normal source walk.

---

# 2. Archive Record (`archive_database.db`)

## 2.1 `archive_files`

Importer creates `archive_database.db` under `archive_root` and creates this table. `archive_path` is the only declared unique business key. Paths can be absolute or working-directory-relative depending on Importer's configured `archive_root`.

The table is intended to describe copied archive files, but it is not guaranteed to match disk state: files can be moved/deleted externally, partial copies can remain, and filesystem/database operations are not transactional. Audit Archive exists to reconcile that drift.

### Base columns created by Importer

| Column | Declared type / constraint | Meaning |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY AUTOINCREMENT` | Archive row identifier. |
| `archive_path` | `TEXT UNIQUE NOT NULL` | Destination path chosen by Importer or later updated by `write_data`. |
| `source_path` | `TEXT` | Source path used for the copy. No foreign key to `located_files`. |
| `file_extension` | `TEXT` | Lowercase destination/source suffix including the dot. |
| `file_size` | `INTEGER` | Source size observed immediately before copying. |
| `date_taken` | `TEXT` | Original analyzer choice serialized with `isoformat()`. Manual correction does not overwrite it. |
| `date_source` | `TEXT` | Primary analyzer source used by Importer. Current possible values are listed below. |
| `filesystem_creation_date` | `TEXT` | Analyzer's filesystem fallback/cross-check value serialized with `isoformat()`. |
| `date_uncertain` | `INTEGER DEFAULT 0` | Importer stores `1` when confidence is below 50 and routes the file to its configured review folder. `write_data` sets it to `0` after a correction. It is a flag, not a constraint tying the row to a particular folder name. |
| `date_added` | `TEXT` | `datetime.now().isoformat()` when Importer records the copy. |
| `camera_make` | `TEXT` | EXIF camera manufacturer, if read. |
| `camera_model` | `TEXT` | EXIF camera model, if read. |
| `gps_latitude` | `REAL` | Decimal latitude derived from EXIF GPS coordinates. |
| `gps_longitude` | `REAL` | Decimal longitude derived from EXIF GPS coordinates. |
| `aperture` | `TEXT` | Formatted EXIF aperture such as `f/2.8`. |
| `iso_speed` | `TEXT` | EXIF ISO value converted to text. |
| `focal_length_mm` | `TEXT` | Formatted EXIF focal length such as `50.0mm`. |

### Columns added later with `ALTER TABLE`

| Column | Declared type | Added/written by | Meaning |
|---|---|---|---|
| `confidence` | `INTEGER` | Importer | Date-analysis confidence stored with a new archive row. Importer ensures this column for older databases. |
| `date_reason` | `TEXT` | Importer | Analyzer explanation stored with a new archive row. Importer ensures this column for older databases. |
| `file_hash` | `TEXT` | Audit Archive or Duplicate Finder archive mode | Cached SHA-256 digest for documented files. Existing non-`NULL` values are trusted without checking current size or modification time. |
| `user_corrected_date` | `TEXT` | `write_data` | Latest manual correction as an ISO string. Original analyzer fields remain unchanged. |
| `corrected_at` | `TEXT` | `write_data` | Timestamp of the latest manual correction. Earlier correction history is not retained. |

`write_data` ensures both correction columns before it looks up the requested row, so even an unsuccessful request for an unknown ID can migrate the schema.

### Archive `date_source` values

Importer calls `analyze_date` again rather than consuming Condition Database's stored fields. Because Importer does not enable OCR, values it can currently store are:

`exif_gps`, `exif_original`, `exif_digitized`, `tiff_datetime`, `xmp_create_date`, `xmp_modify_date`, `filename_pattern`, `path_folder_pattern`, `filesystem_fallback`, or `NULL` if no signal is available.

In normal Importer processing an accessible source file supplies a filesystem signal, so `NULL` is unusual. `xmp_modify_date` is gathered but normally cannot become primary while a filesystem timestamp is available because its base confidence is lower.

### Field ownership and ordering concerns

- Importer copies the file, marks the source row `imported`, then inserts the archive row with `INSERT OR IGNORE`. A failure or ignored uniqueness conflict can leave disk/source state without a newly recorded archive row.
- Importer recomputes date evidence and does not read Condition Database's stored `date_taken`, `date_source`, `confidence`, or `date_reason`.
- Audit Archive and Duplicate Finder may cache hashes but do not invalidate them after in-place file changes.
- `write_data` moves the file before updating `archive_path`; a later SQL failure can leave the database pointing to the old location.
- Audit Archive treats `user_corrected_date` as authoritative over `date_taken` when checking recognized date folders.
- `retrieve_data` and `write_data` resolve stored relative paths using the process working directory, which can differ from the directory used by Importer.

---

# 3. Migration Model and Compatibility Risks

ChronoVault uses decentralized, tool-owned migrations: each tool checks `PRAGMA table_info(...)` and adds only the columns it needs. There is no central migration sequence, schema version, transaction covering all migrations, or validation of existing column types/defaults.

Consequences:

- Tools assume their base table already exists; pointing them at a new/nonexistent database path can create an empty SQLite file and then fail on the missing table.
- Older databases are upgraded only when the relevant tool runs.
- A tool can successfully add its own columns while other later-required columns remain absent.
- `SELECT *` consumers expose whichever columns happen to exist and may fail when they assume a column introduced by another tool is present.
- No constraints enforce score ranges, boolean values, status/category vocabularies, ISO date strings, hash format, or consistency between flags and paths.

These are current implementation characteristics, not a proposed migration design. Central schema versioning and integrity checks are roadmap work.

---

# 4. Future Schema — Labels (Not Implemented)

The following remains a design proposal. No current tool creates or reads these tables.

## Proposed `labels`

| Column | Proposed type / constraint | Meaning |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY AUTOINCREMENT` | Label identifier. |
| `label_name` | `TEXT UNIQUE` | Label text such as `Japan`, `beach`, or a person's name. |
| `category` | `TEXT` | Optional class such as `person`, `place`, or `thing`. |

## Proposed `file_labels`

| Column | Proposed type | Meaning |
|---|---|---|
| `file_id` | `INTEGER` | Intended reference to `archive_files.id`. |
| `label_id` | `INTEGER` | Intended reference to `labels.id`. |
| `source` | `TEXT` | Intended provenance such as `ai` or `user`. |

The proposal still needs decisions about actual foreign-key enforcement, uniqueness of `(file_id, label_id, source)`, deletion behavior, label confidence, and confirmation state.

---

# 5. Future Schema — Candidate Review (Designed, Not Implemented)

The roadmap proposes a `candidate` source status plus a separate `candidate_decision` field (`pending`, `approved`, or `rejected`) for media requiring human approval before import. This is not present in the database or code.

The proposal is intended to serve both archive-member extraction and ambiguous media classification without conflating a human rejection with the existing `excluded` status. Before implementation it needs a single owner for schema migration and explicit interaction rules with `media_excluded`, Condition Database selection, and Importer selection.
