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

**Status values:**

| Status     | Meaning                                                                 |
|------------|---------------------------------------------------------------------------|
| `located`  | Found by Indexer, not yet processed by Importer.                          |
| `imported` | Successfully copied into the archive by Importer. Permanently done — never re-processed. |
| `excluded` | Did not pass one of Importer's filters (size, EXIF requirement, excluded path, thumbnail). **Re-evaluated on every Importer run**, since filters can change — not a permanent state. |

**Built by:** Indexer, incrementally, across one or more runs against different source locations. Rows are never deleted by the normal pipeline; only their `status` changes over time as Importer processes them.

---

# 2. Archive Database (`archive_database.db`)

Created and maintained by **Importer**, and lives *inside* the archive folder itself (`archive/archive_database.db`). This database represents ground truth for what is actually in the archive — every row corresponds to a real file sitting on disk under `archive/YYYY/MM/DD/`.

**Table: `archive_files`**

| Column           | Type    | Description                                                              |
|------------------|---------|------------------------------------------------------------------------------|
| `id`             | INTEGER | Auto-incrementing primary key.                                               |
| `archive_path`   | TEXT    | Final path of the file inside the archive. Unique.                          |
| `source_path`    | TEXT    | Original path the file was copied from (for traceability/auditing).         |
| `file_extension` | TEXT    | File extension.                                                              |
| `file_size`      | INTEGER | File size in bytes.                                                         |
| `date_taken`     | TEXT    | The date used to place the file in the archive folder structure (EXIF `DateTimeOriginal`/`DateTimeDigitized`, or file system date as fallback). |
| `date_added`     | TEXT    | Timestamp of when the file was actually copied into the archive.             |

**Built by:** Importer, one row per file, at the moment it's successfully copied. A future `audit_database.py` tool will reconcile this database against the actual contents of the `archive/` folder, adding entries for anything found on disk that isn't yet logged here (e.g. a file manually dropped into the archive outside of Importer).

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

This section is a design placeholder — these tables are not created by any current tool. They'll be implemented when the AI labeling phase of the project begins.
