# ChronoVault Development Backlog

This backlog was verified against the current roadmap, audited documentation, and representative implementation paths.

The largest cluster of risks comes from one underlying architectural fact: ChronoVault coordinates filesystem changes and two independent SQLite databases without a recoverable operation protocol. Import atomicity, partial copies, correction failures, collisions, cancellation, and repair should therefore be designed together, even if implemented incrementally.

## Master backlog

| # | Item | Type | Criticality | Effort | Dependencies |
|---:|---|---|---|---|---|
| 1 | Recoverable Importer state transition | Data integrity | Critical | Large | 2, 3, 13 |
| 2 | Temporary-copy, verification, and atomic finalize | Data integrity | Critical | Medium | None; informs 1 |
| 3 | Detect archive-row and destination collisions explicitly | Bug | Critical | Small | Prefer before 1 |
| 4 | Make date correction recoverable and validated | Data integrity | Critical | Medium | 3, 12; align with 1 |
| 5 | Prevent duplicates already present in the archive | Reliability | High | Large | 6, 8, 13 |
| 6 | Add hash-cache freshness and invalidation | Data integrity | High | Medium | 13 helpful |
| 7 | Refresh and reconcile previously indexed source paths | Reliability | High | Medium | 6, 13 |
| 8 | Establish one authoritative date-decision contract | Architecture | High | Large | 19–22 inform it |
| 9 | Establish one classification/import eligibility contract | Architecture | High | Medium | 11, 13 |
| 10 | Make source duplicate grouping deterministic and rerunnable | Reliability | Medium | Small | 6, 7, 9 |
| 11 | Add candidate and duplicate decision lifecycle | Missing functionality | Medium | Large | 9, 13 |
| 12 | Make paths independent of process working directory | Architecture | High | Large | 13; enables 18, 31 |
| 13 | Introduce schema versions and ordered migrations | Architecture | High | Large | None |
| 14 | Add database/configuration preflight checks | Reliability | Medium | Small | Can precede 13 |
| 15 | Fix Audit Archive extension-filter false positives | Bug | Medium | Small | None |
| 16 | Correct Audit Archive layout recognition | Bug | Medium | Small | 12 helpful |
| 17 | Use shared date analysis for audit recommendations | Architecture | Medium | Medium | 8, 19–21 |
| 18 | Add dry-run archive reconciliation and repair | Missing functionality | High | Large | 1–6, 12–17 |
| 19 | Use exact elapsed time for date agreement | Bug | Medium | Tiny | None |
| 20 | Define and implement timezone-aware date comparison | Data integrity | High | Large | Prefer before 23–25 |
| 21 | Read XMP RDF attribute-form dates | Bug | Medium | Small | Tests in 33 |
| 22 | Run OCR only when stronger evidence is inadequate | Reliability | Medium | Small | 8 helpful |
| 23 | Implement audio-specific date extractors | Missing functionality | Medium | Large | 8, 19, 20 |
| 24 | Implement video-specific date extractors | Missing functionality | Medium | Large | 8, 19, 20 |
| 25 | Support broader still metadata and sidecars | Feature | Medium | Very large | 8, 11, 19, 20 |
| 26 | Persist Indexer discovery incrementally | Reliability | Medium | Medium | 13 helpful; supports 30 |
| 27 | Correct and verify archive-container listing state | Reliability | Medium | Medium | 33, 34 helpful |
| 28 | Add safely staged archive-member extraction | Missing functionality | Medium | Large | 11–13, 27 |
| 29 | Detect nested ChronoVault archives in source scans | Reliability | Medium | Small | 5 eventually supersedes part |
| 30 | Add controlled GUI cancellation | UX / Reliability | Medium | Medium | 1, 2, 4, 26 |
| 31 | Introduce a unified per-run path/configuration context | Architecture / UX | High | Medium | 12, 14 |
| 32 | Add GUI review, duplicate, and repair workflows | Feature / UX | Medium | Very large | 11, 18, 31 |
| 33 | Build automated unit and migration tests | Testing | High | Medium | Can begin immediately |
| 34 | Build isolated failure-injection integration tests | Testing | High | Large | Design alongside 1–7 |
| 35 | Make generated fixtures deterministic and safely cleanable | Testing | Medium | Small | Supports 33, 34 |
| 36 | Repair the contained manual test workflow | Bug / Testing | Medium | Tiny | None |
| 37 | Add a dependency manifest and CI baseline | Architecture / Testing | Medium | Medium | 33; runtime-policy decision |

