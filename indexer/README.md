# Indexer

Indexer is the first step in the ChronoVault pipeline. Its only job is to search a folder hierarchy for media files and log what it finds into a database — it does not move, copy, or modify any files on disk.

## What It Does

Given a starting folder and a JSON configuration file, Indexer recursively walks the entire directory tree beneath that folder, checking every file it encounters against a list of file extensions defined in the config. Every matching file is logged into a SQLite database (`located_files.db` by default) along with some basic metadata: its path, extension, size, and creation/modification dates.

Indexer is **accumulative and safe to run repeatedly**:

- It can be run multiple times against different folders (an old HDD, a USB key, a NAS mount, a cloud-synced folder), and every run adds to the same database rather than replacing it.
- If a file path is already in the database, Indexer skips it rather than adding a duplicate entry — so running it twice over the same folder won't create duplicate rows.
- Indexer never deletes, modifies, or touches the original files in any way. It only reads and logs.

Each entry starts with a status of `located`. Later stages of the pipeline (like Importer) update that status as files move through the archive process.

## Archive Detection (ZIP, TAR, ISO)

During the same walk, Indexer also recognizes compressed/disc-image files — ZIP, TAR (including `.tar.gz`/`.tgz`), and ISO by default — and records their location in a separate table, **unconditionally**. This never opens the archive; it's exactly as cheap as noting a normal file's path and size, so it happens regardless of any other setting.

Whether Indexer goes a step further and actually **looks inside** an archive — listing which files inside it match the same `extensions` you're already searching for, without extracting anything — is controlled by `look_inside_archives` in `config.json` (default `false`).

| `look_inside_archives` | Behavior |
|---|---|
| `false` (default) | Archive locations are recorded. Nothing about their contents is known yet. |
| `true` | Archive locations are recorded, **and** Indexer opens each one (ZIP via `zipfile`, TAR via `tarfile`, ISO via `pycdlib` if installed) just far enough to list which member files match your extensions — no extraction, no files written to disk from inside the archive. |

**Turning this on later doesn't require a rescan.** If you first index a large or slow source location with `look_inside_archives` off, then decide afterward you do want to look inside the archives it found, just flip the flag and run Indexer again over the same path. Archives already on record (location only, contents never listed) get their contents listed *then* — this is a genuine backfill, not a re-scan of the whole drive. An archive whose contents were already successfully listed on a prior run is never re-opened on a later one, the same "don't redo work already done" principle used for hashing elsewhere in the project.

### Why no extraction, no mounting

- **ZIP** — `zipfile` reads only the central directory (a small index at the end of the file), never the file contents themselves. Fast regardless of the archive's total size.
- **TAR / TAR.GZ** — `tarfile.getmembers()` walks the archive's headers without extracting file contents. For a compressed tar this does mean decompressing enough to walk those headers — an inherent cost of TAR's format (it has no separate index the way ZIP does), not a limitation of this implementation.
- **ISO** — `pycdlib` reads the ISO9660/Joliet filesystem structures directly. No OS-level mount is ever used — mounting typically needs root/sudo on Linux and risks leaving an orphaned loop mount behind if interrupted mid-scan.

### Optional dependency: `pycdlib`

ISO listing needs `pycdlib` (`pip install pycdlib --break-system-packages`). If it isn't installed, ISO files are still detected and their locations recorded — only the "look inside" part is skipped, with a clear note explaining why (visible in the `note` column of `located_archives`, and in `test_env.py`'s output). Nothing crashes or blocks the rest of the run.

### Unsupported archive types

If you add an extension to `archive_extensions` that Indexer doesn't have a built-in lister for (e.g. `.rar`, `.7z`), it's still detected and recorded like any other archive — only content listing is skipped, with a note saying so.

### Corrupt or unreadable archives

A archive that fails to open (corrupted, incomplete, not actually the format its extension claims) has its location recorded regardless — only the listing attempt fails, with the underlying error captured in the `note` column. One bad archive never stops the rest of the run.

## Usage

Run Indexer from the terminal, from the `ChronoVault/` project root:

```
python3 indexer/indexer.py indexer/config.json /path/to/search
```

**Arguments:**

1. Path to the JSON config file (tells Indexer what to look for and where to store results)
2. Top-level path to search — Indexer will recurse into every subfolder beneath this path

**Example:**

```
python3 indexer/indexer.py indexer/config.json ~/Pictures
```

This searches everything under `~/Pictures`, recursively, and logs any matching files into the database specified in `config.json`.

You can run Indexer again with a different path to add more locations to the same inventory:

