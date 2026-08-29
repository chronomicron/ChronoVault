# ChronoVault — Project Handoff Document

**Purpose:** Context transfer for migrating this project to a new Claude account. Codebase and READMEs are moving via GitHub — this document deliberately does NOT re-document anything already covered there. It captures everything that exists only in conversation history: decisions, rationale, preferences, unbuilt ideas, and open threads.

**Status:** v1, single-pass generation. See "Gaps" (Section 9) for reliability caveats given this session included multiple sandbox resets.

---

## 1. Project Purpose & Scope

ChronoVault consolidates media scattered across old hard drives, USB keys, NAS, and cloud storage into one organized, chronological, locally-owned archive — originally scoped as a personal photo/video archiver.

**How the framing evolved:**
- Started as: "find my scattered photos/videos, organize them by date."
- Expanded to: any file type at all (the user's own real secondary use case is archiving **MP3 recordings of meetings**; also mentioned Word docs and PDFs from school). The core pipeline (hashing, duplicate detection, filename/path date analysis) was deliberately built type-independent from early on; only the *date-signal extraction* layer is type-specific, and it's designed to grow one file-type module at a time.
- Long-term ambition: AI-assisted labeling (people, places, things), a searchable gallery GUI, and eventually multi-language support (English/French/Japanese) for both file-naming conventions and the GUI itself.
- The user has explicitly floated (not committed to) this architecture being generically useful *outside* ChronoVault too — e.g., `analyze_date` as a standalone tool "someone else might want to run in a script on their own files."

---

## 2. Key Decisions & Rationale

*(Decision — Why, not just what.)*

- **Small independent CLI tools, each with its own `config.json`**, rather than one monolithic app. Deliberate "baby steps" philosophy: build one small tested piece, then the next.
- **No premature shared libraries.** Small logic (e.g. SHA-256 hashing) is deliberately duplicated across tools rather than factored into a shared utils module — until a *real, proven* need exists. Exception made for `analyze_date` once it needed to serve `retrieve_data`/`write_data` AND a future GUI/webapp identically — a legitimate case, not a violation of the philosophy.
- **`analyze_date`'s "evidence in, scored answer out" pattern** was explicitly designed to be reused later for AI labeling — not just a date-specific convenience.
- **Signals-list combination design**: any number of date-evidence signals are combined generically (pick highest-confidence primary, adjust for agreement/disagreement) rather than hardcoded pairwise logic. This is *why* adding GPS, XMP, TIFF, filename, and folder-path signals later required zero changes to the actual scoring function — only to signal-gathering.
- **Confidence scoring (0–100) instead of binary certain/uncertain** — preserves nuance and allows tuning.
- **Low-confidence files routed to `archive/_review_needed/`** instead of guessed into a possibly-wrong date folder — avoids silent misplacement.
- **`retrieve_data` (read-only) / `write_data` (mutating) kept as separate modules.** Read-only consumers can never accidentally mutate anything. Both designed to be **UI-agnostic** — usable identically by a terminal script, a future Qt desktop app, or a future web app. JSON-serializability of `retrieve_data`'s output was explicitly tested and treated as a hard design goal, not incidental.
- **`write_data`'s uncertainty guardrail**: only allows correcting a file if it's currently `date_uncertain=1`, OR it was already corrected before (so the user can fix their own past mistake, but can't accidentally overwrite a confident algorithmic date). This was refined mid-session after realizing a naive "block if not uncertain" rule would lock out fixing one's own prior correction.
- **Corrections never overwrite original algorithmic evidence.** `user_corrected_date` is stored *alongside* `date_taken`/`date_source`/`confidence`/`date_reason`, never replacing them — preserves a full audit trail.
- **Audit Archive's placement check was patched to prefer `user_corrected_date` over `date_taken`** when present. This fixed a real, discovered-live bug: corrected files were being flagged as "misplaced" because Audit only ever checked the original (frozen) `date_taken`.
- **Hand-rolled EXIF/XMP writers instead of Pillow's convenience classes** (`Image.Exif()`, `getxmp()`). Real bug found: `Image.Exif()`'s sub-IFD writing worked in the sandbox but silently failed on the user's actual machine (different Pillow version) — files saved with no error but zero readable EXIF. This became a standing lesson applied repeatedly afterward, including choosing hand-rolled XML parsing over `getxmp()` for XMP (also avoids `getxmp()`'s namespace-flattening collision risk).
- **OCR is opt-in only** (`try_ocr` flag), never automatic — it's slow (multiple corners × rotations × preprocessing variants) and only useful for files with weak/no other evidence.
- **OCR crop geometry is wide-but-short (95% width, 25% height), not square** — found empirically that a square crop diluted the tiny stamp text with too much unrelated photo content.
- **OCR tries 4 rotations per corner** — added after real examples (including a Japanese kanji date stamp, rotated 90°) failed under the original fixed-orientation approach.
- **OCR uses Otsu auto-thresholding** — added specifically to handle small, low-contrast dot-matrix/CCTV-style stamps that were otherwise unreadable.
- **OCR requires per-word confidence (`image_to_data`, not `image_to_string`)**, plus a *stricter* confidence threshold for punctuation-free matches (65 vs. 40) — found necessary after a bare-digit misread (`24 11 26`) scored almost identically to a genuinely correct punctuated match (`07.20.2010`). Punctuation is treated as real structural evidence a match is actually a date.
- **A structurally-valid-but-implausible-year OCR match stops the search entirely**, rather than falling through to a weaker pattern — fixed a real bug where rejecting one bad reading (`1024`) let the code accept an even-worse one from leftover digits.
- **Colon deliberately excluded as an OCR date separator** — real user-provided examples showed colons in stamps always mean *time*, not date; treating one as a date risked a confident false match.
- **File-type dispatch in `analyze_date`** (`JPEG_LIKE_EXTENSIONS`, `TIFF_EXTENSIONS`). `.raw` is deliberately **not** auto-mapped to TIFF — Adobe DNG is TIFF-based but Canon CR2/Nikon NEF/Sony ARW are not, and the extension alone can't tell you which. A caller must pass an explicit `file_type` override instead of the module guessing wrong.
- **`.thm` added to `JPEG_LIKE_EXTENSIONS`** — Canon sidecar thumbnails are structurally JPEGs, and `.thm` was already a recognized extension elsewhere in the project (Importer's thumbnail-exclusion filter).
- **`multi_tools/` created inside `analyze_date/`** for type-*independent* signals (filename, folder path) — distinct from `image_tools`/`audio_tools`/`video_tools`, which are type-*specific* "multitools" (see Terminology). This was placed at the project root once, mistakenly, and corrected to live inside `analyze_date/` after the user clarified "alongside `image_tools`."
- **Filename date parsing handles both US (MDY) and European (DMY) ordering** for bare numeric dates — a real gap the user caught after the first version only handled year-first patterns. Fixed with the same disambiguation-by-plausibility approach already proven in OCR: try both orderings, whichever produces a valid date wins; default to US ordering if both are valid.
- **Folder-path date signal given lower confidence (40) than filename (70)** — a folder named `2024` is as likely to reflect when files were *sorted* as when they were taken.
- **`condition_database` created as a new pre-import phase**: hashes, dates, and marks duplicates *before* copying to archive (Duplicate Finder previously only caught dupes *after* copying — wasted disk space and copy time).
- **`condition_database`'s duplicate handling**: keeps the *first* file in each hash-group `'located'`, marks the rest `'duplicate'` (skipped from import, never deleted/hidden). Explicitly flagged by the assistant as *a* design choice, not *the* correct one — open to a future duplicate-review GUI overriding it.
- **`condition_database` is idempotent via `confidence IS NULL`** as the "not yet conditioned" marker, rather than a separate flag column.
- **Type-independence was proven, not just claimed** — a plain `.txt` file was run through `condition_database` with zero special-casing, confirmed to hash and gracefully fall back to filesystem date correctly.
- **`chronovault.sh` restructured** from a simple 4-option launcher into a step-by-step *test runner* (cleanup → generate test data → index → condition → import → audit → find duplicates), explicitly to reduce the pain of repeated one-shot-then-interrupted sessions.
- **GPS given the highest confidence of any signal (98)** — comes from satellite time, independent of the camera's own (possibly wrong or never-set) clock.
- **XMP ModifyDate given deliberately low confidence (20)** — lower than filesystem fallback (30) — because it reflects a *later edit*, not original creation.
- **`analyze_date` itself was split into `image_tools/`** (one file per signal source) once the single file grew too large — the same "small tools, no premature abstraction" philosophy applied recursively, once real growth justified it.
- **`analyze_date` deliberately remains a pure Python library, never a CLI**, even though a full CLI design was extensively discussed (see Section 4/5). Importer calls it directly; a hypothetical future CLI would be a *separate*, additional consumer, not a replacement — the same principle as `retrieve_data`/`write_data` being usable from multiple front ends.
- **Multithreading (not multiprocessing) was the agreed approach** for any future `analyze_date` CLI — reasoning: OCR/hashing work is I/O-bound (subprocess/disk waits), so the GIL doesn't block the benefit; also avoids multiprocessing's pickling complexity.

---

## 3. My Working Preferences & Conventions

- **"Baby steps," explicitly and repeatedly demanded** — one small piece, tested, before the next. Don't batch multiple untested changes.
- **Deliver files via download, never inline code blocks** — established early after a described copy-paste indentation problem with the desktop app.
- **Every module gets a `README.md`.** Documentation is treated as seriously as code, and kept in sync as things change — the user has proactively asked for re-documentation passes multiple times.
- **Real execution + assertions before presenting anything**, not just written-and-assumed-correct. The user has repeatedly valued this rigor; several real bugs were caught this way (Pillow EXIF-writing reliability, US/European date ambiguity, a regex boundary gap, TIFF's missing `_getexif()`).
- **`python3` explicit, always** — never bare `python` in scripts. The user's own `.bashrc` alias doesn't apply in non-interactive script contexts; this was caught and fixed multiple times across different files.
- **Folder naming: lowercase, underscore-separated**, action-noun or noun-noun style (`indexer`, `audit_archive`, `duplicate_finder`, `analyze_date`, `generate_test_data`, `retrieve_data`, `write_data`, `condition_database`, `multi_tools`, `image_tools`).
- **Strongly dislikes over-engineering / premature abstraction.** Explicitly praised avoiding a "COM-model"-style over-engineered architecture early on. Direct quote (paraphrased from memory): *small independent apps is sufficient; if a process needs to be reproduced in two places, just implement it twice — no library needed yet.* Will accept an exception when a *real, proven* reuse need exists (e.g. `analyze_date` serving multiple consumers).
- **Appreciates small personal touches when relevant** — `EARLIEST_PLAUSIBLE_DATE = July 26, 1972` is the user's own birthday, an intentional Easter egg, explicitly commented in code as "a small tribute, not a bug."
- **Gets visibly frustrated by repeated interruptions/incomplete turns** — has used strong, direct language about this ("you owe me tokens," "3 days now," all-caps insistence). **Explicit standing instruction going forward: for any multi-step task, write an explicit checklist FIRST, mark items off as completed, and structure work assuming interruption is likely.** This pattern was well-received once adopted.
- **When told to stop fixing something and ship it as-is, stop immediately** — no relitigating or "just one more attempt." (Example: told explicitly not to chase an OCR digit-misread accuracy issue further.)
- **Frequently uploads real files** (past transcripts, real test images, real terminal output) rather than describing them from memory — always verify against the actual uploaded content rather than continuing from assumption.
- **Catches assistant errors directly and expects immediate acknowledgment + fix + retest**, not defensiveness or hedging.
- **Wants "what changed and why" summaries with test evidence shown**, not just claimed. Confidence tables and before/after comparisons are preferred over abstract prose description.
- **Wants direct yes/no confirmation when asking "is X done/ready"** — not vague reassurance.
- **Appreciates when the assistant proactively catches an adjacent bug** while working on something else (e.g., discovering TIFF's missing `_getexif()` while building TIFF support), rather than only reacting to explicitly reported bugs.
- Uses voice transcription for some messages (garbled phrasing occasionally) — be forgiving of typos/odd phrasing, infer intent.
- Values steady, visible incremental progress; explicitly praised good pacing at least once ("since we're going at a good pace").

---

## 4. Feature Ideas & Future Add-Ons (Exhaustive, Unfiltered)

*Everything ever mentioned, no matter how small or half-formed. Not prioritized here — that's Section 5.*

### Sources / Ingestion
- Cloud storage support via mounting (rclone for Google Drive/OneDrive; Dropbox has a native Linux client already; NAS/SMB via `mount -t cifs`) — "mount as a folder" preferred over bespoke API integrations.
- Scanning OS Trash/Recycle Bin folders (easy — it's just a folder, effectively already works).
- **True forensic undelete** from unallocated disk sectors — would wrap an external tool (PhotoRec, TestDisk), not be built from scratch. Never clarified whether this or the Trash-only case is what the user actually wants first.
- Hidden folder scanning — believed to already work via `Path.rglob`, never explicitly tested with a real hidden-folder case.

### Date-Determination Signals
- Filename parsing — **built**, with US/European disambiguation.
- Folder path parsing — **built**.
- `.THM` Canon sidecar files — **built** (added to `JPEG_LIKE_EXTENSIONS`).
- XMP metadata — **built**. IPTC (the older, related standard) was mentioned but never built.
- GPS EXIF timestamp — **built**.
- OCR corner date-stamp scanning — **built**, opt-in. Known unsolved: Japanese/kanji stamps (needs `tesseract-ocr-jpn` language pack, not installed, plus new kanji-aware parsing patterns), dot-matrix/CCTV-style fonts (improved via Otsu, still genuinely hard).
- ID3 tags for MP3 — **not built**, `audio_tools/` is a documented placeholder. Likely dependency: `mutagen`.
- MP4 container metadata (`creation_time` in the `mvhd` atom) — **not built**, `video_tools/` is a documented placeholder. Likely dependency: `mutagen` or `ffprobe`.
- PDF/document metadata — **not built, not even scoped as a folder** (`document_tools/` doesn't exist).
- **Adjacent-files date inference** — look at *other* files in the same folder and infer a date from their already-resolved dates. Discussed, not built. Explicitly flagged as architecturally different from every other signal (needs DB access to siblings' resolved dates, not just this file's own metadata). Open design question: lives in `multi_tools/` as a function accepting pre-fetched sibling data, or as a second pass inside `condition_database.py`?
- Visible rendered watermarks (as opposed to invisible XMP/IPTC metadata) — would need OCR-style scanning of wherever the watermark sits, not built.
- PNG's native `tIME` chunk — mentioned in passing as another metadata mechanism distinct from EXIF/XMP, not explored further.
- ICC color profile embedded creation date — mentioned in passing as very low-value, not pursued.

### Pipeline / Processing
- Pre-copy duplicate skip against files **already in the archive** (not just among newly-indexed files) — `condition_database` currently only dedupes *within* `located_files.db`. Acknowledged real gap.
- "Apply fixes" tool acting on Audit Archive's report (add undocumented files to DB, move misplaced files, clean orphaned entries) — discussed early, never built.
- Cross-copy duplicate date-conflict resolution — when Duplicate Finder finds identical files in different date folders with different recorded dates, nothing currently resolves which is "right." Repeatedly deferred to "the GUI phase."
- Delete-originals-after-copy tool — explicitly flagged as dangerous; should be a separate, guarded tool (possibly gated on Audit Archive confirming the copy first), same read/write-split pattern as `retrieve_data`/`write_data`.
- `analyze_date` as a standalone terminal CLI — **extensively designed, not built**:
  - `config.json`-driven (`input_mode`: database|folder; `output_mode`: database|report_file|both; `use_ocr_below_confidence` threshold; `worker_threads`; `already_analyzed_skip`).
  - Multithreaded (`ThreadPoolExecutor`), configurable thread count.
  - Two-phase: cheap signals first, escalate to OCR only if still below a confidence threshold.
  - Per-tool enable/disable flags, plus a "just apply everything regardless" override.
  - Explicitly imagined as reusable **outside ChronoVault entirely** by someone else, on their own files.

### GUI (nothing built yet at all)
- Calendar heatmap view (day cells colored by photo density — GitHub-contributions style / Apple Photos style).
- iTunes Cover-Flow-style horizontal scrubber for flipping through a day's photos.
- Detail panel: selected image + confidence/date_reason/camera info/GPS.
- Review queue screen surfacing `retrieve_data`/`write_data` for `_review_needed/` items.
- Duplicate resolution view — see both copies, pick one, optional "apply to all future finds" toggle.
- Map view using stored GPS coordinates.
- Thumbnail gallery filterable by label or date range.
- User-added manual labels (e.g., "these were taken in Hawaii").
- **GUI v0.1 (newly scoped, small)**: just buttons that launch the existing CLI tools — a graphical `chronovault.sh`. Not started.
- Eventual full Qt GUI — PySide6 recommended specifically (official Qt binding, LGPL license, API similar to the C++ Qt the user has used before).
- Localization: English, French, Japanese — noted as an architecture decision to make *from v0.1*, not retrofit later. Undecided whether v0.1 needs this immediately or can defer to v0.2.

### AI / Labeling
- People/place/object recognition — schema (`labels`, `file_labels`, many-to-many, `source` field distinguishing `ai` vs `user`) **already designed** in `Database_schema.md`, **not implemented**.
- GPS reverse-geocoding for location labels — smaller, more tractable subset of full AI labeling.
- Search/retrieval UI once labeling exists.

### Multi-language / Internationalization
- French filename/folder dates — mostly works already via existing DMY disambiguation (French dates are typically `DD/MM/YYYY`). Folder month-name matching (`MONTH_NAMES` dict) is **English-only currently** — French month names not yet added (small, scoped, not done).
- Japanese OCR — needs `tesseract-ocr-jpn` language pack (not installed) + new kanji-aware parsing patterns. Not built.
- Japanese folder-name matching — considered lower priority (Japanese dates are typically numeric, not name-based).
- GUI i18n architecture (en/fr/jp) — not built, no GUI exists yet.

### Industries / Alternate Use Cases (brainstormed, not pursued as features)
- Legal/compliance (Audit Archive's read-only design matches compliance audit-trail needs).
- Healthcare (DICOM medical imaging).
- Insurance claims documentation.
- Media/broadcasting digital asset management.
- Real estate listing photos.

### Testing Infrastructure
- `test_env.py` — **built**.
- `generate_test_data.py` — **built**, extended repeatedly, currently 16 scenario categories.
- `test_retrieve_data.py`, `test_write_data.py`, `test_ocr_date.py`, `test_analyze_date.py` — **all built**.
- `test_all.sh` (runs the entire pipeline + all test scripts from a clean slate) — **was in progress, cancelled mid-task**. A draft exists but was not fully verified.
- A menu-driven version of `test_analyze_date.py` (pick which signal source to test interactively) — discussed as an idea; what was actually built instead is a simpler single-file argparse script, not a menu.

---

## 5. Next 10–12 Things To Do

Based on exactly where the conversation left off:

1. **Finish `test_functions/test_all.sh`** — drafted but cancelled mid-task (not fully tested/verified) when this handoff was requested.
2. **Confirm the old standalone `ocr_date/` folder was actually deleted** on the user's end (superseded by `analyze_date/image_tools/ocr_tools.py`; flagged as the user's action item, never confirmed done).
3. **Confirm `multi_tools/README.md` and `condition_database/README.md` made it into the GitHub repo** — both were generated and delivered as downloads late in the session; given the account migration, verify they were actually committed.
4. **Confirm the `multi_tools`-wired `analyze_date.py` (with filename/folder signals integrated) is the version actually in GitHub** — this was completed and tested this session, but given multiple sandbox resets during the same work, double-check the final committed version matches.
5. **Close the archive-hash pre-copy-skip gap** in `condition_database` — currently only dedupes within `located_files.db`, not against `archive_database.db`.
6. **Verify hidden-folder scanning** actually works with Indexer (believed to work via `Path.rglob`, never explicitly tested).
7. **Add French month names** to `analyze_folder.py`'s `MONTH_NAMES` dict — small, scoped, clearly next.
8. **Test OCR against a real French date-stamped photo** to confirm the existing DMY disambiguation logic actually handles it correctly in practice (should work, unverified with real data).
9. **Decide the adjacent-files date inference architecture** (open question — see Section 6) and build it.
10. **Start GUI v0.1** — simple button-launcher for existing CLI tools, PySide6, with an explicit decision on whether to build in i18n architecture now or defer.
11. **Re-run a documentation pass on root `README.md` and `ROADMAP.md`** to reflect the now-completed `condition_database` + `multi_tools` integration (last full pass predates confirmed integration).
12. **Consider building `audio_tools`/ID3 support next**, given the user's real stated MP3-meeting-recording use case — likely dependency `mutagen`, needs install-and-verify like every other new dependency added this session.

---

## 6. Open Threads

*(Unresolved ambiguity/disagreement — distinct from the feature list above.)*

- **Adjacent-files inference architecture** — genuinely undecided: a `multi_tools` function accepting pre-fetched sibling data, vs. a second pass built into `condition_database.py` (which already has natural DB access).
- **"Undelete" scope** — never resolved whether the user wants just Trash-folder scanning (effectively already works) or true forensic recovery (a much bigger, externally-wrapped project) as the actual next priority.
- **GUI v0.1 and i18n** — raised, not decided: build the localization architecture in from the start, or defer to v0.2 once the basic button-launcher shape is proven?
- **`condition_database`'s "keep first duplicate found" default** — explicitly flagged by the assistant as *a* choice, not *the* choice. Not fully validated as final; a future duplicate-review GUI could override it. Whether it should eventually be user-configurable was never decided.
- **OCR's remaining known failure modes** (Japanese/kanji stamps, dot-matrix CCTV fonts) are explicitly *not* being worked on further per the user's direct "don't fix it now" instruction — unclear if/when this gets revisited.
- **Whether the fully-designed `analyze_date` CLI is still wanted**, and at what priority relative to other next steps — extensively scoped, never actually started.
- **Confidence value tuning** (98/95/90/85/80/70/60/40/30/20 across all signal sources) is reasoning-and-testing-based but was never declared "final" — open to revision as more real-world data comes in.
- **`raw_stub` test category is a known approximation**, not validated against any real manufacturer RAW file. The user said they'd try to find/test real RAW files themselves — unknown if this happened.

---

## 7. Terminology & Shorthand

- **"multitool"** — the user's own coined term for a type-*specific* tools folder (`image_tools`, `audio_tools`, `video_tools`) — like a swiss-army-knife for one media type. Use this word going forward per explicit instruction.
- **"multi_tools"** (the actual folder name) — the type-*independent* tools folder (filename/folder-path analysis). **Note the terminology trap**: this is easy to confuse with "multitool" above, but they mean different (almost opposite) things — one is per-type, the other is type-agnostic.
- **"conditioning" / `condition_database`** — the pre-import phase (hash + date + duplicate marking) that runs after Indexer, before Importer.
- **`archive/_review_needed/`** — the archive subfolder where low-confidence files land instead of a guessed date folder.
- **"baby steps"** — the user's own repeated phrase for the incremental, test-before-proceeding development philosophy. Treat as a standing instruction, not just a mood.
- **`EARLIEST_PLAUSIBLE_DATE = 1972-07-26`** — the user's own birthday, an intentional Easter egg in the implausible-date-cutoff constant.
- **"determine_date.py"** — an early, no-longer-used working name for what became `analyze_date.py`. Historical only; don't use going forward.
- **"signal" / "signal source"** — one piece of date evidence (EXIF, GPS, XMP, filename, etc.) in `analyze_date`'s combination model.
- **`base_confidence`** — the starting trust score assigned to a signal type before agreement/mismatch adjustments are applied.
- **ChronoVault** — the project name.

---

## 8. Memory Check

No persistent memory of this user or project was found. Per system configuration, Claude's cross-conversation memory feature is not enabled for this account, so there is no memory file to read or surface — this document, and whatever ships to GitHub, is the only durable record.

---

## 9. Gaps / Reliability Caveats

- **This session included multiple sandbox resets**, during which several files (`analyze_date.py`, `image_tools/*.py`, `multi_tools/*.py`, and others) were repeatedly reconstructed from the assistant's own memory of earlier turns, rather than re-read from a persistent source. Real uploaded files were used to correct this where the user provided them (notably, a full correct set was uploaded partway through the `multi_tools` integration work). **If anything in this document conflicts with the actual GitHub repo, the repo should be treated as authoritative.**
- **The assistant never saw the full, current, real content of `indexer.py`, `importer.py`, `audit_archive.py`, or `duplicate_finder.py` within this specific handoff conversation turn** — earlier-session reconstructions of these existed, but per the instruction to focus only on conversation-only context (not repo-documented content), they're intentionally not re-summarized here. Worth a sanity check that GitHub's versions are the ones actually meant to carry forward.
- **Unknown**: the user's actual GitHub repo URL/structure, whether the hidden-folder scan was ever tested, whether French month names or the archive-hash dedup gap were addressed after this document's generation, and whether real manufacturer RAW files were ever tested against `analyze_date`.
- **This document is a single-pass generation.** The user asked for an append/update-able file given the risk of further resets — this version should be treated as the seed; any continuation should append new findings rather than regenerate from scratch, to avoid losing anything captured here.

---

## Changelog

- **v1** — Initial generation, single pass, covering the full conversation history available at time of writing.