## Backlog details

### 1. Recoverable Importer state transition

- **Why it matters:** Importer currently copies the destination, marks the source `imported`, and only then inserts the archive record. A crash, SQL error, or ignored insert can leave a real file and imported source row without a matching archive record.
- **Likely scope:** `importer/importer.py`, both database schemas, restart/reconciliation behavior.
- **Dependencies / sequencing:** Design with items 2 and 3; schema support from 13 is preferable.
- **Evidence/status:** Confirmed current issue; tracked in `roadmap.md`.

### 2. Temporary-copy, verification, and atomic finalize

- **Why it matters:** Large files are written directly under their final names. An interrupted copy can leave an incomplete file that looks complete. Copy to a temporary sibling, flush/close, verify size and preferably hash, then atomically rename.
- **Likely scope:** Importer copy helper and future extraction/correction utilities.
- **Dependencies / sequencing:** Can be implemented before the broader transaction protocol and reused by it.
- **Evidence/status:** Confirmed current issue; tracked in `roadmap.md`.

### 3. Detect archive-row and destination collisions explicitly

- **Why it matters:** Destination allocation checks disk state only, while archive inserts use `INSERT OR IGNORE` without checking whether a row was inserted. A stale database row or path conflict can therefore be silently accepted.
- **Likely scope:** Importer destination allocation and `add_to_archive_database()`.
- **Dependencies / sequencing:** Useful quick safety improvement before item 1.
- **Evidence/status:** Confirmed current issue; the general collision risk is tracked, but the silent ignored insert deserves explicit treatment.

### 4. Make date correction recoverable and validated

- **Why it matters:** `write_data` moves the archive file before committing the database update. A later failure strands the file. Re-correcting to its current date can also create an unnecessary suffixed name, and arbitrary dates are not plausibility-checked.
- **Likely scope:** `write_data/write_data.py`, correction schema, retrieve/write tests.
- **Dependencies / sequencing:** Share the recovery protocol with item 1; path normalization from 12 helps. Preserve correction history rather than only the latest value if practical.
- **Evidence/status:** Confirmed current issue; non-atomic correction is tracked, while repeat-correction and validation behavior are audit findings.

### 5. Prevent duplicates already present in the archive

- **Why it matters:** Source deduplication only compares rows inside `located_files.db`. Rescanning read-only media can copy content that already exists in the persistent archive.
- **Likely scope:** Condition Database, Importer, archive database, canonical-date policy.
- **Dependencies / sequencing:** Requires trustworthy hashes from item 6 and a decision about whether a known archive date—especially a user-corrected one—should be reused.
- **Evidence/status:** Confirmed missing core protection; high-priority roadmap item.

### 6. Add hash-cache freshness and invalidation

- **Why it matters:** Condition Database, Audit Archive, and Duplicate Finder trust non-null cached hashes without recording the size/mtime fingerprint they describe. Replaced-in-place files can be treated as their former content.
- **Likely scope:** Both schemas and all three hash consumers.
- **Dependencies / sequencing:** Establish one shared fingerprint/invalidation rule before archive-wide deduplication.
- **Evidence/status:** Confirmed current issue; tracked in `roadmap.md`.

### 7. Refresh and reconcile previously indexed source paths

- **Why it matters:** Indexer uses `INSERT OR IGNORE`, so rediscovery does not update size or timestamps. Deleted paths also remain eligible, while already-conditioned rows are not automatically reconditioned after content changes.
- **Likely scope:** Indexer, source schema, Condition Database invalidation, run summaries.
- **Dependencies / sequencing:** Coordinate with hash freshness and migrations.
- **Evidence/status:** Confirmed current issue; refresh is tracked, but a complete last-seen/missing/changed lifecycle remains undesigned.

### 8. Establish one authoritative date-decision contract

