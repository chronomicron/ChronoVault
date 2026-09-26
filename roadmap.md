# ChronoVault Roadmap

This roadmap distinguishes current capability, verified limitations, and proposed work. Current behavior is defined by the implementation and subsystem READMEs; this file records direction and priorities rather than promising delivery dates.

## Product direction

ChronoVault is a local-first, non-destructive set of small tools for discovering scattered media, assessing likely relevance and capture date, and copying selected files into a chronological archive. The Qt application orchestrates those tools; it is not a second pipeline implementation.

The working pipeline is:

```text
Indexer → Classify Media → Condition Database → Importer → Audit Archive
```

Duplicate Finder and the `retrieve_data`/`write_data` review boundary support the pipeline. Originals are not deleted.

## Current capability

### Discovery and source inventory

- Indexer recursively discovers configured extensions, including dot-prefixed directories, and accumulates rows in `located_files.db`.
- It refuses a source root that already contains `archive_database.db` unless explicitly overridden. This guard does not detect a ChronoVault archive nested below a broader source root.
- ZIP, TAR-family, and ISO files can be recorded in `located_archives`. Optional listing records matching member names; ZIP/TAR paths are exercised by generated fixtures, while successful ISO listing still needs a real-file verification.
- Archive members are not extracted or added to the media workflow.
- Classify Media scores images conservatively and records its category, reason, and exclusion flag before hashing.

### Conditioning, import, and review

- Condition Database hashes eligible source rows, runs shared date analysis, and marks duplicates within the source inventory.
- Date analysis currently combines JPEG-family GPS/EXIF/XMP, TIFF `DateTime`, filename, folder, filesystem, and opt-in OCR evidence. Audio- and video-specific metadata are not implemented.
- Importer copies selected sources into dated folders, routes confidence below 50 to `_review_needed/`, and records archive metadata in `archive_database.db`.
- `retrieve_data` reads review state without mutation. `write_data` applies a chosen date, moves the archive file, and preserves original algorithmic fields while recording correction metadata.
- Audit Archive reports disk/database mismatches and caches hashes; it does not repair the archive.
- Duplicate Finder reports content-identical files in either source or archive mode; it does not delete or select a winner.

### User interface and diagnostics

- The PySide6 GUI launches the pipeline and supporting tools, streams output, synchronizes configured paths for mapped tools, records activity, and generates a diagnostic report.
- Archive-source and ambiguous destination checks guard common path-selection mistakes.
- The interface remains a launcher/orchestration layer. It does not yet provide a thumbnail browser, date/label filtering, candidate review, duplicate resolution, or audit repair.
- Running tools can be stopped by terminating their process. Graceful cancellation and cleanup of an in-progress copy are not implemented.

### Test support

- `generate_test_data` creates disposable synthetic fixtures for the main pipeline and media classification.
- `chronovault.sh` provides an isolated manual end-to-end workflow under `chronovault_test/`.
- `test_functions/` contains focused environment and behavior scripts. It is a manual verification collection, not an automated unit/integration test suite.
- The repository has no package manifest, formal test runner, CI configuration, formatter, or linter configuration.

## Known gaps and risks

### Data integrity and transaction boundaries

1. **Cross-database duplicate prevention.** Condition Database deduplicates within `located_files.db`, but no pre-copy step rejects a hash already present in `archive_database.db`. This is the highest-value safety improvement for repeated scans of read-only sources.
2. **Condition/import date divergence.** Importer recomputes date evidence rather than consuming the conditioned result. It also never enables OCR, so conditioned and archived dates can differ.
3. **Classification ownership.** Classify Media sets `media_excluded`, but Importer selects both `located` and `excluded` statuses and does not consult that flag. The intended owner of final eligibility needs to be made explicit.
4. **Non-atomic import.** Importer copies the file, marks the source row `imported`, and then inserts the archive row. A failure between those steps can leave disk and databases inconsistent.
5. **Non-atomic correction.** `write_data` moves a file before updating its row. A later database failure can strand the moved file.
6. **Partial-copy handling.** Interrupted copies have no temporary-name/finalize protocol, so incomplete destinations may look final.
7. **Destination collisions and retries.** Name allocation depends on current disk state. Stale database rows and repeated corrections can produce confusing suffixed names.
8. **Schema governance.** Tables evolve through independent `PRAGMA table_info`/ `ALTER TABLE` calls, without a schema version, foreign keys, check constraints, or explicit operational indexes.

