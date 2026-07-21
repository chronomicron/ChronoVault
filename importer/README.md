# Importer

Importer is the second step in the ChronoVault pipeline. It reads the inventory built by Indexer, copies matching files into a dated archive, and keeps a record of what it archived. It never touches or modifies the original source files — only reads and copies them.

## What It Does

Importer connects to the database Indexer created (`located_files.db` by default) and looks for entries that are still eligible to be processed. For each eligible file, it:

1. Checks the file against any configured filters (size limits, EXIF requirement, excluded paths, thumbnail exclusion). Files that fail a filter are marked `excluded` and skipped.
2. Determines the file's date, using the best information available, in this priority order:
   - EXIF `DateTimeOriginal` (when the photo was actually taken)
   - EXIF `DateTimeDigitized` (when it was digitized/scanned)
   - File system creation date, as a last resort
3. Copies the file into the archive, organized as `archive/YYYY/MM/DD/filename.ext`.
4. Logs the copied file into a second database, `archive_database.db`, which lives inside the archive folder itself.
5. Updates the original entry's status to `imported`.

Large files (20MB and up) are copied in chunks with a live progress readout, so big video files don't look frozen mid-copy. Smaller files copy instantly.

## Re-running Importer Safely

Importer is safe to run repeatedly:

- Files already marked `imported` are considered done and are never re-processed or re-copied.
- Files marked `excluded` **are re-evaluated on every run**. This matters because filters can change — if you loosen a filter (e.g. turn off `require_exif`), previously excluded files get a fresh chance to pass and be imported, without needing to re-run Indexer.
- If a source file no longer exists (deleted or moved since it was indexed), Importer reports it as missing and moves on without failing the whole run.
- If Importer is interrupted partway through (Ctrl+C, crash, closed terminal), just re-run it — already-imported files are skipped automatically.

## Usage

Run Importer from the terminal, from the `ChronoVault/` project root:

```
python importer/importer.py importer/config.json
```

Importer takes a single argument: the path to its config file. Everything else — the database location, the archive location, and all filtering behavior — is controlled through that file.

## Configuration (`config.json`)

```json
{
    "database_path": "located_files.db",
    "archive_root": "archive",
    "extensions_to_copy": [
        "jpg",
        "jpeg",
        "mp4",
        "mov"
    ],
    "min_file_size_bytes": 20480,
    "max_file_size_bytes": 524288000,
    "require_exif": false,
    "exclude_path_contains": [".config", "cache"],
    "exclude_thumbnails": true,
    "thumbnail_extensions": ["thm"]
}
```

| Key                      | Required | Default   | Description |
|---------------------------|----------|-----------|--------------|
| `database_path`            | Yes      | —         | Path to the Indexer database to read from. |
| `archive_root`              | Yes      | —         | Root folder where the dated archive will be built. |
| `extensions_to_copy`        | Yes      | —         | Which indexed file extensions Importer should actually copy. |
| `min_file_size_bytes`       | No       | `0`       | Files smaller than this are excluded (useful for filtering out browser cache thumbnails, icons, etc). |
| `max_file_size_bytes`       | No       | none      | Files larger than this are excluded (useful for filtering out non-camera video files, e.g. downloaded movies). |
| `require_exif`              | No       | `false`   | If `true`, only files with real EXIF metadata are imported — helps exclude web images and screenshots that were never actually photographed. |
| `exclude_path_contains`     | No       | `[]`      | List of substrings — any file whose full path contains one of these is excluded (e.g. `.config`, `Downloads`, `cache`). |
| `exclude_thumbnails`        | No       | `true`    | Excludes camera-generated thumbnail sidecar files (like Canon `.THM` files) from being copied into the archive. |
| `thumbnail_extensions`      | No       | `["thm"]` | Which extensions are treated as thumbnails when `exclude_thumbnails` is on. |

All paths are resolved relative to the directory you run the command from — by convention, that's always the `ChronoVault/` project root.

**Note:** files excluded by a filter are still indexed and still tracked — they're just not copied. Nothing is ever silently lost from the inventory; you can always loosen a filter later and re-run Importer to pick them up.

## Archive Structure

Files are organized chronologically:

```
archive/
├── 2024/
│   ├── 01/
│   │   └── 12/
│   │       └── photo.jpg
│   └── 03/
│       └── 15/
│           └── video.mp4
└── 2026/
    └── 07/
        └── 09/
            └── another_photo.jpg
```

This structure is built automatically as files are copied — dates come from EXIF when available, otherwise from file system metadata.

## Archive Database (`archive_database.db`)

Created automatically inside `archive_root` the first time Importer runs. This is a separate database from `located_files.db` — it only tracks what's actually inside the archive, not the full source inventory.

| Column            | Type    | Description                                   |
|--------------------|---------|-------------------------------------------------|
| `id`                | INTEGER | Auto-incrementing primary key                    |
| `archive_path`      | TEXT    | Final path of the file inside the archive (unique) |
| `source_path`       | TEXT    | Original path the file was copied from            |
| `file_extension`    | TEXT    | File extension                                     |
| `file_size`         | INTEGER | File size in bytes                                 |
| `date_taken`        | TEXT    | Date used to place the file in the archive (EXIF or file system) |
| `date_added`        | TEXT    | Timestamp of when Importer copied the file          |

This database will later be extended to hold labels (people, places, things) once the AI-assisted labeling phase is built. A future `audit_database.py` tool will scan the archive folder directly and reconcile this database against anything added or changed outside of Importer's normal flow.

## Requirements

- Python 3
- [Pillow](https://pypi.org/project/Pillow/) — `pip install Pillow` — used for reading EXIF metadata

## Example

```
python importer/importer.py importer/config.json
```

```
Loading configuration from: importer/config.json
Located-files database: located_files.db
Archive root: archive
Extensions to copy: ['jpg', 'jpeg', 'mp4', 'mov']
Filters: min_size=20480 bytes, max_size=524288000, require_exif=False, exclude_path_contains=['.config', 'cache'], exclude_thumbnails=True (['.thm'])
Archive database: archive/archive_database.db
------------------------------------------------------------
Found 119 file(s) to evaluate.
------------------------------------------------------------
[1/119] /home/user/Pictures/IMG_0001.jpg (3.2MB)
    OK -> archive/2026/07/09/IMG_0001.jpg
[2/119] /home/user/Pictures/cache/thumb_0001.jpg (4.1KB)
EXCLUDED: /home/user/Pictures/cache/thumb_0001.jpg (below min size (4.1KB < 20.0KB))
...
------------------------------------------------------------
Copied: 94
Excluded by filter: 12
Failed: 0
Missing (source no longer exists): 1
Total evaluated: 119
```