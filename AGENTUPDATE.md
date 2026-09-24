# ChronoVault Agent Update Guide

This document serves as a navigational guide for AI coding agents working with the ChronoVault project. It summarizes the project structure, conventions, and key subsystems without duplicating existing documentation.

## Project Overview

ChronoVault is a local-first Python toolset for finding scattered media, evaluating its likely date and relevance, and copying it into a chronological archive without deleting originals. The system follows a pipeline approach with small, independent command-line tools that compose together.

The normal pipeline is:

```text
Indexer → Classify Media → Condition Database → Importer → Audit Archive
```

`Duplicate Finder` and the `retrieve_data` / `write_data` pair support that pipeline but are not required for every run.

## Repository Map

- `indexer/` — discovery into the SQLite source inventory; also records ZIP/TAR/ISO locations and optionally lists their contents.
- `classify_media/` — conservative pre-hash image classification. It persists a score/category/reason in the source inventory; see its README before changing scoring or exclusion behavior.
- `condition_database/` — hashes eligible inventory rows, runs date analysis, and marks within-inventory duplicates before import.
- `importer/` — copies eligible sources into the archive and owns `archive_database.db`.
- `analyze_date/` — reusable date-analysis package. `analyze_date.py` orchestrates source-specific modules in `image_tools/` and type-independent filename/path modules in `multi_tools/`. `audio_tools/` and `video_tools/` are future-facing placeholders.
- `audit_archive/` — reconciles files on disk with `archive_database.db`; it is read-only except for cached file hashes.
- `duplicate_finder/` — reports content-identical files in source or archive mode.
- `retrieve_data/` and `write_data/` — the review read/write boundary. The former is read-only; the latter moves eligible review-bucket files and updates their records.
- `generate_test_data/` — produces disposable synthetic pipeline and media-classification fixtures.
- `test_functions/` — manual verification/debugging scripts, not a formal test suite.
- `gui/` plus `chronovault.py` — PySide6 GUI and non-Qt GUI support code.
- `chronovault.sh` — interactive, contained test runner; its artifacts belong under `chronovault_test/`.

## Core Pipeline Architecture

The main pipeline consists of these sequential steps:

1. **Indexer** - Discovers media files and logs them to `located_files.db`
2. **Classify Media** - Pre-classifies files as likely personal media or web assets
3. **Condition Database** - Hashes files, determines dates, and identifies duplicates
4. **Importer** - Copies eligible files into the chronological archive
5. **Audit Archive** - Reconciles archive contents with database records
6. **Duplicate Finder** - Identifies content-identical files

## Key Subsystems

### Indexer (`indexer/`)
- Searches folder hierarchies for media files
- Logs results to `located_files.db` 
- Handles compressed archives (ZIP, TAR, ISO) with optional content listing
- Safe to run repeatedly - accumulative and non-destructive
- Creates `located_files` and `located_archives` tables

### Classify Media (`classify_media/`)
- Conservative pre-hash classification of media files
- Only excludes files explicitly marked as `certain_not`
- Adds `media_score`, `media_category`, `media_reason`, and `media_excluded` columns to database
- Re-running is safe with `force_reclassify` flag for threshold changes

### Condition Database (`condition_database/`)
- Computes SHA-256 hashes, runs date analysis, identifies duplicates
- Works on files with status `'located'`
- Adds `confidence`, `date_reason`, `date_source`, `date_taken`, and `file_hash` columns
- Idempotent - safe to re-run multiple times

### Importer (`importer/`)
- Copies eligible files into dated archive structure
- Routes low-confidence files to `_review_needed/` folder
- Creates `archive_database.db` inside archive root
- Maintains separate database for archive records vs. source inventory
- Safe to re-run - skips already-imported files

### Audit Archive (`audit_archive/`)
- Read-only reconciliation tool comparing disk contents with database
- Reports undocumented, missing, and misplaced files
- Caches SHA-256 hashes in `archive_files.file_hash` column
- Never modifies or deletes files

### Duplicate Finder (`duplicate_finder/`)
- Hashes files to find content-identical duplicates
- Two modes: `source` (checks `located_files.db`) and `archive` (checks archive folder)
- Both modes produce same report format but from different starting points
- Caches hashes to avoid re-computation

### Data Access Layer (`retrieve_data/` and `write_data/`)
- **`retrieve_data`**: Read-only access layer for archive database data
  - Returns structured Python dicts for UI consumption
  - Provides `list_review_items()` and `get_file_details()` functions
  - Never touches files or modifies database

- **`write_data`**: Mutating twin of `retrieve_data`
  - Only module allowed to move files from review bucket
  - Updates records with user corrections
  - Applies date corrections via `apply_date_correction()` function
  - Never modifies original algorithmic evidence fields