### Audit and reconciliation

- Audit Archive applies its configured extension filter while walking disk. A documented database row whose file has a currently excluded extension can be reported missing even when it exists.
- The misplaced-file check derives an expected `YYYY/MM/DD` path from the first three relative path components. Deeper or nonstandard layouts can evade or confuse it.
- Recommendations for undocumented files use a separate EXIF/filesystem heuristic instead of shared `analyze_date`, so audit and import can disagree.
- Audit and Duplicate Finder cache hashes without recording file size/mtime or another freshness key. Replaced-in-place files can retain stale hashes.
- Neither tool offers an approved repair workflow; reports require manual interpretation.

### Source freshness and indexing

- Re-indexing an existing path does not refresh size or timestamps because `file_path` uniqueness turns rediscovery into an ignored insert.
- Relative database, source, archive, and report paths remain dependent on the process working directory.
- Archive member matching stops after 500 names. `matching_file_count` is therefore a stored capped-list length, not necessarily the archive's full match count.
- A later successful archive listing can clear a previous failure note, which loses failure history.
- Run summaries can mix newly inserted rows with previously known paths in ways that obscure what changed.
- Archive extraction, password handling, and RAR/7z content support are not implemented.

### Date evidence

- Agreement uses integer `timedelta.days`, so the configured threshold is not a precise elapsed-time tolerance.
- GPS, EXIF, and XMP values are compared without a complete timezone model; XMP offsets are discarded rather than normalized.
- The XMP parser reads element text but can miss common RDF attribute forms.
- `analyze_date/config.json` is not loaded by the analyzer.
- OCR is opt-in and expensive. When Condition Database enables it, it is attempted for every supported image rather than only weak cases.
- `audio_tools/` and `video_tools/` are placeholders. ID3, BWF, QuickTime/MP4, HEIC/RAW, IPTC, external XMP, Takeout JSON, and known-date hash twins remain future work.

### GUI, configuration, and portability

- GUI path synchronization only affects tools mapped to a config entry. Each tool still owns its path configuration, so drift is possible outside the GUI.
- Some scripts and manual tests assume particular working directories or fixture layouts.
- The GUI's executable probe is fixed and its subprocess stop action is abrupt.
- Optional dependencies and external executables are reported by environment checks, but installation is manual.

### Tests and generated data

- Test helpers are mostly print-and-inspect scripts with limited assertions and no isolation framework.
- Some tests mutate review data and are safe only against disposable fixtures.
- Fixture generation does not clean an existing output tree unless the caller does so.
- Date-relative fixtures depend on the current clock, which limits reproducibility.
- Coverage is incomplete for failure injection, interrupted copies/moves, migration order, stale caches, path collisions, and real ISO success.

## Planned work

### Priority 1: protect archive integrity

- Add an archive-hash cross-check before copying and define how corrected/high-confidence archive records supply the canonical known date.
- Make import and correction transitions recoverable: temporary destination names, verified copy completion, coordinated database updates, and explicit restart behavior.
- Resolve whether Importer consumes conditioned date/classification fields or owns recomputation; then make status and `media_excluded` semantics consistent.
- Add cache invalidation metadata and verify hashes when a file's size or modification time changes.
- Add failure-injection tests around copy, move, and database boundaries.

### Priority 2: make reconciliation actionable

