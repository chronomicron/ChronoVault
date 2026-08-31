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
| `generate_test_data.py`: French-month-name folder scenario (e.g. `mars 2024`) to exercise `analyze_folder.py`'s planned French `MONTH_NAMES` support | ❌ Noted, not yet built |
| `generate_test_data.py`: hidden-folder scenario (real matching files inside a `.`-prefixed folder) to actually verify Indexer's `rglob` walks into it | ❌ Noted, not yet built |

## Documentation Debt

| File | Status |
|---|:---:|
| Root `README.md`, `analyze_date/README.md`, `image_tools/README.md`, `audio_tools/README.md`, `video_tools/README.md`, `test_functions/README.md`, `generate_test_data/README.md`, `multi_tools/README.md`, `condition_database/README.md` | ✅ Up to date |
| Old `ocr_date/` folder | ⚠️ Superseded, should be deleted (unconfirmed whether this happened) |

## New Since Last Roadmap Pass

### Multi-language support (French + Japanese) — newly raised, not yet built

This touches several different places, worth scoping separately rather than as one task:

- **`analyze_folder.py`'s month names** — currently English-only (`MONTH_NAMES` dict). Adding French (`mars`, `janvier`...) is small and mechanical. Japanese folder naming by month name is a much rarer real-world pattern (Japanese dates are usually numeric, `2024年3月`), so lower priority.
- **OCR + French** — mostly already works. French date stamps are typically `DD/MM/YYYY`, and the DMY disambiguation logic already built for `ocr_tools.py` and `analyze_filename.py` already handles this ordering. No new work needed, just worth testing against a real French-stamped photo to confirm.
- **OCR + Japanese** — still needs the `tesseract-ocr-jpn` language pack and kanji-aware parsing patterns, as already documented in `ocr_tools.py`'s known limitations. Unchanged status: real, scoped, not started.
- **GUI localization (en/fr/jp)** — no GUI exists yet, so this is really a *requirement on the GUI's architecture* from day one: build it with a strings/translation-table pattern from the start rather than hardcoded English text, so language support doesn't mean retrofitting later. Worth deciding as part of GUI v0.1's design, even if only English ships first.

### GUI v0.1 — newly scoped, not started

Deliberately small: not the calendar-heatmap/thumbnail-gallery vision from earlier brainstorming — just a simple window with buttons that launch the tools already built (Indexer, Condition Database, Importer, Audit Archive, Duplicate Finder), a graphical version of `chronovault.sh`'s menu. Using PySide6 (LGPL, official Qt bindings, discussed earlier). This is a real, well-scoped "first GUI screen" — worth deciding whether it also needs the localization architecture from day one, or whether that's a v0.2 concern once v0.1 proves the basic shape works.

### Archive/compressed-file scanning (ISO, ZIP, tarballs) — newly raised, not yet built

Real gap: media can be sitting inside a `.zip`, `.tar`/`.tar.gz`, or `.iso` on an old drive, and today Indexer walks right past it — the file itself gets indexed if its extension matches, but nothing inside it ever does.

**Confirmed 2-step approach** (Indexer stays a pure scanner; opening archives is a deliberately separate, opt-in concern):

- **Step 1 (Indexer, unchanged in spirit).** During its normal walk, Indexer recognizes a configurable list of archive extensions and logs them to a separate table rather than opening them — never touches their contents. At the end of the run, the report includes a dedicated section: *"I found the following compressed/disc-image files: [list]. Run `archive_scanner.py` if you'd like me to look inside them."* Same "report, let a person decide" pattern already used by Audit Archive and `condition_database`'s duplicate report.
- **Step 2 (new opt-in tool, `archive_scanner/`, its own `config.json`).** Run deliberately, only against the flagged list:
  - **ZIP / tar / tar.gz** — Python's stdlib `zipfile`/`tarfile` list and extract members directly, no mounting, no elevated permissions, no cleanup risk.
  - **ISO** — avoid OS-level mounting (typically needs root/sudo on Linux, and risks an orphaned loop mount if interrupted). `pycdlib` (pure Python, reads ISO9660/Joliet/UDF) lists and extracts without ever mounting — a new dependency, would need `test_env.py` updated to check for it, same as tesseract/opencv/numpy were for OCR.
  - Anything found inside gets extracted to a staging folder and added to `located_files.db` as new rows with the **candidate** status described below — it does *not* get auto-imported. A person still has to say yes to each one (or the batch) via the candidate-review mechanism, same as everything else pulled in through a non-obvious path.
- Open question, not yet decided: whether `.rar`/`.7z` are worth supporting given they need external dependencies Python doesn't handle natively (`rarfile`/`py7zr`, both often shelling out to a system binary) — lower priority than ZIP/tar/ISO.

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
