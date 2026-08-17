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

## Documentation Debt

| File | Status |
|---|:---:|
| Root `README.md`, `analyze_date/README.md`, `image_tools/README.md`, `audio_tools/README.md`, `video_tools/README.md`, `test_functions/README.md`, `generate_test_data/README.md` | ✅ Up to date |
| **`multi_tools/README.md`** | ❌ Doesn't exist yet — folder was added after the last documentation pass |
| **`condition_database/README.md`** | ❌ Doesn't exist yet — same reason |
| Old `ocr_date/` folder | ⚠️ Superseded, should be deleted (your action item, noted a while back) |

## New Since Last Roadmap Pass

### Multi-language support (French + Japanese) — newly raised, not yet built

This touches several different places, worth scoping separately rather than as one task:

- **`analyze_folder.py`'s month names** — currently English-only (`MONTH_NAMES` dict). Adding French (`mars`, `janvier`...) is small and mechanical. Japanese folder naming by month name is a much rarer real-world pattern (Japanese dates are usually numeric, `2024年3月`), so lower priority.
- **OCR + French** — mostly already works. French date stamps are typically `DD/MM/YYYY`, and the DMY disambiguation logic already built for `ocr_tools.py` and `analyze_filename.py` already handles this ordering. No new work needed, just worth testing against a real French-stamped photo to confirm.
- **OCR + Japanese** — still needs the `tesseract-ocr-jpn` language pack and kanji-aware parsing patterns, as already documented in `ocr_tools.py`'s known limitations. Unchanged status: real, scoped, not started.
- **GUI localization (en/fr/jp)** — no GUI exists yet, so this is really a *requirement on the GUI's architecture* from day one: build it with a strings/translation-table pattern from the start rather than hardcoded English text, so language support doesn't mean retrofitting later. Worth deciding as part of GUI v0.1's design, even if only English ships first.

### GUI v0.1 — newly scoped, not started

Deliberately small: not the calendar-heatmap/thumbnail-gallery vision from earlier brainstorming — just a simple window with buttons that launch the tools already built (Indexer, Condition Database, Importer, Audit Archive, Duplicate Finder), a graphical version of `chronovault.sh`'s menu. Using PySide6 (LGPL, official Qt bindings, discussed earlier). This is a real, well-scoped "first GUI screen" — worth deciding whether it also needs the localization architecture from day one, or whether that's a v0.2 concern once v0.1 proves the basic shape works.

## Suggested Priority Order

Given everything above, roughly in order of "smallest effort for real value":

1. **Documentation debt** — `multi_tools/README.md`, `condition_database/README.md`. Cheap, closes a real gap.
2. **Hidden-folder scan verification** — one test case, confirms something that's *probably* already fine.
3. **Archive-hash pre-copy skip (5b)** — small, closes a real functional gap in `condition_database`.
4. **GUI v0.1** — button-launcher, proves the GUI shape works before investing in anything fancier.
5. **Everything else** (delete-originals tool, AI labeling, ID3/MP4 signals, adjacent-files inference, French/Japanese depth) — larger, worth picking one at a time as they become the actual next priority.
