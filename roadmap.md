# ChronoVault Roadmap

A living map of the project: what's built, what's missing, and what's next — organized around the real use case (an old hard drive full of scattered media, archived and made searchable), not just a feature list.

## The Use Case, Stage by Stage

| # | Stage | Status |
|---|---|:---:|
| 1 | Point at a storage location (HDD/NAS/cloud-mounted folder) | ✅ Done |
| 2 | Recursively scan, including hidden folders | 🟡 Likely works (`Path.rglob`), never explicitly tested with a hidden-folder case |
| 3 | Scan arbitrary file types (images, video, audio, documents) | 🟡 Mechanically works (just extensions in config) — only images get *smart* date detection so far |
| 4 | Scan Trash/Recycle Bin | ✅ Already works — it's just a folder, point Indexer at it |
| 4b | True forensic undelete (unallocated sectors) | ❌ Not started — would wrap an external tool (PhotoRec/TestDisk), not build from scratch |
| 5 | **Pre-copy conditioning**: hash, date, mark duplicates *before* copying | ✅ Done — `condition_database` |
| 5b | Skip files whose hash already exists in the *archive* (not just among themselves) | ❌ Real gap — `condition_database` dedupes within `located_files.db` only, doesn't check against `archive_database.db` |
| 5c | Refuse to index an existing ChronoVault archive by accident | ✅ Fixed — found via a real, reproducible mistake during GUI testing: pointing both Source and Archive at the same existing archive re-imported every file into itself, landing as `(1)`/`(2)` duplicate copies (every tool behaved correctly given the input — the whole scenario was still wrong). Indexer now refuses upfront if the search path itself contains `archive_database.db` (only Importer ever creates this file), before touching the database at all. Override: `--allow-archive-source`, for deliberate migration/consolidation. GUI reuses the identical check (not a separate copy) and shows a confirmation dialog. **Known limitation, accepted for now:** only checks the search path itself, not archives nested deeper inside a larger scanned folder — narrower than 5b above, which would also catch cross-location duplicate content generally, not just this specific "pointed straight at an archive" case. |
| 6 | Determine creation date using multiple independent tools | ✅ Done — `analyze_date` + 7 signal sources (see below) |
| 7 | Copy into archive | ✅ Done — Importer |
| 8 | Store date evidence + confidence in the archive database | ✅ Done |
| 9 | Prompt to delete originals from source | ❌ Not built — deliberately, given how dangerous deletion is. Should be its own explicit tool, gated on Audit Archive confirming the copy first |
| 10 | AI labeling (people, places, things) | ❌ Not built — schema designed in `Database_schema.md`, unimplemented |
| 10b | Location labeling via GPS reverse-geocoding | ❌ Not built, but much smaller than full AI labeling |
| 11 | User-applied manual labels | ❌ Not built — needs the labels schema *and* a GUI |
| 12 | GUI (thumbnail gallery, filter by label/date range) | ❌ Not built at all — see "GUI v0.1" below for the newly-scoped first step |

## `analyze_date` Signal Sources

| Source | Confidence | Status |
|---|:---:|:---:|
| EXIF GPS timestamp | 98 | ✅ |
| EXIF DateTimeOriginal | 95 | ✅ |
| TIFF native DateTime tag | 90 | ✅ |
| XMP CreateDate (Photoshop/Lightroom) | 80 | ✅ |
| Filename pattern (US + European disambiguation) | 70 | ✅ |
| OCR corner date-stamp (opt-in) | 60 | ✅ — real limitations documented (Japanese/kanji stamps, dot-matrix CCTV fonts) |
| Folder path pattern | 40 | ✅ |
| Filesystem date | 30 | ✅ (fallback of last resort) |
| **ID3 tags (MP3)** | — | ❌ `audio_tools/` is a documented placeholder, no code |
| **MP4 container metadata** | — | ❌ `video_tools/` is a documented placeholder, no code |
| **Adjacent-files inference** | — | ❌ Discussed, not built — architecturally different from every other signal (needs database access to siblings' *already-resolved* dates, not just this file's own path/metadata). Open design question: does this live in `multi_tools/` as a function that accepts pre-fetched sibling data, or as a second pass inside `condition_database.py` (which already has the natural database access)? |
| **PDF/document metadata** | — | ❌ Not scoped yet at all — no `document_tools/` folder exists |

