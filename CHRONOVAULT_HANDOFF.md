# ChronoVault Persistent Handoff

## Purpose and authority

This file preserves project context that was expensive to reconstruct during the full repository and documentation audit. It records rationale, non-obvious interactions, and unresolved architectural choices; it is not a project overview, module reference, backlog, or agent routing guide.

Use current sources in this order:

1. implementation for actual behavior;
2. the audited module and root documentation;
3. this handoff for cross-cutting context and rationale.

Start with [AGENTS.md](AGENTS.md) to locate the minimum relevant documentation. Use [README.md](README.md) for the project overview, [Database_schema.md](Database_schema.md) for schema/ownership, [Date_signals.md](Date_signals.md) for date behavior, and [roadmap.md](roadmap.md) for maintained risks and future work.

## Recontextualization system

- [AGENTS.md](AGENTS.md) is the navigation and task-routing map. It tells a new agent what to read without scanning the repository.
- `CHRONOVAULT_HANDOFF.md` preserves conclusions and rationale that would otherwise require reconstructing several modules or old conversations.
- Annotated Git tags named `context-baseline-*` mark reviewed checkpoints where code, documentation, and agent context were intentionally reconciled. `context-baseline-2026-09` is the current audited checkpoint.
- The intended `recontext.sh` workflow identifies the newest baseline tag and summarizes changes since it, so a future agent can focus on post-audit drift. The script is not present in the repository at this checkpoint; until it exists, inspect the newest tag and compare it with `HEAD` using Git directly.
- After locating changes since the baseline, load only the relevant documentation and implementation progressively. Do not reread every README or source file for a narrow task.

Baseline tags are context checkpoints, not product releases and not proof that every known issue is fixed.

## Durable design intent

### Small tools, deliberate reuse

ChronoVault grew as a sequence of small CLI tools with explicit responsibilities. The GUI is intentionally an orchestration layer over those tools. Avoid creating parallel GUI implementations of pipeline behavior.

The project resists premature abstraction, but not reuse itself. `analyze_date` and the Qt-free GUI support code were extracted after concrete reuse or testability needs appeared. Prefer the existing boundary first; introduce new shared machinery only when multiple real consumers justify it.

### Preservation means source preservation, not universal read-only behavior

The central safety promise is that normal processing does not delete or move original source media. ChronoVault legitimately writes inventories, reports, cached metadata, configuration state, archive copies, and archive corrections. Any future source-cleanup feature must be a separate, guarded workflow rather than an implicit extension of import.

### Explainability and uncertainty are product behavior

Dates and media classification retain evidence, scores/confidence, and reasons. Weak date evidence is surfaced through `_review_needed/` instead of being silently promoted to a fact. Manual date correction records a new decision alongside the original algorithmic evidence rather than overwriting it.

This provenance is not incidental schema baggage. Preserve it when changing analysis, review, audit, or UI behavior.

### Conservative inclusion is intentional

Classify Media is designed to avoid false negatives: a stripped personal photo or scan should not disappear merely because it lacks camera metadata. Ambiguous material remains eligible until a human-review mechanism exists. More aggressive exclusion changes the product's safety posture and must be considered together with Importer and future candidate review.

### Mounted storage is the present integration boundary

The current local-first model treats removable disks, NAS shares, and cloud-synchronized or mounted storage as filesystem trees. Bespoke cloud APIs have not been established as an architectural requirement. Preserve portability across changing mount paths when designing path behavior.

## Expensive-to-rediscover interactions

### The two databases have different lifetimes

`located_files.db` is a rebuildable source inventory; `<archive_root>/archive_database.db` is the persistent record of the archive. Their relationships are conventions, not enforced foreign keys or a shared transaction. A change to a status, path, hash, or date field often has several owners and consumers, so [Database_schema.md](Database_schema.md) must be read before treating one module's interpretation as the whole contract.

### Conditioning is visibility and source deduplication, not an Importer cache

Condition Database hashes and dates eligible inventory rows and marks duplicates within that inventory. Importer currently recomputes date evidence and does not consume the stored conditioned result. This means the two stages can disagree—especially when Condition Database enables OCR, which Importer does not.

Any attempt to remove this duplication must first decide which stage owns the authoritative import decision, how older conditioned rows are invalidated, and how configuration differences are represented. It is not a simple optimization.

### Classification and import eligibility do not yet share one owner

