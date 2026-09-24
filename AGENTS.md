# ChronoVault Agent Guide

## Project Overview

ChronoVault is a local-first Python toolset for finding scattered media, evaluating its likely date and relevance, and copying it into a chronological archive without deleting originals. It is deliberately composed of small command-line tools; the Qt GUI is a launcher/orchestration layer, not a replacement implementation.

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

## Documentation Map

- `README.md` — project purpose, current pipeline, setup, broad architecture, and a high-level status summary.
- `roadmap.md` — the authoritative place to understand feature history, accepted limitations, open design questions, and priorities before proposing larger work.
- `Database_schema.md` — SQLite tables, status meanings, migrations, and ownership boundaries. Read this before changing a database column, status, or cross-tool behavior.
- `Date_signals.md` and `analyze_date/README.md` — date-evidence model and date subsystem architecture.
- Each pipeline directory has a `README.md`; read the README for the subsystem you are changing. In particular, consult `gui/README.md` for GUI/path behavior and `generate_test_data/README.md` before altering fixtures.
- `CHRONOVAULT_HANDOFF.md` is historical context and design rationale. Treat current source and subsystem documentation as more authoritative where they differ.

Some docs are intentionally candid but can lag implementation. Confirm behavior in the relevant source/config before changing it, and update the affected README when a user-facing workflow changes.

## Architecture and Data Boundaries

- `located_files.db` is a disposable source inventory maintained by Indexer and enriched by classification/conditioning.
- `archive_database.db`, inside the archive root, is the persistent record of copied archive files.
- Keep the read/write boundary intact: `retrieve_data` must not mutate; `write_data` is the explicit correction path.
- Date analysis is evidence-in/scored-result-out. Add new signals at the appropriate extractor/dispatch point rather than hard-coding special cases into combination logic.
- Low-confidence dates are intentionally routed to `_review_needed/`; do not replace this with silent guessing.
- The project favors small independent tools and proven reuse over broad new abstractions.

## Configuration and Dependencies

- Each tool owns a `config.json`; `gui/gui_config.json` maps tools to their script/config locations.
- Paths in tool configs are operational state and may be changed by the GUI or by the user. Preserve unrelated config changes and do not reset paths casually.
- Core runtime: Python 3 and Pillow. OCR is opt-in and additionally needs Tesseract, `pytesseract`, OpenCV, and NumPy. The GUI additionally needs PySide6.
- There is no `requirements.txt`, `pyproject.toml`, Docker setup, formatter, linter, or CI configuration currently present. Do not assume one exists.

## Validation

- Start with `python3 test_functions/test_env.py` when validating a machine/environment.
- Use `./chronovault.sh` for an isolated end-to-end exercise; it intentionally contains a cleanup option that deletes only `chronovault_test/`. Do not use that option against real archives.
- Use the relevant focused script in `test_functions/` for date, OCR, retrieve, or write behavior. `test_write_data.py` intentionally mutates review data, so only run it against disposable/test data.
- `generate_test_data/generate_test_data.py` is the normal synthetic fixture source. Run changed code against an isolated output directory, not real media.
- After changes, run the narrowest relevant checks, inspect the resulting database/report behavior where applicable, and review `git diff --check` plus the final diff.

## Agent Guidelines

- Read only the documentation and code relevant to the requested subsystem before editing; do not re-read the entire repository by default.
- Keep changes small, incremental, and testable. Prefer one completed, verified step over a broad partially implemented redesign.
- Preserve non-destructive behavior: never delete or move originals unless the task explicitly concerns the guarded write path.
- Be especially cautious with database statuses, archive paths, and `config.json` edits: these affect multiple tools and may point at real user media.
- When a change alters behavior, update the corresponding subsystem README and, when needed, the root README/roadmap rather than duplicating documentation.
- Do not modify unrelated files or overwrite a dirty working tree. Do not commit unless the user explicitly asks.