## Review & Correction Workflow

| Piece | Status |
|---|:---:|
| `retrieve_data` (read-only, UI-agnostic) | ✅ Done |
| `write_data` (applies corrections, preserves original evidence) | ✅ Done |
| Duplicate-group review (which copy is "correct" when Duplicate Finder finds cross-folder dupes) | ❌ Not built — same review-workflow pattern, not yet applied to this case |

## Testing Infrastructure

| Piece | Status |
|---|:---:|
| `generate_test_data.py` — 16 scenario categories across JPEG/TIFF/BMP/RAW-approx/THM | ✅ Done |
| `test_functions/` — env check, retrieve/write/OCR/analyze_date debugging scripts | ✅ Done |
| `chronovault.sh` — step-by-step menu (cleanup → generate → index → condition → import → audit → duplicates) | ✅ Done |
| `chronovault.sh` self-contained test environment — everything lives in `chronovault_test/`, cleanup is a single safe folder delete, real archives at the project root are never at risk | ✅ Done |
| `chronovault.sh` module-test menu options (test_env, test_retrieve_data, test_write_data, test_analyze_date, test_ocr_date) | ✅ Done |
| `generate_test_data.py`: hidden-folder scenario (2 dot-prefixed folders, one at the search root and one nested) | ✅ Done — confirmed directly: `Path.rglob('*')` does walk into dot-prefixed folders at both depths, so item #6 in the "next 10" list (roadmap use-case row 2) is no longer just an assumption once run through a real Indexer pass |
| `generate_test_data.py`: European-style (day-first) filename-only date scenario, no EXIF | ✅ Done — confirmed directly against `analyze_filename.py`'s actual DMY logic, all four test cases parsed correctly as day-first |
| `generate_test_data/README.md` documentation gap | ⚠️ Found and corrected: the README described TIFF/BMP/RAW-stub/THM scenarios and an `--other-format-samples` argument that don't exist anywhere in the actual code. README now matches the real script; whether those formats should actually be built is an open question, not resolved by the correction. |
| **Bug: `ocr_tools.py` imported `cv2`/`numpy`/`pytesseract` at module level**, meaning anyone using `analyze_date` at all (via Importer, Condition Database, etc.) needed those packages installed even without ever touching OCR — surfaced as a real `ModuleNotFoundError: No module named 'cv2'` on a machine without opencv, from nothing more than launching Importer. | ✅ Fixed — imports moved inside `_otsu_threshold()` and `_ocr_with_confidence()`, the two functions that actually use them. Verified directly: `analyze_date` imports and runs correctly with all three packages genuinely blocked from being imported, and only fails — correctly — the moment `try_ocr=True` actually needs them. `test_env.py` updated to mark NumPy/OpenCV/Tesseract/pytesseract as optional, matching this. |
| **Bug: `condition_database.py` never `ensure_column`'d `file_hash`**, but read and wrote that column throughout. The old assumption (documented in `condition_database/README.md`) was that Duplicate Finder would have already added it — but Duplicate Finder runs *last* in the documented pipeline order, so the very first Indexer → Condition Database run always hit this. Every per-file row silently failed (swallowed by a broad `try/except`, printed as `FAILED`), then the final duplicate-check query crashed outright with `sqlite3.OperationalError: no such column: file_hash`. | ✅ Fixed — added the missing `ensure_column()` call alongside the other four. Verified directly via a real generate → index → condition run: 0 failures, duplicate detection completes, report writes out. `condition_database/README.md` updated with a "Bug Fixed" section documenting this, matching `audit_archive/README.md`'s existing convention for logging caught bugs. |

## Documentation Debt

| File | Status |
|---|:---:|
| Root `README.md`, `analyze_date/README.md`, `image_tools/README.md`, `audio_tools/README.md`, `video_tools/README.md`, `test_functions/README.md`, `generate_test_data/README.md`, `multi_tools/README.md`, `condition_database/README.md` | ✅ Up to date |
| Old `ocr_date/` folder | ⚠️ Superseded, should be deleted (unconfirmed whether this happened) |

## New Since Last Roadmap Pass

### Multi-language support (French + Japanese) — French month names DONE, rest not yet built

This touches several different places, scoped separately rather than as one task:

