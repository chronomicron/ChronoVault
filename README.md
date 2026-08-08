# ChronoVault

Hey! Are you like me — with pictures and media scattered everywhere? Some on a DVD, some on an old HDD, some on a USB key, others on a NAS, and even more buried in Google Drive or Dropbox? ChronoVault is here for you.

ChronoVault searches through all of your storage locations, finds your media, and consolidates it into a single, organized, chronological archive. It also helps you review and correct anything it wasn't confident about, using whatever evidence is available — camera metadata, GPS, editing software history, and, when nothing else exists, an OCR scan of a printed date stamp.

## The Problem

Photos and videos pile up across years of phones, cameras, cloud backups, and forgotten external drives. There's rarely one single place where everything lives, and duplicates, dumped phone exports, and messy folder structures make it worse over time. ChronoVault exists to pull all of that together into one clean, dated archive — without you having to sort through everything by hand.

## How It Works

ChronoVault is built as a set of small, focused, modular tools rather than one big application. Each tool does one job well, can be run on its own from the terminal, and can also be launched from a simple menu (`chronovault.sh`).

The current pipeline:

1. **Indexer** — Recursively scans a starting folder for matching file types and logs everything into a database. Non-destructive, purely additive, safe to run against multiple locations.

2. **Importer** — Copies matching files into the archive, organized as `archive/YYYY/MM/DD/`, using `analyze_date` (see below) to decide the date and how confident to be in it. Files it isn't confident about go to `archive/_review_needed/` instead of a guessed folder.

3. **Audit Archive** — Read-only reconciliation: compares the archive folder on disk against the database, reporting anything undocumented, missing, or misplaced. Never modifies anything.

4. **Duplicate Finder** — Hashes files and groups identical content together, so you can see true duplicates and how much space could be reclaimed.

5. **`retrieve_data` / `write_data`** — The review workflow for anything sitting in `_review_needed/`. `retrieve_data` is a UI-agnostic, read-only data layer (usable from a terminal script, a future desktop app, or a future web app — nothing about it assumes which); `write_data` applies a person's corrected date, physically moving the file and updating the database, while deliberately preserving the *original* algorithmic evidence rather than overwriting it.

Each tool can be run independently from the terminal, or through the `chronovault.sh` menu.

### Smarter Dates

Figuring out when a photo was actually taken isn't always straightforward. `analyze_date` handles this as its own subsystem: given whatever evidence is available for a file, it returns a chosen date, a **confidence score (0–100)**, and a short explanation of its reasoning.

Evidence comes from multiple independent sources, each with its own trustworthiness, combined rather than just picked from:

| Source | Roughly | Notes |
|---|:---:|---|
| EXIF GPS timestamp | 98 | From the satellite signal, immune to a wrong camera clock |
| EXIF DateTimeOriginal | 95 | |
| TIFF's native DateTime tag | 90 | |
| XMP CreateDate (Photoshop, Lightroom) | 80 | |
| OCR corner date-stamp scan | 60 | **Opt-in only** — slow, and only useful when nothing else exists |
| Filesystem date | 30 | Fallback of last resort |

Multiple sources agreeing pushes confidence up; disagreement pulls it down. Files ChronoVault isn't confident about are routed to `archive/_review_needed/` rather than guessed into a possibly-wrong folder.

`analyze_date` is deliberately built so a file's *type* determines which evidence sources even get checked (JPEG-family files get EXIF/GPS/XMP; TIFF gets its own tag; a future MP3/MP4 signal would come from entirely different places) — see `analyze_date/README.md` for the full architecture. The eventual goal is genuinely media-independent archiving, not just photos.

### Testing Without Real Photos

`generate_test_data/generate_test_data.py` generates a realistic, messy folder tree of small fake files covering every confidence scenario across every currently-supported format (JPEG with EXIF/GPS/XMP variations, TIFF, BMP, a RAW approximation, THM sidecars) plus deliberate duplicates and unreadable junk files — useful for trying out any tool, or testing a change, without risking real photos.

## Project Status

