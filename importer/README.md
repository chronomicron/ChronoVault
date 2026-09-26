# Importer

Importer is the copy stage after Indexer, Classify Media, and Condition Database. It reads the source inventory, copies eligible files into a dated archive, records each copy, and updates source-row statuses. It never modifies or deletes original media files.

## What It Does

Importer connects to the database Indexer created (`located_files.db` by default) and selects rows whose status is `located` or `excluded` and whose extension is configured. Rows marked `duplicate` or `imported` are skipped. For each selected file, it:

1. Checks the file against any configured filters (size limits, EXIF requirement, excluded paths, thumbnail exclusion). Files that fail a filter are marked `excluded` and skipped.
2. Reads EXIF and calls `analyze_date` (see `analyze_date/README.md`) to recompute the chosen date, confidence, and explanation. Importer does **not** read the `date_taken`, `date_source`, `confidence`, or `date_reason` values previously stored by Condition Database.
3. Copies the file into the archive:
   - **Confident dates** (`confidence >= 50` with the current analyzer threshold) go into `archive/YYYY/MM/DD/filename.ext`.
   - **Low-confidence dates** go into `archive/_review_needed/filename.ext` instead of a possibly-wrong date folder, so they're easy to find and sort out by hand later.
4. Logs the copied file into a second database, `archive_database.db`, which lives inside the archive folder itself — including the chosen date, its source, the confidence score, and the reasoning string.
5. Updates the original entry's status to `imported`.

Large files (20MB and up) are copied in chunks with a live progress readout, so big video files don't look frozen mid-copy. Smaller files copy instantly.

## Re-running Importer Safely

Importer is safe to run repeatedly:

- Files already marked `imported` are considered done and are never re-processed or re-copied.
- Every row marked `excluded` is re-evaluated on every run. The query does not distinguish Importer's own filter exclusions from `media_excluded = 1` rows excluded by Classify Media. A classifier-excluded row can therefore return to `located`/be imported if it passes Importer's independent filters.
- If a source file no longer exists (deleted or moved since it was indexed), Importer reports it as missing and moves on without failing the whole run.
- If Importer is interrupted, rows already marked `imported` are skipped on the next run. This is not fully transactional across filesystem and database operations; see the failure notes below.

## Usage

Run Importer from the terminal, from the `ChronoVault/` project root:

```
python3 importer/importer.py importer/config.json
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
    "thumbnail_extensions": ["thm"],
    "date_mismatch_threshold_days": 1,
    "review_folder_name": "_review_needed"
}
```

| Key                              | Required | Default            | Description |
|------------------------------------|----------|---------------------|--------------|
| `database_path`                    | Yes      | —                   | Path to the Indexer database to read from. |
| `archive_root`                      | Yes      | —                   | Root folder where the dated archive will be built. |
| `extensions_to_copy`                | Yes      | —                   | Which indexed file extensions Importer should actually copy. |
| `min_file_size_bytes`               | No       | `0`                 | Files smaller than this are excluded (useful for filtering out browser cache thumbnails, icons, etc). |
| `max_file_size_bytes`               | No       | none                | Files larger than this are excluded (useful for filtering out non-camera video files, e.g. downloaded movies). |
| `require_exif`                      | No       | `false`             | If `true`, only files with real EXIF metadata are imported — helps exclude web images and screenshots that were never actually photographed. |
| `exclude_path_contains`             | No       | `[]`                | List of substrings — any file whose full path contains one of these is excluded (e.g. `.config`, `Downloads`, `cache`). |
| `exclude_thumbnails`                | No       | `true`              | Excludes camera-generated thumbnail sidecar files (like Canon `.THM` files) from being copied into the archive. |
| `thumbnail_extensions`              | No       | `["thm"]`           | Which extensions are treated as thumbnails when `exclude_thumbnails` is on. |
| `date_mismatch_threshold_days`      | No       | `1`                 | Passed straight through to `analyze_date` — how many days apart two date signals (e.g. EXIF vs. filesystem) can be before they're treated as disagreeing. |
| `review_folder_name`                | No       | `"_review_needed"`  | Folder (directly under `archive_root`) where low-confidence files are placed instead of a guessed date folder. |

All paths are resolved relative to the directory you run the command from — by convention, that's always the `ChronoVault/` project root.

**Note:** files excluded by a filter are still indexed and still tracked — they're just not copied. Nothing is ever silently lost from the inventory; you can always loosen a filter later and re-run Importer to pick them up.

## Archive Structure

```
archive/
├── 2024/
│   ├── 01/
│   │   └── 12/
│   │       └── photo.jpg
│   └── 03/
│       └── 15/
│           └── video.mp4
├── 2026/
│   └── 07/
│       └── 09/
│           └── another_photo.jpg
└── _review_needed/
    └── screenshot_with_no_exif.jpg
```

