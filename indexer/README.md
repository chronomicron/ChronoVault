# Indexer

Indexer is the first step in the ChronoVault pipeline. Its only job is to search a folder hierarchy for media files and log what it finds into a database — it does not move, copy, or modify any files on disk.

## What It Does

Given a starting folder and a JSON configuration file, Indexer recursively walks the entire directory tree beneath that folder, checking every file it encounters against a list of file extensions defined in the config. Every matching file is logged into a SQLite database (`located_files.db` by default) along with some basic metadata: its path, extension, size, and creation/modification dates.

Indexer is **accumulative and safe to run repeatedly**:

- It can be run multiple times against different folders (an old HDD, a USB key, a NAS mount, a cloud-synced folder), and every run adds to the same database rather than replacing it.
- If a file path is already in the database, Indexer skips it rather than adding a duplicate entry — so running it twice over the same folder won't create duplicate rows.
- Indexer never deletes, modifies, or touches the original files in any way. It only reads and logs.

Each entry starts with a status of `located`. Later stages of the pipeline (like Importer) update that status as files move through the archive process.

## Usage

Run Indexer from the terminal, from the `ChronoVault/` project root:

```
python indexer/indexer.py indexer/config.json /path/to/search
```

**Arguments:**

1. Path to the JSON config file (tells Indexer what to look for and where to store results)
2. Top-level path to search — Indexer will recurse into every subfolder beneath this path

**Example:**

```
python indexer/indexer.py indexer/config.json ~/Pictures
```

This searches everything under `~/Pictures`, recursively, and logs any matching files into the database specified in `config.json`.

You can run Indexer again with a different path to add more locations to the same inventory:

```
python indexer/indexer.py indexer/config.json /media/usb-drive
python indexer/indexer.py indexer/config.json /mnt/nas/old-backups
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
        "arw",
        "thm"
    ]
}
```

- **`database_path`** — where the database lives. Paths are resolved relative to the directory you run the command *from*, not relative to `config.json`'s location. Since the convention is to always run commands from the `ChronoVault/` root, a plain filename like `"located_files.db"` will land at the project root.
- **`extensions`** — the list of file extensions Indexer should look for. Not case-sensitive, and the leading dot is optional (`"jpg"` and `".jpg"` are both fine).

Edit this file to change what file types are indexed, or to point Indexer at a different database — no code changes required.

## Database Schema

Indexer creates and maintains a table called `located_files`:

| Column              | Type    | Description                                      |
|---------------------|---------|---------------------------------------------------|
| `id`                | INTEGER | Auto-incrementing primary key                     |
| `file_path`         | TEXT    | Full path to the file (unique — prevents duplicates) |
| `file_extension`    | TEXT    | File extension, e.g. `.jpg`                        |
| `file_size`         | INTEGER | File size in bytes                                 |
| `creation_date`     | TEXT    | File system creation timestamp                     |
| `modification_date` | TEXT    | File system last-modified timestamp                |
| `status`            | TEXT    | Pipeline status — starts as `located`               |

The database is created automatically the first time Indexer runs, if it doesn't already exist.

## Notes

- Indexer only reads file system metadata (path, size, dates) — it does not open or inspect file contents (no EXIF reading happens at this stage; that's handled later by Importer).
- If Indexer encounters a folder it doesn't have permission to read, it will report the error and exit rather than silently skipping it.
