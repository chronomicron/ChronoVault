# ChronoVault

ChronoVault is a local-first Python toolset for finding media scattered across drives and mounted storage, evaluating its likely relevance and date, and copying it into a chronological archive. It favors explainable evidence, visible uncertainty, and small tools that can be run independently.

The project is currently most capable with still images. Its core indexing, image classification, date analysis, conditioning, import, review, audit, duplicate-reporting, test-data, and GUI-launcher workflows exist; broader media analysis and stronger recovery, repair, and test infrastructure remain under development.

## Why ChronoVault exists

Personal media tends to accumulate across old hard drives, removable media, NAS shares, cloud-synchronized folders, camera exports, and backups. Names and folder structures are inconsistent, metadata is sometimes missing or misleading, and copying everything blindly can preserve large amounts of noise and duplication.

ChronoVault builds a traceable working inventory, records why a file appears relevant and when it was probably created, and copies eligible files into an archive organized by date. When the available evidence is weak, it places the copy in `_review_needed/` instead of silently guessing.

## Design principles

- **Local-first.** Media and SQLite records stay on storage you control; the current pipeline does not require a hosted service.
- **Non-destructive toward sources.** The normal workflow reads original media and copies it into the archive. It does not delete or move source files.
- **Explicit writes.** ChronoVault is not wholly read-only: tools create and update databases, reports, cached hashes, configuration state, archive copies, and—when a person applies a correction—archive paths.
- **Explainable decisions.** Date results include their source, confidence, and reasoning. Classification likewise records its score, category, and evidence.
- **Visible uncertainty.** Low-confidence dates are routed to review rather than treated as facts.
- **Small, composable tools.** The command-line modules own the behavior. The Qt GUI launches and coordinates them rather than reimplementing the pipeline.

## Workflow

```text
Indexer → Classify Media → Condition Database → Importer → Audit Archive
```

1. **[Indexer](indexer/README.md)** recursively discovers configured media extensions and records them in the disposable source inventory, `located_files.db`. It also records ZIP, TAR, and ISO containers and can optionally list matching members without extracting them.
2. **[Classify Media](classify_media/README.md)** conservatively scores indexed images as likely personal media or likely web/graphic material. Its default policy excludes only the strongest negative category.
3. **[Condition Database](condition_database/README.md)** hashes eligible inventory rows, records date-analysis results for pre-import visibility, and marks byte-identical duplicates within the source inventory.
4. **[Importer](importer/README.md)** applies its own filters, calls the shared date analyzer again, copies eligible files into `YYYY/MM/DD/` or `_review_needed/`, records them in the persistent archive database, and updates source statuses. It does not consume Condition Database's stored date result as a cache.
5. **[Audit Archive](audit_archive/README.md)** compares the archive on disk with its database and reports undocumented, missing, and misplaced files. It does not repair or move them; its only database write is cached hashes for matched files.

Supporting components:

- **[Analyze Date](analyze_date/README.md)** is the shared evidence-gathering and scoring library used by Condition Database and Importer. Current signals cover JPEG-family metadata, TIFF dates, filenames, containing folders, filesystem timestamps, and opt-in image OCR. See [Date Signals](Date_signals.md) for the authoritative evidence catalog.
- **[Duplicate Finder](duplicate_finder/README.md)** reports SHA-256 duplicate groups in the source inventory or the archive. It never deletes or selects a preferred copy.
- **[Retrieve Data](retrieve_data/README.md)** provides read-only structured access to review rows. **[Write Data](write_data/README.md)** is the explicit mutating boundary for applying a person's date correction and moving the corresponding archive file.
- **[GUI](gui/README.md)** is a PySide6 launcher that streams tool output, synchronizes supported archive paths, records recent activity, and produces diagnostic reports.
- **[Generate Test Data](generate_test_data/README.md)** and **[test_functions](test_functions/README.md)** support disposable manual testing. They are not a formal automated test suite.

## Data and archive layout

ChronoVault deliberately keeps two SQLite databases:

- `located_files.db` is a rebuildable source inventory enriched by classification, conditioning, and status updates.
- `<archive_root>/archive_database.db` is the persistent record of files copied into the archive.