- Align Audit Archive's file discovery and date recommendation with the importer's supported media and shared analyzer.
- Expand audit output to distinguish filtered, missing, undocumented, misplaced, stale-hash, and database-collision cases reliably.
- Design a dry-run-first repair path. It must never silently delete originals or choose a duplicate winner.
- Add archive-level duplicate prevention and a separate human review flow for existing duplicate groups.

### Priority 3: stabilize paths, migrations, and repeat runs

- Adopt consistent path resolution independent of the launch directory, while preserving portable relative configurations where intentional.
- Introduce schema versioning and ordered migrations for both SQLite databases.
- Refresh mutable metadata for previously indexed paths and clarify incremental-run summaries.
- Finish ISO success-path verification; decide whether RAR/7z listing is worth its external dependencies.
- Preserve archive-listing failure history and distinguish truncated match lists from complete counts.

### Priority 4: formalize verification

- Build automated unit tests for date parsers/scoring and database migrations.
- Add isolated integration tests for the full pipeline, reruns, collision naming, stale files, hidden folders, archive guards, and interrupted operations.
- Make fixture generation deterministic with an optional seed/reference time and an explicit safe-clean mode.
- Add a minimal dependency/package definition and CI only after the supported runtime/dependency policy is decided.

### Priority 5: broaden evidence and media support

- Correct exact-duration agreement and timezone normalization before adding more high-confidence signals.
- Support XMP RDF attributes and broader still-image metadata.
- Add audio tag and video container extractors in their existing placeholder packages.
- Evaluate external sidecars, Takeout metadata, HEIC/RAW support, and archive-known hash/date evidence.
- Keep speculative content inference and OCR as review aids rather than automatic authority.

## Candidate review and archive extraction

A shared candidate workflow is a useful future foundation for ambiguous-photo classification and extracted archive members. It is not implemented.

A possible model is:

- a `candidate` source status for a discovered item that requires a decision;
- a separate pending/approved/rejected decision field so rejection is not confused with config-driven `excluded`;
- read-only listing functions returning serializable records;
- explicit write functions that approve or reject selected IDs;
- approval changing the item to normal import eligibility;
- terminal-first verification, followed by GUI integration.

The exact schema, provenance fields, lifecycle, and interaction with classification must be designed before migration code is written. The proposed tables and columns in `Database_schema.md` are not current database objects.

Archive extraction should use this review boundary rather than auto-importing opaque members. It also needs safe staging, path traversal protection, password/error reporting, provenance back to the containing archive, and cleanup rules.

## Longer-term product work

- A media browser with thumbnails, date ranges, evidence details, review actions, and duplicate-group decisions.
- Manual labels and optional machine-generated suggestions for people, places, events, and content. Label tables remain proposed only.
- GPS reverse geocoding with a local-first/privacy-conscious provider strategy.
- Richer document, audio, and video workflows.
- Localization architecture before translating the GUI; French date-folder parsing exists, but GUI localization and Japanese OCR/date notation do not.
- An optional source-cleanup workflow only after content verification, archive integrity, permissions, and physical read-only media are handled explicitly. Source deletion is not part of the current product contract.
- True forensic undelete, if ever pursued, should wrap established tools such as PhotoRec/TestDisk rather than reimplement recovery.

## Explicit non-goals for current automated behavior

- Deleting source originals.
- Automatically deleting duplicates or selecting a “winner.”
- Treating edit/tagging/filesystem timestamps as authoritative capture dates without corroboration.
- Filing speculative ML/ASR guesses without human review.
- Presenting candidate, labels, archive extraction, or repair schemas as implemented.

## Decision log carried forward

- Keep `located_files.db` disposable and `archive_database.db` persistent.
- Keep retrieve operations read-only and corrections behind an explicit write boundary.
- Keep low-confidence dates visible in `_review_needed/` rather than guessing silently.
- Favor small tools and shared pure logic over duplicating behavior in the GUI.
- Preserve originals and prefer reversible, report-first operations.