- **Why it matters:** Condition Database stores a date result, but Importer recomputes it and does not enable OCR. The same source can therefore be conditioned with one result and archived under another.
- **Likely scope:** `condition_database`, `importer`, `analyze_date`, schema fields for analyzer/config version or invalidation.
- **Dependencies / sequencing:** Decide whether conditioning owns the persisted decision or merely caches evidence. Exact-duration, timezone, and XMP work should inform the contract.
- **Evidence/status:** Confirmed architectural inconsistency; tracked in `roadmap.md`.

### 9. Establish one classification/import eligibility contract

- **Why it matters:** Classify Media records `media_excluded` and sets `status='excluded'`, but Importer selects excluded rows and does not consult that flag. A classifier exclusion is not a durable veto.
- **Likely scope:** Classify Media, Importer, status definitions, database schema.
- **Dependencies / sequencing:** Define config-driven exclusion versus human rejection before candidate review.
- **Evidence/status:** Confirmed current issue; tracked in `roadmap.md`.

### 10. Make source duplicate grouping deterministic and rerunnable

- **Why it matters:** The retained member of a hash group depends on database return order because there is no `ORDER BY`. The duplicate grouping pass is also skipped entirely when no unconditioned rows are found.
- **Likely scope:** `condition_database/condition_database.py`, duplicate provenance and override behavior.
- **Dependencies / sequencing:** Apply freshness rules first or concurrently.
- **Evidence/status:** Confirmed implementation issue; determinism and the skipped rerun behavior are audit findings not clearly isolated in the roadmap.

### 11. Add candidate and duplicate decision lifecycle

- **Why it matters:** Ambiguous classification and duplicate groups cannot be approved, rejected, or overridden through a durable human-review state. Current `excluded` and `duplicate` values conflate processing outcomes with decisions.
- **Likely scope:** Source schema, read/write review boundary, terminal tooling, later GUI.
- **Dependencies / sequencing:** Classification ownership and schema migration must be settled first.
- **Evidence/status:** Missing planned feature; designed conceptually in the roadmap and schema documentation.

### 12. Make paths independent of process working directory

- **Why it matters:** Stored and configured relative paths can resolve differently depending on where a script is launched. This affects databases, archive files, corrections, reports, and direct library use.
- **Likely scope:** All CLIs, both databases, configuration loading, retrieve/write functions, migration strategy.
- **Dependencies / sequencing:** Decide which paths are canonical absolute identities and which intentionally remain portable relative paths.
- **Evidence/status:** Confirmed cross-module weakness; tracked in `roadmap.md`.

### 13. Introduce schema versions and ordered migrations

- **Why it matters:** Multiple tools independently add columns when first run. There is no version, migration order, constraint validation, or reliable way to distinguish a compatible database from an unexpected SQLite file.
- **Likely scope:** Shared database/migration layer and both schemas.
- **Dependencies / sequencing:** Foundational for state protocols, review, freshness metadata, and extraction provenance.
- **Evidence/status:** Confirmed architectural weakness; tracked in `roadmap.md`.

### 14. Add database/configuration preflight checks

- **Why it matters:** Several tools can create an empty SQLite file when given the wrong path and then fail because the expected table is absent. Path/config drift is detected late.
- **Likely scope:** Shared CLI preflight helpers, each tool’s entry point, GUI diagnostics.
- **Dependencies / sequencing:** A small protective step that need not wait for central migrations.
- **Evidence/status:** Confirmed behavior in schema review; only indirectly represented in the roadmap.

### 15. Fix Audit Archive extension-filter false positives

- **Why it matters:** Disk discovery is filtered by extension, while database rows are not. A documented file with a currently excluded extension can be reported missing even though it exists.
- **Likely scope:** `audit_archive/audit_archive.py` and report tests.
- **Dependencies / sequencing:** Independent quick fix; define whether filtering limits analysis or filesystem existence checks.
- **Evidence/status:** Confirmed current bug; tracked in `roadmap.md`.

### 16. Correct Audit Archive layout recognition

- **Why it matters:** Placement checking assumes the first three relative components are the date hierarchy and declines to evaluate shallow paths. Nonstandard/deeper layouts can be misclassified or silently treated as acceptable.
- **Likely scope:** Audit path parser and tests for dated, review, corrected, shallow, and nested layouts.
- **Dependencies / sequencing:** Easier after canonical path rules, but can be fixed independently.
- **Evidence/status:** Confirmed current issue; tracked in `roadmap.md`.

