# ChronoVault Agent Guide

## Purpose

Read this file first when beginning work in the repository. It is a routing map for finding the minimum authoritative context needed for a task, not a substitute for the project and module documentation.

Use progressive context loading:

1. Identify the subsystem or cross-cutting concern in the request.
2. Read the documents named for that task below.
3. Inspect only the relevant implementation and configuration files.
4. Expand to adjacent modules only when a dependency, database field, or workflow boundary requires it.

Do not scan the entire repository for a narrowly scoped change. For current behavior, use this precedence: implementation → audited current documentation → historical context files.

## Project orientation

ChronoVault is a local-first Python toolset that inventories scattered media, evaluates relevance and likely dates, and copies eligible files into a chronological archive while preserving original source media. It consists of small command-line tools; the PySide6 GUI launches and coordinates those tools rather than implementing a separate pipeline.

```text
Indexer → Classify Media → Condition Database → Importer → Audit Archive
```

Duplicate Finder and the `retrieve_data`/`write_data` review boundary support the pipeline. The project is most mature for still images. Do not present roadmap features as implemented.

## Authoritative documentation

| Path | Read it for |
|---|---|
| [README.md](README.md) | Project purpose, high-level architecture, current capabilities, setup, and documentation entry points. |
| [Database_schema.md](Database_schema.md) | Complete SQLite schema, field ownership, statuses, migrations, and database-boundary risks. Read before changing a column, status, or cross-tool data contract. |
| [Date_signals.md](Date_signals.md) | Implemented date sources, scoring behavior, consumers, limitations, and clearly separated future signals. |
| [roadmap.md](roadmap.md) | Known defects, implementation risks, priorities, open design questions, and future work. Consult before architectural changes or “fixing” behavior that may be deliberate or already tracked. |
| `<module>/README.md` | Authoritative usage, configuration, behavior, and limitations for that module. Read it before editing the module. |

`AGENTUPDATE.md` and `CHRONOVAULT_HANDOFF.md` are historical context only. They contain stale status, completed tasks, and superseded plans; do not use them as current authority.

## Repository map

| Area | Responsibility | First documentation to read |
|---|---|---|
| `indexer/` | Recursively discovers configured media; records source files and archive containers; optionally lists archive members. | [indexer/README.md](indexer/README.md) |
| `classify_media/` | Conservatively scores indexed images before hashing/import. | [classify_media/README.md](classify_media/README.md) |
| `condition_database/` | Hashes eligible source rows, records date analysis, and marks within-inventory duplicates. | [condition_database/README.md](condition_database/README.md) |
| `analyze_date/` | Reusable date-evidence dispatch and scoring library. It is not a CLI. | [Date_signals.md](Date_signals.md), then [analyze_date/README.md](analyze_date/README.md) |
| `analyze_date/image_tools/` | Implemented image-specific EXIF, GPS, XMP, TIFF, and OCR extractors. | [analyze_date/image_tools/README.md](analyze_date/image_tools/README.md) |
| `analyze_date/multi_tools/` | Filename and folder signals that apply to any file type. | [analyze_date/multi_tools/README.md](analyze_date/multi_tools/README.md) |
| `analyze_date/audio_tools/`, `video_tools/` | Future-facing placeholders; no type-specific audio/video extraction exists yet. | Their local `README.md` files and [roadmap.md](roadmap.md) |
| `importer/` | Filters and copies eligible sources, recomputes dates, creates/updates the persistent archive database. | [importer/README.md](importer/README.md), then [Database_schema.md](Database_schema.md) |
| `retrieve_data/` | Read-only structured access to archive review rows. | [retrieve_data/README.md](retrieve_data/README.md) |
| `write_data/` | Explicit mutating API for applying date corrections and moving eligible archive files. | [write_data/README.md](write_data/README.md), then [Database_schema.md](Database_schema.md) |
| `audit_archive/` | Reports disk/database mismatches and caches hashes; does not repair the archive. | [audit_archive/README.md](audit_archive/README.md) |
| `duplicate_finder/` | Reports SHA-256 duplicate groups in source or archive mode; does not delete or choose a winner. | [duplicate_finder/README.md](duplicate_finder/README.md) |
| `gui/`, `chronovault.py` | PySide6 launcher, path synchronization, activity log, and diagnostics. | [gui/README.md](gui/README.md) |
| `generate_test_data/` | Creates disposable synthetic pipeline and classification fixtures. | [generate_test_data/README.md](generate_test_data/README.md) |
| `test_functions/` | Focused manual diagnostics, including mutating review tests; not a formal test suite. | [test_functions/README.md](test_functions/README.md) |
| `chronovault.sh` | Contained interactive manual pipeline under `chronovault_test/`. | Script comments, [README.md](README.md), and relevant module READMEs |

## Task-to-context routing