### Date Analysis (`analyze_date/`)
- Core date determination engine used by Importer and Condition Database
- Orchestrates evidence gathering from multiple sources (EXIF, XMP, GPS, filesystem)
- Supports different file types with specialized tools in `image_tools/`
- Returns scored, explained date conclusions (confidence score 0-100)

### GUI (`gui/`)
- PySide6 Qt-based launcher for the pipeline
- Launches terminal tools with live output streaming
- Manages configuration synchronization between tools
- Includes diagnostic report generation and activity logging

## Database Schema

### Source Inventory (`located_files.db`)
- `located_files` table: File metadata, status, hashes
- `located_archives` table: Archive file locations and contents

### Archive Records (`archive_database.db`) 
- `archive_files` table: Archive file records with date, confidence, and history

## Key Design Principles

1. **Non-destructive**: Never modifies or deletes original files
2. **Safe re-running**: Most tools can be safely run multiple times
3. **Separation of concerns**: Read-only vs. mutating operations clearly separated
4. **Accumulative**: Tools add to existing data rather than replace it
5. **Type-agnostic**: Core logic works across different media types
6. **Modular**: Each tool has a single, well-defined purpose

## Configuration and Dependencies

- Each tool owns a `config.json`; `gui/gui_config.json` maps tools to their script/config locations.
- Paths in tool configs are operational state and may be changed by the GUI or by the user. Preserve unrelated config changes and do not reset paths casually.
- Core runtime: Python 3 and Pillow. OCR is opt-in and additionally needs Tesseract, `pytesseract`, OpenCV, and NumPy. The GUI additionally needs PySide6.
- There is no `requirements.txt`, `pyproject.toml`, Docker setup, formatter, linter, or CI configuration currently present. Do not assume one exists.

## Validation Procedures

- Start with `python3 test_functions/test_env.py` when validating a machine/environment.
- Use `./chronovault.sh` for an isolated end-to-end exercise; it intentionally contains a cleanup option that deletes only `chronovault_test/`. Do not use that option against real archives.
- Use the relevant focused script in `test_functions/` for date, OCR, retrieve, or write behavior. `test_write_data.py` intentionally mutates review data, so only run it against disposable/test data.
- `generate_test_data/generate_test_data.py` is the normal synthetic fixture source. Run changed code against an isolated output directory, not real media.
- After changes, run the narrowest relevant checks, inspect the resulting database/report behavior where applicable, and review `git diff --check` plus the final diff.

## Codebase Conventions

- All tools use consistent `config.json` path resolution patterns
- Database schema changes use `ALTER TABLE` with automatic column creation
- Tools are designed for command-line usage and can be called programmatically
- All database operations use SQLite with proper error handling
- Progress indicators shown for large file operations (20MB+)
- Configuration values are preserved during GUI synchronization

## File Structure Overview

```
chronovault/
├── indexer/                 # File discovery tool
├── classify_media/          # Pre-classification tool  
├── condition_database/      # Hashing and date analysis
├── importer/                # Archive copying tool
├── audit_archive/           # Archive reconciliation
├── duplicate_finder/        # Duplicate detection
├── retrieve_data/           # Read-only data access
├── write_data/              # Mutating data access
├── analyze_date/            # Date analysis engine
├── gui/                     # Qt GUI launcher
├── generate_test_data/      # Test data generation
├── test_functions/          # Manual verification scripts
├── chronovault.py           # Main GUI launcher
└── chronovault.sh           # Test runner script
```

## Documentation Resources

- `README.md` - Project purpose, current pipeline, setup, broad architecture, and a high-level status summary.
- `roadmap.md` - The authoritative place to understand feature history, accepted limitations, open design questions, and priorities before proposing larger work.
- `Database_schema.md` - SQLite tables, status meanings, migrations, and ownership boundaries. Read this before changing a database column, status, or cross-tool behavior.
- `Date_signals.md` and `analyze_date/README.md` - date-evidence model and date subsystem architecture.
- Each pipeline directory has a `README.md`; read the README for the subsystem you are changing. In particular, consult `gui/README.md` for GUI/path behavior and `generate_test_data/README.md` before altering fixtures.
- `CHRONOVAULT_HANDOFF.md` is historical context and design rationale. Treat current source and subsystem documentation as more authoritative where they differ.

## Agent Guidelines

- Read only the documentation and code relevant to the requested subsystem before editing; do not re-read the entire repository by default.
- Keep changes small, incremental, and testable. Prefer one completed, verified step over a broad partially implemented redesign.
- Preserve non-destructive behavior: never delete or move originals unless the task explicitly concerns the guarded write path.
- Be especially cautious with database statuses, archive paths, and `config.json` edits: these affect multiple tools and may point at real user media.
- When a change alters behavior, update the corresponding subsystem README and, when needed, the root README/roadmap rather than duplicating documentation.
- Do not modify unrelated files or overwrite a dirty working tree. Do not commit unless the user explicitly asks.