A typical destination looks like:

```text
archive/
├── archive_database.db
├── 2024/03/15/photo.jpg
└── _review_needed/uncertain-photo.jpg
```

The databases are related by convention rather than foreign keys, and schema additions are currently performed by the tools that need them. See [Database Schema](Database_schema.md) for the complete schema, field ownership, statuses, and migration behavior.

## Getting started

ChronoVault is currently a developer-oriented repository rather than an installed Python package. There is no `requirements.txt`, `pyproject.toml`, installer, or container definition. Run commands from the repository root because many configured paths are resolved from the process working directory.

### Requirements

- Python 3.8 or newer
- Pillow for core image metadata and fixture generation
- PySide6 only for the GUI
- Tesseract, `pytesseract`, OpenCV, and NumPy only for opt-in OCR
- `pycdlib` only for listing ISO contents

For example, in a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install Pillow
```

Install optional dependencies only for the features you intend to use; consult the relevant module README for details.

### Check the environment

```bash
python3 test_functions/test_env.py
```

This checks required and optional components and reports what is available. It is a diagnostic script, not a full test suite.

### Explore safely with generated data

```bash
./chronovault.sh
```

The interactive test runner keeps its generated media, databases, archive, and reports under `chronovault_test/`. Its cleanup action deletes that disposable directory, so read the prompt and do not repurpose the directory for real media.

The underlying pipeline can also be run directly after reviewing each tool's `config.json`:

```bash
python3 indexer/indexer.py indexer/config.json /path/to/source
python3 classify_media/classify_media.py classify_media/config.json
python3 condition_database/condition_database.py condition_database/config.json
python3 importer/importer.py importer/config.json
python3 audit_archive/audit_archive.py audit_archive/config.json
```

Treat configuration paths as operational state: they may point to real media or be changed by the GUI. Prefer a disposable source and destination until you understand the resulting databases and archive layout.

### Use the GUI launcher

After installing PySide6:

```bash
python3 chronovault.py
```

The GUI exposes the working tools and diagnostics, but it is not yet a media browser or full review interface. See its [README](gui/README.md) for path synchronization, safety checks, dependencies, and current limitations.

## Current status and direction

The core image-oriented workflow is usable and has been exercised with generated and real-world data, but ChronoVault should still be treated as an evolving personal project rather than a polished archival product. In particular, filesystem/database transitions are not fully transactional, automated test coverage is limited, and archive-wide pre-copy duplicate protection is not yet complete.

Major planned areas include audio/video metadata extraction, richer image and sidecar support, candidate review, archive-member extraction, repair workflows, duplicate resolution, stronger schema/migration handling, automated tests, labeling, and search. These are future directions, not current features. See the [Roadmap](roadmap.md) for the maintained list of risks, priorities, and open design decisions.

## Documentation

- [Database Schema](Database_schema.md) — authoritative SQLite schema, ownership, statuses, and migration behavior.
- [Date Signals](Date_signals.md) — implemented date evidence and scoring, limitations, and researched future sources.
- [Roadmap](roadmap.md) — current gaps, risks, priorities, and future work.
- [Agent Guide](AGENTS.md) — repository guidance for coding agents; it is scheduled for a separate audit.
- Module READMEs — detailed usage, configuration, behavior, and limitations:
  - [Indexer](indexer/README.md), [Classify Media](classify_media/README.md), [Condition Database](condition_database/README.md), [Importer](importer/README.md)
  - [Audit Archive](audit_archive/README.md), [Duplicate Finder](duplicate_finder/README.md), [Retrieve Data](retrieve_data/README.md), [Write Data](write_data/README.md)
  - [Analyze Date](analyze_date/README.md), including [image](analyze_date/image_tools/README.md), [multi-type](analyze_date/multi_tools/README.md), [audio placeholder](analyze_date/audio_tools/README.md), and [video placeholder](analyze_date/video_tools/README.md) documentation
  - [GUI](gui/README.md), [Generate Test Data](generate_test_data/README.md), and [manual test utilities](test_functions/README.md)

When documents disagree about current behavior, the implementation and the audited subsystem documentation take precedence. Planned behavior should remain clearly labeled until it exists.