| Task | Minimum context |
|---|---|
| Architecture, setup, or project status | `README.md` → `roadmap.md`; inspect modules only if the question needs implementation proof. |
| Date extraction or confidence behavior | `Date_signals.md` → `analyze_date/README.md` → relevant `image_tools/` or `multi_tools/` source. Also inspect the consuming module when changing persisted or import behavior. |
| Indexing, archive detection, or source scanning | `indexer/README.md` → `indexer/indexer.py` and `indexer/config.json`; use `Database_schema.md` for table changes. |
| Media classification | `classify_media/README.md` → classifier/config and relevant `image_tools/`; inspect Importer and roadmap before changing exclusion semantics. |
| Database schema, statuses, or migrations | `Database_schema.md` → README/source for every field owner and consumer affected. Do not infer a contract from one tool alone. |
| Conditioning or pre-import duplicates | `condition_database/README.md` → its source/config → `analyze_date` docs if date behavior changes. |
| Import or archive creation | `importer/README.md` → `Database_schema.md` → Importer source/config; add `Date_signals.md` for date-routing changes. |
| Review reads or date corrections | `retrieve_data/README.md` and/or `write_data/README.md` → `Database_schema.md`; include Audit Archive when placement semantics change. |
| Archive reconciliation | `audit_archive/README.md` → `Database_schema.md` → audit source/config. |
| Duplicate detection | `duplicate_finder/README.md` → `Database_schema.md`; include Condition Database for pre-import duplicate behavior. |
| GUI or path synchronization | `gui/README.md` → `gui/gui_config.json` and relevant GUI source → README/config of every launched tool affected. |
| Tests or fixtures | `generate_test_data/README.md` and/or `test_functions/README.md` → relevant script → subsystem README being exercised. |
| New feature or broad refactor | `README.md` → `roadmap.md` → relevant specialized docs and implementation. Broaden inspection deliberately. |

## Repository-wide boundaries

- Protect original source media. The normal pipeline may read and copy sources but must not delete or move them. Archive-management operations may intentionally create or move archive files and update databases; keep those writes explicit and guarded.
- Keep the two databases conceptually separate: `located_files.db` is a disposable source inventory, while `<archive_root>/archive_database.db` is the persistent archive record. There are no enforced foreign keys between them.
- Preserve the review read/write boundary: `retrieve_data` remains read-only; `write_data` is the explicit correction path. Preserve original algorithmic evidence when recording a user correction.
- Preserve explainability. Date and classification decisions retain sources, scores/confidence, and reasons. Low-confidence dates belong in `_review_needed/`, not silently in a guessed date folder.
- Importer currently calls `analyze_date` again; it does not consume Condition Database's stored result as a cache. Verify both consumers before changing date behavior.
- The GUI is orchestration only. Shared behavior belongs in the underlying tool or reusable non-Qt logic, not a second GUI-specific implementation.
- Prefer small, proven changes over speculative abstractions. Reuse existing boundaries; introduce shared machinery when a concrete cross-module need justifies it.
- Treat relative paths and configuration as operational state. Many paths resolve from the process working directory, and the GUI may update selected tool configs. Inspect current values and preserve unrelated user changes.
- Database statuses, paths, and dynamically added columns affect multiple tools. Read `Database_schema.md` and all relevant owners/consumers before editing them.
- Distinguish current functionality from proposals. Candidate review, archive extraction, labels/search, repair workflows, and audio/video metadata extraction are not implemented merely because designs or placeholders exist.

## Working and validation rules

- Preserve unrelated work in a dirty tree. Do not commit unless the user explicitly requests it.
- Keep changes incremental and reviewable. For multi-step work, state the checklist and report progress; validate each completed slice before broadening scope.
- Use `python3`, not bare `python`, in commands and scripts. New directories follow the repository's lowercase underscore-separated naming convention.
- Run tools from the repository root unless the relevant README says otherwise. There is no package manifest, formal test runner, CI, formatter, or linter configuration.
- Never test mutations against real media when disposable fixtures suffice. `test_functions/test_write_data.py` moves archive files and must run only against disposable data.
- Start environment checks with `python3 test_functions/test_env.py`. Use `./chronovault.sh` for the contained manual pipeline and `generate_test_data/generate_test_data.py` for fixtures, after reading their documentation.
- Run the narrowest relevant check, inspect resulting databases/reports when applicable, then review `git diff --check` and the final diff. Do not claim automated coverage that the repository does not have.
- When behavior changes, update the owning module README. Update `Database_schema.md`, `Date_signals.md`, root `README.md`, or `roadmap.md` only when their respective cross-cutting contract or status also changes; link rather than duplicate detail.

## Known issues and historical context

Use [roadmap.md](roadmap.md) for the maintained backlog and risk register. Confirm current behavior in source before implementing a roadmap item because priorities and accepted limitations can outlive the code that motivated them.

Historical rationale in `AGENTUPDATE.md` or `CHRONOVAULT_HANDOFF.md` may explain why a design arose, but much of their status information is obsolete. Consult them only when the audited documentation and implementation do not answer a rationale question, and never resurrect an old TODO without verifying it against `roadmap.md` and current source.