Core pipeline (Indexer, Importer, Audit Archive, Duplicate Finder) is functional and tested against real-world messy data. Date determination combines five independent evidence sources with a scored, explainable confidence system. The review-workflow data layer (`retrieve_data`/`write_data`) exists and is tested, designed to work equally from a terminal script or a future GUI. OCR corner-stamp detection exists as a real, working, opt-in feature — extensively tested against real downloaded photos, with honestly-documented real limitations (Japanese/kanji stamps and dot-matrix CCTV fonts are both still unsolved). Development continues in small, incremental, tested steps.

## Roadmap / Future Work

**Done:**
- ~~Archive audit tool~~, ~~duplicate detection~~, ~~confidence-scored date determination~~, ~~review bucket for low-confidence files~~, ~~repeatable test data~~
- ~~GPS timestamp signal~~ — independently verified via satellite time
- ~~XMP metadata signal~~ — Photoshop/Lightroom CreateDate and ModifyDate
- ~~TIFF format support~~ — native DateTime tag
- ~~OCR corner-stamp detection~~ — opt-in, real-world tested, real limitations documented
- ~~Review-workflow data layer~~ — `retrieve_data`/`write_data`, UI-agnostic by design
- ~~`analyze_date` architecture split~~ — orchestration layer + `image_tools/` per-format extractors

**Still ahead:**
- **MP3/MP4 support** — `audio_tools/` and `video_tools/` exist as placeholder folders with a documented plan (ID3 tags, MP4 container metadata), genuinely unbuilt.
- **`analyze_date` as a standalone terminal tool** — currently a pure library, called by Importer. A CLI wrapper (config-driven, threaded, folder- or database-input, report-file or database output) is designed but not built.
- **Additional date-evidence sources** — filename parsing, `.THM`-style camera sidecar files beyond what's already supported.
- **Cross-copy duplicate date resolution** — when Duplicate Finder finds identical files in different date folders, there's no way yet to tell ChronoVault which one is right. Planned as a GUI review step.
- **"Apply fixes" tool for Audit Archive's report** — add undocumented files to the database, move misplaced files, clean up orphaned entries.
- **Qt GUI** — to orchestrate everything without the terminal; `retrieve_data`/`write_data` were specifically designed to plug into this without rework.
- **AI-assisted labeling** — following the same "evidence in, scored answer out" pattern as `analyze_date`.
- **Search and retrieval** — once labeling exists.

## Project Structure

```
ChronoVault/
├── README.md
├── Database_schema.md
├── .gitignore
├── chronovault.sh              (menu launcher / step-by-step test runner)
├── indexer/
├── importer/
├── audit_archive/
├── duplicate_finder/
├── analyze_date/
│   ├── analyze_date.py          (orchestration: dispatch, scoring, combination)
│   ├── image_tools/              (EXIF, GPS, XMP, TIFF, OCR -- all real, tested)
│   ├── audio_tools/              (placeholder -- planned, not built)
│   └── video_tools/              (placeholder -- planned, not built)
├── retrieve_data/                (read-only data layer for the review workflow)
├── write_data/                   (applies corrections -- the mutating twin of retrieve_data)
├── generate_test_data/
├── test_functions/                (throwaway debugging/verification scripts)
├── located_files.db              (created by Indexer -- not tracked in git)
├── archive/                       (created by Importer -- not tracked in git)
│   └── _review_needed/            (low-confidence files land here)
└── test_data/                      (created by generate_test_data.py -- not tracked in git)
```

## Requirements

- Python 3
- [Pillow](https://pypi.org/project/Pillow/) — reading/writing image metadata
- For OCR corner-stamp detection specifically (optional feature): `tesseract-ocr` (system package), `pytesseract`, `opencv-python-headless`, `numpy` — run `python3 test_functions/test_env.py` to check what's installed and what's missing

## Getting Started

Run `python3 test_functions/test_env.py` first to confirm your environment has everything installed. Then run `./chronovault.sh` from the project root for a step-by-step menu (cleanup, generate test data, index, import, audit, find duplicates), or run any tool directly. See the README inside each tool's subfolder for exact usage.

Want to try things out without using real photos? `chronovault.sh` option 2 generates a sample folder tree for you.

## Philosophy

ChronoVault is being built deliberately, in small steps: write a small piece, test it against real data, commit it, then move to the next piece. Shared code is only extracted into its own module when there's a real, proven reason to reuse it — not preemptively. When a module grows past the point where one file makes sense (as happened with `analyze_date`), it gets split, but only once that growth has actually happened, not in anticipation of it.