- **`analyze_folder.py`'s month names — ✅ Done.** French entries (`janvier`, `février`/`fevrier`, `mars`, ... both accented and unaccented spellings for every name that carries an accent) added to `MONTH_NAMES`. This surfaced a real bug in the process, not just a data gap: the `month_name_year` regex matched `[A-Za-z]+` only, so an accented name like `février` could never match at all — it would silently fall through to "no date found" rather than erroring, exactly the quiet-failure mode this project works to avoid. Fixed by matching `[^\W\d_]+` instead (any language's letters), which also means a third language's month names later needs only dictionary entries, no further regex change. Verified directly: 15 test cases (English regression + French accented/unaccented + negative cases like a bare `1080` folder) all pass, and confirmed end-to-end through the real `analyze_date()` call against genuine files sitting in an actual accented folder (`Old_Backup_1/février 2022/`) — not just the isolated function. `generate_test_data.py` now has a dedicated `french_month` scenario exercising this for real. Japanese folder naming by month name was considered and deprioritized — Japanese dates are typically numeric (`2024年3月`), so the existing year/year-month patterns already cover it reasonably without new month-name entries.
- **OCR + French** — mostly already works. French date stamps are typically `DD/MM/YYYY`, and the DMY disambiguation logic already built for `ocr_tools.py` and `analyze_filename.py` already handles this ordering. No new work needed, just worth testing against a real French-stamped photo to confirm.
- **OCR + Japanese** — still needs the `tesseract-ocr-jpn` language pack and kanji-aware parsing patterns, as already documented in `ocr_tools.py`'s known limitations. Unchanged status: real, scoped, not started.
- **GUI localization (en/fr/jp)** — no GUI exists yet, so this is really a *requirement on the GUI's architecture* from day one: build it with a strings/translation-table pattern from the start rather than hardcoded English text, so language support doesn't mean retrofitting later. Worth deciding as part of GUI v0.1's design, even if only English ships first.

### GUI v0.1 — right-side tool panel, archive-source safety check, and diagnostic/logging system added

**Right-side panel added**, deliberately separate from the main Index/Import flow, so every other tool can get a button without reworking the main layout each time it grows. Now wired: **Condition Database**, **Audit Archive**, **Duplicate Finder**, and (pinned to the bottom) **Generate Diagnostic Report**. All action buttons (five, up from two) disable together while any one is running.

**Real bug found and fixed via actual GUI use, not review:** pointing both Source and Archive at the same existing archive caused Indexer to re-discover every already-organized photo as "new," and Importer to re-copy each one into itself as `(1)`/`(2)` duplicates — every tool behaved correctly given its input; the situation was still entirely wrong. Fixed with `looks_like_chronovault_archive()` in `indexer.py` (checks for `archive_database.db` at the search root, before any database access happens) plus a `--allow-archive-source` override for deliberate migration/consolidation. The GUI reuses the identical function (imported directly from `indexer.py`, not a separate copy) and shows a confirmation dialog defaulting to **No**.

**A second real bug, found immediately after the first fix shipped:** Audit Archive and Duplicate Finder were deliberately left un-synced with the GUI's Archive field (reasoning: "supplementary tools, not part of the main flow"). This was wrong in practice — a real test session using a custom archive location had Importer succeed against the real path while these two silently checked the stale default (`"archive_root": "archive"`, relative to the project root) instead, both failing with a correct but confusing `Archive root 'archive' does not exist`. Fixed by making `update_archive_root_in_config()` mode-aware (skips writing `archive_root` if a config's `mode` key is present and set to anything other than `"archive"` — relevant only to Duplicate Finder's source/archive dual-mode config) and applying it to all three archive-touching tools consistently. Verified directly against all three mode scenarios (no mode key, `mode="archive"`, `mode="source"`).

**Persistent activity log + crash detection, built into `gui_settings.ini`:** a fixed-size circular buffer (50 numbered slots, `entry_0`..`entry_49`, plus a persisted `next_index` counter deciding which slot gets written next) records every button press, tool launch, and outcome. Chosen deliberately over a simpler "rewrite the whole list every time" design: the persisted index means a restart after a crash doesn't reset to slot zero, so events leading up to a crash aren't at risk of being overwritten until the buffer wraps all the way back around (50 more events later), not on the very next restart. Reading the log back sorts by each entry's own embedded microsecond timestamp rather than trusting slot order, since slot order stops matching chronological order the moment the buffer wraps around even once — verified directly by writing 75 entries and confirming exactly the most recent 50 survive, in correct order.