### 17. Use shared date analysis for audit recommendations

- **Why it matters:** Audit’s undocumented-file recommendation uses a limited EXIF/filesystem heuristic instead of `analyze_date`, so it ignores GPS, XMP, TIFF, filename, and folder evidence.
- **Likely scope:** Audit Archive and shared analyzer invocation.
- **Dependencies / sequencing:** Align with the authoritative-date decision in item 8.
- **Evidence/status:** Confirmed divergence; tracked in `roadmap.md`.

### 18. Add dry-run archive reconciliation and repair

- **Why it matters:** Audit reports drift but cannot safely repair missing records, stale paths, misplaced files, or collisions. Manual repair risks making the persistent archive record worse.
- **Likely scope:** Audit output schema, explicit write-side repair tool, operation log and rollback/restart behavior.
- **Dependencies / sequencing:** Build only after identity, hash, path, and transaction rules are dependable.
- **Evidence/status:** Missing planned capability; tracked in `roadmap.md`.

### 19. Use exact elapsed time for date agreement

- **Why it matters:** `abs(timedelta.days)` floors to an integer. The configured threshold therefore is not a precise duration and can classify nearly two-day differences as within one day.
- **Likely scope:** `analyze_date/analyze_date.py` and scoring tests.
- **Dependencies / sequencing:** None.
- **Evidence/status:** Confirmed current bug; tracked in `roadmap.md`.

### 20. Define and implement timezone-aware date comparison

- **Why it matters:** GPS is UTC-like, ordinary EXIF is normally camera-local, and XMP offsets are currently discarded without conversion. Comparisons can penalize matching evidence or file media under the wrong calendar day.
- **Likely scope:** Date value representation, GPS/XMP extractors, analyzer, database serialization, tests.
- **Dependencies / sequencing:** Define how aware and naive signals coexist without inventing a timezone. Preferably precede new high-confidence format signals.
- **Evidence/status:** Confirmed limitation; tracked in `roadmap.md`.

### 21. Read XMP RDF attribute-form dates

- **Why it matters:** The parser reads element text only; common XMP using attributes on `rdf:Description` can be missed.
- **Likely scope:** `analyze_date/image_tools/xmp_tools.py` and fixture tests.
- **Dependencies / sequencing:** Keep timezone-offset handling compatible with item 20.
- **Evidence/status:** Confirmed parser limitation; tracked in `roadmap.md`.

### 22. Run OCR only when stronger evidence is inadequate

- **Why it matters:** When enabled, Condition Database attempts expensive OCR for every supported image, even when reliable GPS or EXIF evidence already exists.
- **Likely scope:** Analyzer orchestration or a two-pass Condition Database policy.
- **Dependencies / sequencing:** Define whether OCR is evidence collection or review escalation under item 8.
- **Evidence/status:** Confirmed behavior; tracked in `roadmap.md`.

### 23. Implement audio-specific date extractors

- **Why it matters:** Audio currently receives only filename, folder, and filesystem evidence. ID3, BWF, QuickTime/M4A, and Vorbis metadata could materially improve recording-date accuracy.
- **Likely scope:** `analyze_date/audio_tools`, dependencies, fixtures, source confidence definitions.
- **Dependencies / sequencing:** Stabilize date ownership, duration comparison, and timezone handling first.
- **Evidence/status:** Missing planned feature; placeholder package and roadmap exist.

### 24. Implement video-specific date extractors

- **Why it matters:** Video container dates and camera metadata are ignored, leaving many videos in low-confidence review or incorrectly using filesystem dates.
- **Likely scope:** `video_tools`, MP4/QuickTime/MKV parsing, possibly ExifTool or ffprobe policy.
- **Dependencies / sequencing:** Same date-contract prerequisites as audio.
- **Evidence/status:** Missing planned feature; placeholder package and roadmap exist.

### 25. Support broader still metadata and sidecars

- **Why it matters:** HEIC/HEIF, manufacturer RAW, IPTC, external XMP, THM pairing, PNG/WebP metadata, and Takeout JSON remain unsupported. These are common in real personal-media collections.
- **Likely scope:** Multiple extractors, sidecar association/provenance, dependencies, review UI.
- **Dependencies / sequencing:** Treat as a planned program, not one patch. Candidate review and timezone policy should exist first.
- **Evidence/status:** Missing planned feature set; tracked in `Date_signals.md` and the roadmap.

