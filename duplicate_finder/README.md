# Duplicate Finder

Duplicate Finder hashes files with SHA-256 and groups anything with identical content together, so you can see exactly which files are true duplicates (not just same name or same size) and how much space could be reclaimed by removing the extras. Like Audit Archive, it's **read-only** — it reports duplicates, it never deletes or merges anything itself.

## Two Modes

Set via `"mode"` in the config — `"source"` or `"archive"`.

**`source` mode** — checks `located_files.db`, the pre-import inventory Indexer built. This was the original use case: run it *before* Importer, to catch and think about duplicates before they ever get copied into the archive. By default it only checks rows with status `located` (configurable via `statuses_to_check`).

**`archive` mode** — checks the archive folder itself, on disk. This was added after discovering that source-mode alone can't catch everything: files copied into the archive *by hand*, bypassing Indexer and Importer entirely, would never show up in `located_files.db` in the first place. Archive mode walks `archive/` directly, so nothing gets missed regardless of how it got there.

Both modes produce the same kind of report at the end — grouped by hash, sorted by how much space each group wastes — just built from a different starting point.

## Hashing and Caching

Hashing is the expensive part, so both modes try hard to avoid redoing it:

- **`source` mode** caches hashes into `located_files.file_hash` (added via `ALTER TABLE` the first time it runs, same pattern used everywhere else in ChronoVault for schema upgrades). A file already hashed on a previous run is skipped — you'll see it counted under "Already hashed (cached)" rather than "Newly hashed."
- **`archive` mode** is a little more nuanced, because a file here can be in one of two states:
  - **Documented** (it has a row in `archive_database.db`) — uses the hash Audit Archive already cached, if one exists. If not (e.g. Duplicate Finder is run before Audit Archive ever has been), it computes and caches it itself, so either tool can be the one that ends up filling that column in.
  - **Undocumented** (on disk, but no database row — e.g. copied in by hand) — there's no row to cache a hash *into*, so these are hashed fresh on every single run. This is inherent to the situation, not a missed optimization: an undocumented file has nowhere to persist a cached value until it's actually added to the database.

Either way, files ≥20MB show a live `hashing: X / Y (Z%)` progress readout while being hashed, same convention used by Importer and Audit Archive, so a multi-gigabyte video doesn't look like it's frozen.

## Grouping and Reporting

Files are grouped by hash; any group with more than one file is a duplicate group. Groups are sorted by **wasted space** (`file_size × (count - 1)`) descending, so the biggest opportunities to reclaim space show up first — a group of two 400MB videos ranks above a group of ten 30KB thumbnails, even though the thumbnail group has more files in it.

In `archive` mode, each file in a group is tagged `documented` or `[undocumented]` in the printed output, so you can tell at a glance whether a duplicate is one Importer already knows about or one that snuck in another way.

## Usage

```
python3 duplicate_finder/duplicate_finder.py duplicate_finder/config.json
```

**config.json (`source` mode):**

| Option              | Default              | Description                                                      |
|----------------------|-----------------------|----------------------------------------------------------------------|
| `mode`               | `"source"`             | `"source"` or `"archive"`.                                          |
| `database_path`      | *(required)*           | Path to `located_files.db`.                                         |
| `statuses_to_check`  | `["located"]`          | Which `located_files.status` values to include.                      |
| `output_path`        | `duplicate_report.json`| Where to write the JSON report.                                     |

**config.json (`archive` mode):**

| Option          | Default                  | Description                                  |
|------------------|----------------------------|--------------------------------------------------|
| `mode`           | `"source"`                  | Must be `"archive"`.                             |
| `archive_root`   | *(required)*                | Path to the archive folder to scan.              |
| `output_path`    | `duplicate_report.json`     | Where to write the JSON report.                  |

## Output

```json
{
    "scan_timestamp": "...",
    "mode": "archive",
    "summary": {
        "files_checked": 0,
        "duplicate_groups": 0,
        "duplicate_files": 0,
        "wasted_bytes": 0
    },
    "duplicate_groups": [
        {
            "file_hash": "...",
            "file_size": 0,
            "count": 0,
            "files": [
                { "path": "...", "documented": true }
            ]
        }
    ]
}
```

`summary` includes a few extra fields depending on mode — `source` mode has none beyond the common ones; `archive` mode adds `documented_cached`, `documented_newly_hashed`, and `undocumented_hashed`, mirroring the three-way breakdown printed to the terminal.

## Known Limitation

Duplicate Finder can tell you *that* two files are identical, but not *which folder is correct* if they're sitting in two different date folders (e.g. the same video imported twice, landing differently each time based on what date evidence was available at the time). Resolving that requires a person to look at both copies and decide — see Audit Archive's README for the fuller explanation of why this happens, and the root `README.md` roadmap for the planned GUI review step that will handle it.