Classify Media records its own exclusion provenance, while Importer selects and re-evaluates both `located` and `excluded` rows using separate filters. A classifier exclusion is therefore not a durable veto. Treat changes here as a cross-module policy decision rather than a local status tweak.

### Review is split deliberately into read and write capabilities

`retrieve_data` returns UI-neutral, serializable records and must remain read-only. `write_data` is the explicit mutating boundary: it moves an eligible archive file, records correction fields, and preserves the analyzer's original result. Audit Archive gives the user-corrected date precedence when evaluating placement.

Changing any part of that chain requires reviewing all three modules and the archive schema together.

### Audit and duplicate reporting share cached hashes, not a repair workflow

Audit Archive reconciles disk and database state and may populate hashes that Duplicate Finder reuses. Duplicate Finder reports identical content but does not choose a canonical copy. Neither tool is an archive repair engine, and cached hashes currently have no freshness contract. A future repair or duplicate-resolution workflow needs explicit human decisions and recoverable writes rather than silently acting on reports.

### Date analysis is generic at the scorer, type-specific at evidence collection

The combination model accepts named evidence uniformly, while dispatch decides which extractors apply to a file type. Filename and folder evidence applies broadly; image metadata has implemented extractors; audio/video packages remain placeholders. New signals should normally enter through an extractor/dispatch point with preserved provenance, not as special cases in scoring or Importer.

Condition Database and Importer consume the shared analyzer, but Audit Archive's undocumented-file recommendation uses a separate limited heuristic. Cross-tool consistency work must account for that third path.

### Paths are data, configuration, and runtime context

Many configured and stored paths can be relative to the process working directory. The GUI synchronizes selected `archive_root` values immediately before launching mapped tools, but it does not establish one universal configuration store or synchronize every database path. Config files may point at real personal media and are operational state, not disposable examples.

Path-resolution changes must consider existing database rows, terminal launches, GUI launches, removable-media mount changes, and the contained `chronovault.sh` workflow together.

### Archive containers are discovered, not ingested

Indexer records archive containers separately and can list matching members without extraction. Those rows are not media rows, and archive members do not enter the import pipeline. Extraction was intentionally deferred until safe staging, provenance, and candidate review have a coherent design.

## Architectural questions still open

Detailed priorities and known bugs belong in [roadmap.md](roadmap.md). The following questions are worth preserving because they shape multiple future changes:

- Should Importer consume conditioned decisions, or should recomputation remain intentional? What invalidates a stored decision?
- Which component owns final inclusion when classifier evidence and Importer filters disagree?
- Where should archive-wide hash checking occur, and which archived date becomes authoritative for a known-content match?
- What recoverable transaction model should coordinate copies/moves with two independent SQLite databases?
- How should schema versioning replace the current tool-owned, add-column-on-demand migration pattern?
- What path model supports both portable relative configurations and cwd-independent operation?
- Should Audit Archive reuse the shared date analyzer, and how should audit recommendations differ from import decisions?
- What is the minimal candidate-review contract shared by ambiguous classification and extracted archive members?
- How should cached hash freshness be represented without forcing unnecessary rehashing of large media?

Do not resolve these questions from historical prose alone. Check current source and roadmap status before proposing a design.

## Working context worth retaining

- Development has been most successful in small, independently verified steps. Broad untested rewrites conflict with the established project approach.
- Prefer real execution and observable database/report results over reasoning from code alone. Use generated disposable data; never exercise mutating review paths against personal archives by default.
- Use `python3` explicitly. The repository is not packaged and currently has no formal automated test suite or CI, so validation is module-specific and manual.
- Preserve unrelated working-tree and configuration changes. Do not normalize paths or reset configs as incidental cleanup.
- When behavior changes, update the owning module documentation and only the cross-cutting documents whose contracts or status actually changed. Link rather than duplicate detail.

## Historical material deliberately retired

Earlier versions of this file contained account-migration notes, assistant memory disclaimers, sandbox-reset caveats, apologies, exhaustive feature brainstorming, detailed OCR experiments, stale “next tasks,” and appended session devnotes. Those were useful during an unstable handoff but are not durable project context.

Detailed algorithms and current status now belong to the audited documentation. Old claims such as “the GUI is not built,” “French folder parsing is pending,” or “hidden-folder behavior is unverified” are obsolete and must not be revived.