### 26. Persist Indexer discovery incrementally

- **Why it matters:** Indexer accumulates discovered paths in memory before storing them. If a long scan is killed or the machine fails during discovery, the scan’s collected work is lost despite later batched database writes.
- **Likely scope:** `indexer/indexer.py`, progress/checkpoint model, interruption tests.
- **Dependencies / sequencing:** Useful before controlled cancellation, though not dependent on it.
- **Evidence/status:** Confirmed review finding; not clearly identified in the current roadmap.

### 27. Correct and verify archive-container listing state

- **Why it matters:** The 500-member cap is stored as though it were the match count, earlier failure notes can be cleared, and successful ISO listing still lacks a real-file verification. Existing listed archives are not refreshed.
- **Likely scope:** Indexer’s ZIP/TAR/ISO handlers, `located_archives`, reports, fixtures.
- **Dependencies / sequencing:** Decide complete-count versus capped-sample fields; then decide whether RAR/7z dependencies are worthwhile.
- **Evidence/status:** Mostly confirmed issues already tracked; successful ISO verification is explicitly outstanding.

### 28. Add safely staged archive-member extraction

- **Why it matters:** Archive members are discoverable but cannot enter the media workflow. Extraction introduces path traversal, password, provenance, cleanup, and duplicate risks.
- **Likely scope:** Indexer/archive tools, staging area, candidate workflow, source schema.
- **Dependencies / sequencing:** Candidate approval, migrations, canonical paths, and archive-container reliability should come first.
- **Evidence/status:** Missing planned feature; roadmap has a safety-oriented design outline.

### 29. Detect nested ChronoVault archives in source scans

- **Why it matters:** The source guard checks only for `archive_database.db` directly under the chosen root. Selecting a broader parent containing an archive can re-index archived files and create repeated copies.
- **Likely scope:** Indexer preflight and GUI warning.
- **Dependencies / sequencing:** Archive-wide hash prevention later provides a second defense.
- **Evidence/status:** Confirmed known limitation; tracked in `roadmap.md`.

### 30. Add controlled GUI cancellation

- **Why it matters:** There is no Stop button. Closing the window does not implement a coordinated cancellation protocol, and killing a copy can expose the partial-operation risks above.
- **Likely scope:** `gui/chronovault_gui.py`, subprocess signaling, tool cancellation contracts.
- **Dependencies / sequencing:** Add only after the affected tools define safe interruption and restart behavior.
- **Evidence/status:** Confirmed missing capability. The roadmap wording implying an existing abrupt stop action is inaccurate.

### 31. Introduce a unified per-run path/configuration context

- **Why it matters:** The GUI synchronizes `archive_root` for selected tools but does not synchronize source database paths. Selecting a source folder affects only Indexer; Classify Media and Condition Database may silently use another configured database.
- **Likely scope:** GUI, CLI arguments/config loading, diagnostics, run profiles.
- **Dependencies / sequencing:** Build on canonical path semantics and preflight checks.
- **Evidence/status:** Confirmed architectural limitation; partly tracked as configuration drift.

### 32. Add GUI review, duplicate, and repair workflows

- **Why it matters:** The GUI is presently a launcher. Users cannot review uncertain dates, candidate media, duplicate groups, or proposed audit repairs without terminal/manual workflows.
- **Likely scope:** Qt UI, read-only query APIs, explicit mutation APIs, thumbnails/search.
- **Dependencies / sequencing:** Requires candidate lifecycle and safe repair boundaries; should continue reusing CLI/domain logic.
- **Evidence/status:** Missing planned feature; described in longer-term roadmap work.

### 33. Build automated unit and migration tests

- **Why it matters:** Date scoring, parsers, status selection, migrations, and path handling lack a formal assertion-based suite. Regressions in core decisions are therefore easy to miss.
- **Likely scope:** New test runner and isolated fixtures across date, database, classifier, and audit logic.
- **Dependencies / sequencing:** Can start immediately and grow alongside every backlog item.
- **Evidence/status:** Confirmed testing gap; tracked in `roadmap.md`.