Every clean shutdown writes a specific marker as the final event. At startup, if the previous session's last recorded event isn't that marker, the GUI infers an unclean exit (crash, force-quit, lost connection) and notes it in the output panel — not a blocking popup, since a startup dialog for what might be an ordinary force-quit would be more annoying than useful. Verified directly through the full lifecycle: fresh install (no false crash flag), clean shutdown + restart (correctly not flagged), and a simulated crash + restart (correctly flagged, with the exact last event captured in a WARNING log entry).

**Generate Diagnostic Report**, bottom-right button: a plain-text report combining environment info, current field values, the last 50 log entries in correct chronological order, every tool's resolved config values (`database_path`/`archive_root`/`mode`) with existence checks, and database row counts by status — meant to be pasted directly when asking for debugging help. Read-only, uses a read-only SQLite connection, and isn't blocked by another tool running (deliberately — that's often exactly when it's needed). Simulating the real session that surfaced the archive-sync bug above confirmed this report would have shown the exact path mismatch immediately, rather than needing several back-and-forth messages to diagnose.

**Also fixed along the way:** the missing-`libxcb-cursor0` Linux startup crash (`sudo apt install libxcb-cursor0` — a missing system library Qt 6.5+ needs for its X11 cursor-theme support, not a Python or code issue), and a real self-inflicted bug in an earlier delivery of `gui_data.py` where a botched edit merged two functions' bodies together, silently deleting `update_archive_root_in_config` as a callable name (caught by the resulting `ImportError`, fixed, and re-verified this time by actually importing and calling every expected function, not just checking that the file compiles — `py_compile` cannot catch dead code after a `return` statement, which is exactly what the bug was).

### GUI v0.1 — first pass built (Index + Import only), several real design decisions made along the way

**What's actually built:** `chronovault.py` (top-level launcher, run from the project root) and `gui/` (`chronovault_gui.py` — the Qt window; `gui_data.py` — non-Qt config logic, deliberately separated so it's testable without Qt installed at all, same reasoning as `retrieve_data` being UI-agnostic). Source folder field + Browse, Archive folder field + Browse, Index button, Import button, a status line, and a live-streaming read-only output panel. Both action buttons disable while either tool is running, specifically to prevent two tools ever writing to the same database at once.

**Framework:** PySide6 (LGPL, official Qt bindings) — `pip install PySide6 --break-system-packages`, pure Python, no system packages needed. Added to `test_env.py` as an optional check.

**Two config files, deliberately split:** `gui/gui_config.json` (static, checked into git — where each tool's script/config live, paths relative to the project root) and `gui/gui_settings.ini` (dynamic, personal, gitignored — last-used folder paths, via Python's built-in `configparser`, no new dependency).

**How the archive path reaches Importer:** the GUI doesn't invent a parallel configuration path. Right before launching, it reads `importer/config.json`, updates only `archive_root`, and writes it back — every other hand-configured key is read and preserved untouched. Verified directly: a config with extra keys (`min_file_size_bytes`, `exclude_path_contains`) round-trips with only `archive_root` changed. Importer itself remains completely unaware a GUI exists.

**Not sandboxed to `chronovault_test/`** — this GUI operates against real folders from the start, since neither Indexer nor Importer delete or modify source files. `chronovault.sh` remains the safe, contained testing path; the GUI is the real-use path.

**Deliberately deferred, not forgotten:**
- **Stop button** — needs `store_files()`'s commit behavior fixed first (currently one commit at the very end of a whole scan; `store_archives()` already commits per-archive). Until fixed, killing Indexer mid-run loses the entire run's findings, not just what came after the interruption.
- **Verify Status dialog** (path/dependency/archive/config-key sanity, found in a Help/Tools menu — placement follows frequency of use, not just logical grouping) — needs a single shared "expected keys per config" definition that a future `--init` flag will also use, so the two can never quietly disagree about what "correct" looks like.
- **Visual styling** — default Qt/Fusion for now; QSS stylesheets or a theme package (`qt-material`, `PyQtDarkTheme`) can deliver a genuinely modern look later without a framework change. Mechanics first, polish second.