Date folders are built automatically as confident files are copied. `_review_needed/` is flat (no date subfolders) — it holds anything `analyze_date` wasn't confident enough about to file by date.

**Filename collisions:** since `_review_needed/` pools files from many different source folders into one place, it's much more likely for two files to share a filename than in a normal date folder. If a destination filename is already taken, Importer appends `(1)`, `(2)`, etc. rather than silently overwriting an existing file — this applies everywhere Importer copies to, not just the review folder, but it's the review folder where it actually comes up in practice.

## Archive Database (`archive_database.db`)

Created automatically inside `archive_root` the first time Importer runs. This is a separate database from `located_files.db` — it only tracks what's actually inside the archive, not the full source inventory. See the project's `Database_schema.md` for the complete column-by-column reference; the columns most relevant to Importer specifically are:

| Column         | Type    | Description                                                              |
|-----------------|---------|------------------------------------------------------------------------------|
| `date_taken`     | TEXT    | The date `analyze_date` chose.                                              |
| `date_source`    | TEXT    | Analyzer source such as `exif_gps`, EXIF/TIFF/XMP, filename, folder path, or filesystem fallback. Importer does not enable OCR. |
| `confidence`     | INTEGER | `analyze_date`'s confidence score, 0–100.                                    |
| `date_reason`    | TEXT    | Short explanation, e.g. `"EXIF (DateTimeOriginal) -- confirmed by filesystem creation date"`. |
| `date_uncertain` | INTEGER | `1` if this file was routed to the review folder instead of a date folder.   |

`confidence` and `date_reason` are added automatically via `ALTER TABLE` the first time Importer runs against an older archive database that predates them — no manual migration needed.

Camera metadata (`camera_make`, `camera_model`, `gps_latitude`, `gps_longitude`, `aperture`, `iso_speed`, `focal_length_mm`) is also recorded when present in EXIF, regardless of which folder the file ends up in.

## Processing and Failure Notes

- Importer stats the source file at run time; it does not trust the indexed size. Path exclusion substrings are case-sensitive. `require_exif` means Pillow returned any EXIF dictionary, not specifically a capture-date tag.
- For each successful copy, the source row is changed to `imported` **before** the archive row is inserted. A crash or database error between those operations can leave a copied file and imported source status without a corresponding archive record.
- Archive insertion uses `INSERT OR IGNORE`, while filename collision handling checks the filesystem only. If a database row refers to a currently missing destination path, Importer can copy a new file to that path and silently retain the old database row instead of recording the new source.
- A failed chunked copy can leave a partial destination file. A retry then treats that name as occupied and chooses a numbered filename.
- Importer does not compare content hashes with the existing archive. Re-indexing identical bytes from a different source path can create another archived copy unless Condition Database marks it duplicate within the current source inventory.
- There is no Importer JSON report; outcomes are printed and persisted through the two databases.

## Requirements

- Python 3
- [Pillow](https://pypi.org/project/Pillow/) — `pip install Pillow` — used for reading EXIF metadata

## Example

```
python3 importer/importer.py importer/config.json
```

```
Loading configuration from: importer/config.json
Located-files database: located_files.db
Archive root: archive
Extensions to copy: ['jpg', 'jpeg', 'mp4', 'mov']
Filters: min_size=20480 bytes, max_size=524288000, require_exif=False, exclude_path_contains=['.config', 'cache'], exclude_thumbnails=True (['.thm']), date_mismatch_threshold_days=1
Low-confidence files will be routed to: archive/_review_needed/
Archive database: archive/archive_database.db
------------------------------------------------------------
Found 119 file(s) to evaluate.
------------------------------------------------------------
[1/119] /home/user/Pictures/IMG_0001.jpg (3.2MB)
    OK -> archive/2026/07/09/IMG_0001.jpg  (confidence=100: EXIF (DateTimeOriginal) -- confirmed by filesystem creation date)
[2/119] /home/user/Pictures/cache/thumb_0001.jpg (4.1KB)
EXCLUDED: /home/user/Pictures/cache/thumb_0001.jpg (below min size (4.1KB < 20.0KB))
[3/119] /home/user/Pictures/old_scan.jpg (1.1MB)
    REVIEW -> archive/_review_needed/old_scan.jpg  (confidence=30: filesystem creation date)
...
------------------------------------------------------------
Copied: 94
  of which sent to review folder (low confidence): 6
Excluded by filter: 12
Failed: 0
Missing (source no longer exists): 1
Total evaluated: 119
```