### 34. Build isolated failure-injection integration tests

- **Why it matters:** The most dangerous failures occur between copy/move and database commits. Happy-path manual tests cannot establish recovery guarantees.
- **Likely scope:** Disposable source/archive databases, monkeypatched copy/rename/commit failures, restart assertions.
- **Dependencies / sequencing:** Design together with items 1–7; tests can first capture unsafe current behavior.
- **Evidence/status:** Missing planned test coverage; tracked in `roadmap.md`.

### 35. Make generated fixtures deterministic and safely cleanable

- **Why it matters:** Seeded randomness does not make date-relative fixtures stable because they depend on the current clock. Existing output trees are not cleaned, so stale files can contaminate results.
- **Likely scope:** `generate_test_data`, reference-time option, guarded clean mode.
- **Dependencies / sequencing:** Supports unit and integration suites.
- **Evidence/status:** Confirmed limitation; tracked in `roadmap.md`.

### 36. Repair the contained manual test workflow

- **Why it matters:** `chronovault.sh` invokes `test_retrieve_data.py` without its now-required config argument, so that menu action fails. Its prerequisite message also points to Importer option 5 even though Importer is option 6. `test_write_data.py` unnecessarily requires a pre-existing report that it immediately regenerates.
- **Likely scope:** `chronovault.sh`, `test_functions/test_write_data.py`, focused README text.
- **Dependencies / sequencing:** None.
- **Evidence/status:** Confirmed current bugs discovered during this review; absent from the roadmap.

### 37. Add a dependency manifest and CI baseline

- **Why it matters:** Runtime dependencies, optional groups, supported Python versions, and automated checks are informal. Reproducing a working development environment is harder than necessary.
- **Likely scope:** Packaging metadata, optional dependency groups, CI, lint/test commands.
- **Dependencies / sequencing:** Decide the supported runtime and external-tool policy; CI becomes more valuable once item 33 exists.
- **Evidence/status:** Missing planned infrastructure; tracked in `roadmap.md`.

## Quick wins

These are the Tiny/Small items that offer meaningful correctness or workflow value:

| # | Item | Criticality | Effort |
|---:|---|---|---|
| 3 | Detect archive-row and destination collisions explicitly | Critical | Small |
| 10 | Make source duplicate grouping deterministic and rerunnable | Medium | Small |
| 14 | Add database/configuration preflight checks | Medium | Small |
| 15 | Fix Audit Archive extension-filter false positives | Medium | Small |
| 16 | Correct Audit Archive layout recognition | Medium | Small |
| 19 | Use exact elapsed time for date agreement | Medium | Tiny |
| 21 | Read XMP RDF attribute-form dates | Medium | Small |
| 22 | Run OCR only when stronger evidence is inadequate | Medium | Small |
| 29 | Detect nested ChronoVault archives in source scans | Medium | Small |
| 35 | Make generated fixtures deterministic and safely cleanable | Medium | Small |
| 36 | Repair the contained manual test workflow | Medium | Tiny |

Items 3, 14, and 36 are especially self-contained. Items 10, 21, and 22 benefit from adding focused tests at the same time.

## High-impact work

These are all Critical or High items, with their original criticality unchanged:

| # | Item | Criticality | Effort |
|---:|---|---|---|
| 1 | Recoverable Importer state transition | Critical | Large |
| 2 | Temporary-copy, verification, and atomic finalize | Critical | Medium |
| 3 | Detect archive-row and destination collisions explicitly | Critical | Small |
| 4 | Make date correction recoverable and validated | Critical | Medium |
| 5 | Prevent duplicates already present in the archive | High | Large |
| 6 | Add hash-cache freshness and invalidation | High | Medium |
| 7 | Refresh and reconcile previously indexed source paths | High | Medium |
| 8 | Establish one authoritative date-decision contract | High | Large |
| 9 | Establish one classification/import eligibility contract | High | Medium |
| 12 | Make paths independent of process working directory | High | Large |
| 13 | Introduce schema versions and ordered migrations | High | Large |
| 18 | Add dry-run archive reconciliation and repair | High | Large |
| 20 | Define and implement timezone-aware date comparison | High | Large |
| 31 | Introduce a unified per-run path/configuration context | High | Medium |
| 33 | Build automated unit and migration tests | High | Medium |
| 34 | Build isolated failure-injection integration tests | High | Large |