**`--init` flag (discussed, not yet built, revisit per-tool as each is next touched):** a `--init` flag for each tool (starting whenever that tool is next modified) that regenerates a clean, default `config.json` — never destructively; the existing file gets renamed to `config.json.bak` first, never silently overwritten. A full reset, not a smart partial repair — simpler and more predictable. This exists specifically so a GUI that edits config files (like this one now does) has a built-in, terminal-usable recovery path if it ever corrupts one — the fix doesn't depend on the GUI itself working.

**Indexer robustness work needed to support Stop/heartbeat (not yet built):**
- Batch commits during the walk (every ~100 files) instead of one commit at the end — measured directly: committing every single row is ~500× slower than any form of batching, but batching even modestly is effectively free, so there's no real cost to choosing safety here.
- Broaden the walk's exception handling from `PermissionError` only to `OSError` generally — today, a disconnected drive mid-scan likely surfaces as an unhandled crash rather than a clean, informative stop.
- Periodic progress output every ~100 files (same cadence as the commits) — showing both a running count and the current path being scanned, e.g. `...still scanning (1,500 found so far) — currently in: /mnt/backup/Pictures/2019`. Serves both as user-facing heartbeat and as a crash-diagnostic checkpoint (see below) from the same piece of data.
- **New `indexer_runs` table** in `located_files.db`, one row per distinct `search_root` (overwritten on each new scan of the same location — "latest state," not a full history log, per explicit decision: the real use case is periodically re-scanning the same phone/drive, not needing a timeline of past scans). Tracks `status` (`in_progress`/`completed`), `last_seen_path`, `files_found_so_far`. A dangling `in_progress` row found at the start of a new scan is itself the crash signal — no separate crash-detection logic needed. The GUI would surface this as: *"A previous scan of this location didn't finish — it stopped around X. This could mean a crash, a disconnected drive, or a problem file nearby. Continue?"* — explicitly a diagnostic clue, **not** a resume-without-rescanning shortcut (re-running is already database-safe today via `file_path`'s `UNIQUE` constraint + `INSERT OR IGNORE`; a true fast-resume would require reliably seekable filesystem walk order, which isn't guaranteed and isn't being built).
- **Known limitation, accepted for now:** tracking is by path string, not physical device identity. The same drive remounting at a different path looks like "never seen before." A UUID-based approach is real, worthwhile, platform-specific work — not v0.1.
- **Symlinked directories:** tested directly — on Python 3.12, `Path.rglob()` does not descend into symlinked directories at all (confirmed with both a genuine loop-back symlink and a legitimate symlink to a separate directory — neither got its contents listed). No infinite-loop risk today, but also means legitimate symlinked content (e.g. a NAS reorganized via symlinks) is silently skipped. A `follow_symlinks` opt-in flag (default `false`), matching `look_inside_archives`'s pattern, is a reasonable future addition if this ever turns out to matter for a real setup.
- **`.lnk` files are a non-issue, clarified for the record:** Windows shortcut files are ordinary, inert files interpreted only by Explorer — not a filesystem-level link mechanism at all, and not something `pathlib` ever traverses into. The real equivalent risk (NTFS junctions / directory symlinks) would behave like the tested Linux case, but this wasn't directly verified on Windows.

**Future enhancement, logged, not scoped yet: DVD/optical-media identification by volume label.** A burned DVD's volume label is embedded in the disc's own ISO9660/UDF filesystem metadata at burn time and is permanent (read-only media can't be relabeled) — a more trustworthy identity marker than a USB drive's mutable label. On Linux, many desktop environments already auto-mount removable media at a path that includes the volume label (e.g. `/media/you/FAMILY_PHOTOS_2003`), so simple path-based tracking may already capture disc identity reasonably well there for free. On Windows, a DVD gets a drive letter with no relationship to the label, so path tracking would not distinguish between different discs. A robust, path-independent version would mean reading the label directly from filesystem metadata — real, platform-specific code (`blkid`/`lsblk` on Linux, `GetVolumeInformation` via `pywin32` on Windows) — not attempted yet.

### Archive/compressed-file scanning (ISO, ZIP, tarballs) — location detection + content listing DONE, extraction not yet built

Real gap that prompted this: media can be sitting inside a `.zip`, `.tar`/`.tar.gz`, or `.iso` on an old drive, and Indexer used to walk right past it entirely.

**What's actually built now** (implemented directly in Indexer, not as a separate `archive_scanner` tool as originally sketched below — a design that changed once we got into it):

- **Detection is unconditional.** Indexer recognizes a configurable list of archive extensions (`archive_extensions` in `indexer/config.json`, default `zip`/`tar`/`tar.gz`/`tgz`/`iso`) during its normal walk and records every archive's location in a new `located_archives` table, regardless of any other setting. This never opens the archive — as cheap as noting a normal file's path.
- **Content listing is opt-in** via `look_inside_archives` (default `false`). When on, Indexer also lists which member files inside each archive match the configured media `extensions` — via `zipfile`/`tarfile` (stdlib, no new dependency) for ZIP/TAR, and `pycdlib` (optional dependency, gracefully degrades with a clear note if not installed) for ISO. No extraction happens in either case — only reading headers/central-directory/filesystem-structure, never file contents.
- **Turning the flag on later backfills, rather than requiring a rescan.** An archive already on record (location only) from an earlier run gets its contents listed on a later run once the flag is turned on — Indexer doesn't need to re-walk the whole source drive just because a config value changed. An archive whose contents were already successfully listed is never re-listed, the same "don't redo work already done" principle used for hashing elsewhere.
- **Failure is contained per-archive.** A corrupt/unreadable archive, an unsupported type (e.g. `.rar` added to `archive_extensions` without a built-in lister), or a missing `pycdlib` all result in the archive's location still being recorded, with a specific note explaining what went wrong — never a crash that stops the rest of the run.
- Verified directly against real ZIP and TAR.GZ test archives with known contents (correct inclusion/exclusion of matching vs. non-matching members), a genuinely corrupt ZIP (clean failure, not a crash), and the ISO-without-pycdlib path (clean degradation). `pycdlib` is now installed — the pycdlib-*present* ISO-listing path is still not yet verified against a real ISO (none was available during development); **holding this open until a real ISO file is found to test against**, since the graceful-degradation path being correct doesn't prove the success path is.
- `generate_test_data.py` now generates two real archives (`Archives/old_photos_backup.zip`, `Archives/old_photos_backup.tar.gz`), built from already-generated `match` files rather than placeholder content — gives Indexer's archive detection and content-listing something genuine to open. Verified end-to-end: both detected regardless of `look_inside_archives`, and with it on, the exact filenames inside each are correctly listed.

**Still not built:** anything that acts on `matching_files` once listed — i.e., actually extracting those specific members to a staging folder so they can be reviewed and imported. That's the piece the original 2-step sketch below called "Step 2" — listing now exists, extraction doesn't yet. When it's built, extracted files should land in `located_files.db` with the **candidate** status described below (not auto-imported), going through the same candidate-review mechanism as everything else pulled in through a non-obvious path.

Open question, not yet decided: whether `.rar`/`.7z` are worth supporting given they need external dependencies Python doesn't handle natively (`rarfile`/`py7zr`, both often shelling out to a system binary) — Indexer will detect and record them today if added to `archive_extensions`, just without content listing.

### "Camera photo" discrimination filter — newly raised, not yet built

Real gap: today, "search for `.jpg`" means *every* `.jpg` — including web cache thumbnails, favicons, and logos nobody wants archived. The actual desire is closer to "photos actually taken with a camera, or scanned documents/photos" — a meaningfully different (and fuzzier) question than "does the extension match."

**Confirmed 2-step approach**, mirroring the archive-scanning shape above — Indexer still just scans and scores, a person still makes the actual call:

- **Step 1 (Indexer).** While indexing images normally, compute a lightweight "possible photo" signal per file — not a hard filter, closer to `analyze_date`'s "evidence in, scored answer out" pattern (a natural reuse of a pattern already proven here, not a new one invented from scratch). Files split into three outcomes, not two:
  - **Confident camera photo** (real EXIF camera tags present) — indexed normally, no extra prompt needed.
  - **Confident non-photo** (tiny file size, indexed/palette color, filename patterns like `icon_`/`sprite_`) — excluded normally, no extra prompt needed.
  - **The ambiguous middle** — no EXIF, but a plausible sensor-like aspect ratio (4:3, 3:2, 16:9) *and* high color definition (truecolor) rather than a fixed/indexed palette. These are the ones that actually need a person's judgment — e.g. a photo that had its EXIF stripped by a messaging app export, vs. a genuinely non-camera image that happens to be a normal shape.
  - End-of-run report calls this middle tier out explicitly: *"I found these images that might possibly be photos taken by a camera: [list]. Would you like to include them?"*
- **Step 2 (candidate review).** The ambiguous-tier files land in `located_files.db` with the same **candidate** status as archive-scanner finds — reviewed and approved/rejected the same way, through the same mechanism, rather than needing a second bespoke review flow.

Additional signals worth folding into the scoring later, once the basic three-way split above is working: DPI metadata (scans often 300 DPI vs. 72 for web graphics) and a distinct scanned-document sub-case (high DPI + page-like aspect ratio + low color variance) — a positive case in its own right, not just "not a web graphic."

### Candidate review mechanism — newly identified as a shared dependency, not yet built

Both features above produce the same underlying need: a list of files Indexer/`archive_scanner` found but isn't confident enough to import automatically, that a person has to explicitly approve or reject. Today there's no such concept — Importer only ever acts on `status='located'`/`status='excluded'` rows, both of which assume the *filter logic itself* already made the call.

Proposed design, following the exact split already proven by `retrieve_data`/`write_data`:

- **New `located_files.status` value: `candidate`.** Distinct from `located` (indexed, eligible, no open question) and `excluded` (filtered out by config, re-evaluated each run). A candidate row means "found, but a person needs to decide."
- **Rejection is a separate flag, not a status change.** A new column (`candidate_decision`, say — `NULL`/`pending`, `approved`, `rejected`) sits alongside `status` rather than status moving to `excluded` on rejection. Reasoning: `excluded` already carries its own meaning (a config filter caught it, re-evaluated fresh every Importer run) — collapsing "a person deliberately said no" into that same bucket would blur two genuinely different things, and `excluded`'s automatic re-evaluation isn't the right behavior here anyway. A rejected candidate should stay exactly as rejected until a person revisits it on purpose.
  - This also means **no rework.** Whatever produced the candidate in the first place — extracting a file from an archive, scoring an ambiguous image — never has to be redone if someone changes their mind later. The row, and whatever evidence/score got attached to it, just sits there with `candidate_decision='rejected'` until flipped.
  - Approving sets `candidate_decision='approved'` **and** flips `status` to `located`, so Importer picks it up on its next normal run — approval is the one decision that actually needs to change `status`, since that's what makes a row eligible for import at all.
  - A rejected candidate can be revisited at any time — re-running the review tool would naturally show pending items by default, with an option to also list previously-rejected ones in case someone wants to reconsider.
- **Read side** — a `list_candidates()`-style function, same shape as `list_review_items()`: plain dicts, JSON-serializable, no assumption about terminal vs. future GUI. Would reasonably support filtering by decision (`pending`, `rejected`, or all) and grouping by *why* something became a candidate (archive-extracted vs. ambiguous-photo-score), so a person can review one batch at a time rather than one giant undifferentiated pile.
- **Write side** — an `approve_candidates()`/`reject_candidates()` pair (or a single function taking a decision per id), same "already-decided structured input in, plain dict report out" shape as `apply_date_correction()`.
- Terminal-first, same convention as everything else — a `test_functions/`-style script or a `chronovault.sh` menu option would be the first real front end, with the GUI later just calling the same functions, exactly the same relationship `retrieve_data`/`write_data` already have to a hypothetical future GUI.
- This turns out to be the more foundational piece of the two features above — worth building this shared mechanism first, with archive-scanning or photo-discrimination as the first real *producer* of candidates to prove it end to end, rather than building either feature with its own one-off review flow.

## Suggested Priority Order

Given everything above, roughly in order of "smallest effort for real value":

1. **Documentation debt** — now closed (`multi_tools/README.md`, `condition_database/README.md` both exist).
2. **Hidden-folder scan verification** — one test case, confirms something that's *probably* already fine.
3. **Archive-hash pre-copy skip (5b)** — small, closes a real functional gap in `condition_database`.
4. **GUI v0.1** — button-launcher, proves the GUI shape works before investing in anything fancier.
5. **Candidate review mechanism** — foundational for both archive-scanning and camera-photo discrimination below; worth building before either, since both need it and it's smaller and more self-contained than either.
6. **Everything else** (delete-originals tool, AI labeling, ID3/MP4 signals, adjacent-files inference, French/Japanese depth, archive/compressed-file scanning, camera-photo discrimination) — larger, worth picking one at a time as they become the actual next priority.