```
python3 indexer/indexer.py indexer/config.json /media/usb-drive
python3 indexer/indexer.py indexer/config.json /mnt/nas/old-backups
```

Each run adds newly found files to the same database, skipping anything already logged.

## Configuration (`config.json`)

```json
{
    "database_path": "located_files.db",
    "extensions": [
        "jpg",
        "jpeg",
        "mp4",
        "mov",
        "raw",
        "cr2",
        "arw"
    ],
    "archive_extensions": [
        "zip",
        "tar",
        "tar.gz",
        "tgz",
        "iso"
    ],
    "look_inside_archives": false
}
```

| Key                     | Required | Default                                    | Description |
|--------------------------|----------|---------------------------------------------|--------------|
| `database_path`          | Yes      | —                                           | Where the database lives. Paths are resolved relative to the directory you run the command *from*, not relative to `config.json`'s location. Since the convention is to always run commands from the `ChronoVault/` root, a plain filename like `"located_files.db"` will land at the project root. |
| `extensions`             | Yes      | —                                           | The list of file extensions Indexer should look for. Not case-sensitive, and the leading dot is optional (`"jpg"` and `".jpg"` are both fine). |
| `archive_extensions`     | No       | `["zip", "tar", "tar.gz", "tgz", "iso"]`     | Which extensions are detected as archives. Detection itself always happens, regardless of `look_inside_archives`. |
| `look_inside_archives`   | No       | `false`                                     | If `true`, Indexer also opens each detected archive (no extraction) to list which member files inside match `extensions`. |

Edit this file to change what file types are indexed, or to point Indexer at a different database — no code changes required.

## Database Schema

Indexer creates and maintains a table called `located_files`:

| Column              | Type    | Description                                      |
|---------------------|---------|-----------------------------------------------------|
| `id`                | INTEGER | Auto-incrementing primary key                     |
| `file_path`         | TEXT    | Full path to the file (unique — prevents duplicates) |
| `file_extension`    | TEXT    | File extension, e.g. `.jpg`                        |
| `file_size`         | INTEGER | File size in bytes                                 |
| `creation_date`     | TEXT    | File system creation timestamp                     |
| `modification_date` | TEXT    | File system last-modified timestamp                |
| `status`            | TEXT    | Pipeline status — starts as `located`               |
| `file_hash`         | TEXT    | SHA-256 hash of the file's contents. Not set by Indexer — added later, automatically, the first time Condition Database or Duplicate Finder (`source` mode) runs against this database. `NULL` until then. |

Indexer also creates a second table, `located_archives`, for detected compressed/disc-image files — kept deliberately separate from `archive_files` (the table Importer creates inside `archive_database.db`), since those two names mean genuinely different things: one is "an archive file Indexer found on a source drive," the other is "a file already copied into the ChronoVault archive."

| Column                 | Type    | Description |
|-------------------------|---------|--------------|
| `id`                    | INTEGER | Auto-incrementing primary key. |
| `archive_path`          | TEXT    | Full path to the archive (unique). |
| `archive_type`          | TEXT    | `zip`, `tar`, `targz`, `iso`, or `unknown` (an extension in `archive_extensions` with no built-in lister). |
| `archive_size`          | INTEGER | Archive file size in bytes. |
| `contents_listed`       | INTEGER | `1` if contents were successfully listed at some point, `0` otherwise (never attempted, or attempted and failed — e.g. missing `pycdlib`, or a corrupt archive). Drives the backfill behavior described above. |
| `matching_file_count`   | INTEGER | How many members inside matched `extensions`. `NULL` if never listed. |
| `matching_files`        | TEXT    | JSON list of matching member names/paths inside the archive. Capped at 500 entries (see `note` if capped). `NULL` if never listed. |
| `note`                  | TEXT    | Explains a partial or failed listing — a missing dependency, a truncated list, or the underlying error from a corrupt archive. `NULL` when listing fully succeeded or was never attempted. |

Both tables are created automatically the first time Indexer runs, if they don't already exist. See `Database_schema.md` at the project root for the complete cross-tool schema reference.

## Notes

- Indexer only reads file system metadata (path, size, dates) for media files — it does not open or inspect their contents (no EXIF reading happens at this stage; that's handled later by Importer). Archives are the one exception: with `look_inside_archives` on, Indexer does open them, but only far enough to list member names — never to read or extract file contents.
- If Indexer encounters a folder it doesn't have permission to read, it will report the error and exit rather than silently skipping it.
- What happens to archive contents once they're listed — actually extracting matching files so they can be reviewed and imported — is a separate, not-yet-built step. See `roadmap.md`'s candidate-review mechanism notes.
