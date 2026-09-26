# Indexer

Indexer is the first step in the ChronoVault pipeline. Its only job is to search a folder hierarchy for media files and log what it finds into a database — it does not move, copy, or modify any files on disk.

## What It Does

Given a starting folder and a JSON configuration file, Indexer recursively walks the entire directory tree beneath that folder, checking every file it encounters against a list of file extensions defined in the config. Every matching file is logged into a SQLite database (`located_files.db` by default) along with its path, extension, size, and filesystem timestamps. Paths are stored exactly as produced from the supplied search path; passing a relative search path can therefore store relative file paths.

Indexer is **accumulative and safe to run repeatedly**:

- It can be run multiple times against different folders (an old HDD, a USB key, a NAS mount, a cloud-synced folder), and every run adds to the same database rather than replacing it.
- If a file path is already in the database, Indexer skips it rather than adding a duplicate row. It does not refresh that row's size, timestamps, status, classification, hash, or date fields if the file later changes in place.
- Indexer never deletes, modifies, or touches the original files in any way. It only reads and logs.

Each entry starts with a status of `located`. Later stages of the pipeline (like Importer) update that status as files move through the archive process.

## Archive Detection (ZIP, TAR, ISO)

During the same walk, Indexer also recognizes compressed/disc-image files — ZIP, TAR (including `.tar.gz`/`.tgz`), and ISO by default — and records their location in a separate table, **unconditionally**. This never opens the archive; it's exactly as cheap as noting a normal file's path and size, so it happens regardless of any other setting.

Whether Indexer goes a step further and actually **looks inside** an archive — listing which files inside it match the same `extensions` you're already searching for, without extracting anything — is controlled by `look_inside_archives` in `config.json` (default `false`).

| `look_inside_archives` | Behavior |
|---|---|
| `false` (default) | Archive locations are recorded. Nothing about their contents is known yet. |
| `true` | Archive locations are recorded, **and** Indexer opens each one (ZIP via `zipfile`, TAR via `tarfile`, ISO via `pycdlib` if installed) just far enough to list which member files match your extensions — no extraction, no files written to disk from inside the archive. |

**Turning this on later backfills existing rows, but still requires the normal source walk.** Flip the flag and run Indexer again over the same search path. The filesystem tree is walked again to rediscover the archive paths; when each previously recorded, not-yet-successfully-listed archive is encountered, its row is updated rather than inserted again. Successfully listed archives are not reopened. Archives in some other source tree are not backfilled unless that tree is scanned again.

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
3. `--allow-archive-source` (optional) — see **Safety Check: Refusing to Index an Existing Archive**, below

**Example:**

```
python3 indexer/indexer.py indexer/config.json ~/Pictures
```

This searches everything under `~/Pictures`, recursively, and logs any matching files into the database specified in `config.json`.

## Safety Check: Refusing to Index an Existing Archive

Before doing anything else — before even opening `located_files.db` — Indexer checks whether the search path itself directly contains `archive_database.db`, the file only Importer ever creates, always at the root of whatever archive it built. If found, Indexer refuses to proceed:

```
Error: 'my_archive' looks like it might already be a ChronoVault archive
(it contains 'archive_database.db', which only Importer ever creates).

Indexing an existing archive and importing it again would re-copy every file
into itself, landing as duplicate '(1)', '(2)' copies -- almost certainly not
what you want.

If you're deliberately migrating or consolidating an existing archive and know
what you're doing, re-run with --allow-archive-source to proceed anyway.
```

**Why this exists:** found via a real, reproducible mistake — pointing both the source and archive fields at the same existing archive. Every downstream tool behaved completely correctly given that input: Indexer found "new" files (they were just already-organized photos), Importer recomputed the same date for each, found its own destination already occupied by itself, and its existing filename-collision handling (`(1)`, `(2)`) did exactly what it's designed to do. Nothing was technically broken — the result was still entirely wrong. This check catches the situation before any of that happens.

**The override**, `--allow-archive-source`, exists for the legitimate case: deliberately migrating or consolidating an archive. It's a one-off flag, not a persistent config setting, since "yes, I really mean to do this" isn't an ongoing preference the way `look_inside_archives` is.

```
python3 indexer/indexer.py indexer/config.json /path/to/old_archive --allow-archive-source
```

**Known, accepted limitation:** this only checks the search path itself, not the whole tree beneath it. An archive nested somewhere deep inside a much larger folder being scanned (rather than being the exact path given) won't be caught. This matches the reported case exactly (pointing directly at an archive) without adding the complexity of scanning ahead of time for a rarer, deeper scenario.

The GUI performs the identical check (reusing this same function, not a separate copy) and shows a confirmation dialog instead of a terminal error — declining defaults to **not** proceeding.

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
| `matching_file_count`   | INTEGER | Number of matching members retained by the listing loop. `NULL` if listing failed/was not attempted; capped at 500 rather than a true total for larger archives. |
| `matching_files`        | TEXT    | JSON list of matching member names/paths, also capped at 500 (see `note`). `NULL` if listing failed or was not attempted. |
| `note`                  | TEXT    | Explains a partial or failed listing — a missing dependency, a truncated list, or the underlying error from a corrupt archive. `NULL` when listing fully succeeded or was never attempted. |

Both tables are created automatically the first time Indexer runs, if they don't already exist. See `Database_schema.md` at the project root for the complete cross-tool schema reference.

## Notes

- Indexer only reads filesystem metadata for ordinary media files; no EXIF/content inspection occurs here. `creation_date` is derived from `st_ctime`, which is metadata-change time rather than birth/creation time on typical Linux filesystems. Archives are the exception: optional listing reads container/filesystem structures but never extracts members.
- The walk collects paths in memory before database storage begins. An `OSError` during the walk is caught: files found before that error are then stored, and Indexer exits with status 1. A hard kill/crash during discovery can still lose the not-yet-stored discovery list. Media inserts commit every 100 attempted paths; archive rows commit one at a time.
- Directory symlinks are not explicitly followed by the implementation's `Path.rglob()` walk.
- Archive extensions take precedence if a filename matches both the media and archive extension sets; that path is recorded only in `located_archives`.
- A failed archive listing is retried on a later listing-enabled run. However, rerunning with `look_inside_archives: false` updates an unsuccessfully listed row with `note = NULL`, clearing the earlier failure explanation. Summary counters also under-report an already-known, not-yet-listed archive when listing is disabled: it is neither `newly_recorded` nor `already_known`.
- Extracting listed archive members for review/import is not built. See `roadmap.md`'s candidate-review notes.