The core root-cause clusters are:

- **Operation recovery:** 1–4, 18, 30, 34.
- **File identity and freshness:** 5–7, 10, 18, 29.
- **Shared decision ownership:** 8–11, 17, 22.
- **Path and schema authority:** 12–14, 18, 31.
- **Date correctness foundation:** 19–25.

## Larger projects and features

These Large/Very large items should be planned as projects:

| # | Item | Criticality | Effort |
|---:|---|---|---|
| 1 | Recoverable Importer state transition | Critical | Large |
| 5 | Prevent duplicates already present in the archive | High | Large |
| 8 | Establish one authoritative date-decision contract | High | Large |
| 11 | Add candidate and duplicate decision lifecycle | Medium | Large |
| 12 | Make paths independent of process working directory | High | Large |
| 13 | Introduce schema versions and ordered migrations | High | Large |
| 18 | Add dry-run archive reconciliation and repair | High | Large |
| 20 | Define and implement timezone-aware date comparison | High | Large |
| 23 | Implement audio-specific date extractors | Medium | Large |
| 24 | Implement video-specific date extractors | Medium | Large |
| 25 | Support broader still metadata and sidecars | Medium | Very large |
| 28 | Add safely staged archive-member extraction | Medium | Large |
| 32 | Add GUI review, duplicate, and repair workflows | Medium | Very large |
| 34 | Build isolated failure-injection integration tests | High | Large |

## Roadmap reconciliation

The roadmap is generally accurate and unusually candid. No whole roadmap section appears obsolete, but several details need refinement.

### Already implemented or accurately marked

- Filename and folder date signals, French month folders, hidden-directory indexing, media classification, GUI archive-path synchronization, correction metadata, and archive-source warnings are already implemented and correctly described as current.
- Archive extraction, candidate review, audio/video metadata, audit repair, labels, browser UI, and source cleanup are correctly described as unimplemented.
- The roadmap correctly distinguishes the 500-entry archive-member list from a true total and correctly notes that ISO success still needs real-file verification.

### Contradicted or misleading

- The roadmap says the GUI subprocess stop action is abrupt and that running tools can be stopped by terminating their process. The application has no Stop control; only external termination or closing the application is available.
- Any wording suggesting Indexer’s batch commits preserve partially completed discovery should be qualified: discovered paths are accumulated before storage, so interruption during discovery loses that run’s collected scan results.
- “Condition Database marks duplicates” needs the caveat that its duplicate pass does not run when there are no newly unconditioned rows.

### Duplicated roadmap material

Some repetition is useful for priority grouping, but these are the same underlying work:

- Non-atomic import, partial copies, retries, failure injection, and GUI cancellation are facets of one recoverable-operation protocol.
- Archive duplicate prevention and hash-cache invalidation depend on the same stable content-identity model.
- Condition/Importer date divergence, OCR policy, and audit’s separate heuristic are manifestations of unclear date-decision ownership.
- Classification ownership and candidate review share the same unresolved eligibility/status model.
- Path portability, GUI config drift, and relative stored archive paths share the same path-authority problem.

### Important issues missing or insufficiently explicit

- Silent `INSERT OR IGNORE` failure when inserting archive rows.
- Unnecessary suffixing when correcting a file again to its existing date folder.
- Lack of correction-date validation and correction history.
- Non-deterministic duplicate keeper selection.
- Duplicate grouping being skipped when no new conditioning work exists.
- Indexer’s pre-storage in-memory discovery window.
- Wrong database paths creating empty SQLite files before failing.
- The broken `chronovault.sh` retrieve-data invocation and stale option number.
- `test_write_data.py` requiring an old audit report before producing a fresh one.
- Duplicate/audit cached file sizes and hashes having no freshness fingerprint.
- Per-file analysis or database exceptions potentially aborting an Importer run without a structured failure record.

One ancillary documentation issue also surfaced: `CHRONOVAULT_HANDOFF.md` says `recontext.sh` is absent and names an older baseline as current, but the script and newer `context-baseline-2026-09-26` tag now exist. That handoff should eventually be refreshed.
