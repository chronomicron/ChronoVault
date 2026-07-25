# ChronoVault

Hey! Are you like me — with pictures and media scattered everywhere? Some on a DVD, some on an old HDD, some on a USB key, others on a NAS, and even more buried in Google Drive or Dropbox? ChronoVault is here for you.

ChronoVault searches through all of your storage locations, finds your media, and consolidates it into a single, organized, chronological archive. Later, it will also help you retrieve specific images and videos using search criteria like people, places, and things.

## The Problem

Photos and videos pile up across years of phones, cameras, cloud backups, and forgotten external drives. There's rarely one single place where everything lives, and duplicates, dumped phone exports, and messy folder structures make it worse over time. ChronoVault exists to pull all of that together into one clean, dated archive — without you having to sort through everything by hand.

## How It Works

ChronoVault is built as a set of small, focused, modular tools rather than one big application. Each tool does one job well, can be run on its own from the terminal, and can also be launched from a simple menu (`chronovault.sh`). Keeping the tools separate means each piece can be tested, trusted, and improved independently.

The current pipeline:

1. **Indexer** — Given a JSON config (which file types to look for) and a starting folder, Indexer recursively scans the whole directory hierarchy and logs every matching file it finds into a database. It's non-destructive and purely additive — running it against several different locations (an old HDD, a USB key, a cloud-synced folder) builds up one combined inventory of everything found, skipping anything already logged.

2. **Importer** — Reads that inventory and copies the matching files into the archive, organized chronologically as `archive/YYYY/MM/DD/`. Importer also supports configurable filters, so you can exclude things that don't belong in a personal photo archive: browser cache thumbnails, files with no EXIF data at all, files outside a certain size range, camera thumbnail sidecar files, or anything living in a particular path. As files are copied, Importer also logs them into a second archive-specific database, tracking where each file ended up, when it was taken, when it was added, and how confident ChronoVault is in that date (see **Smarter Dates** below).

3. **Audit Archive** — A read-only reconciliation tool. It scans the archive folder on disk and compares it against the archive database, reporting anything undocumented (on disk but not logged), missing (logged but no longer on disk), or misplaced (sitting in a date folder that doesn't match its recorded date). It never modifies anything — it only reports, and along the way it caches file hashes for the next tool.

4. **Duplicate Finder** — Hashes files (using the hashes Audit already cached where possible) and groups identical content together, so you can see exactly which files are true duplicates and how much space could be reclaimed. It can check either the pre-import inventory (`located_files.db`) or the archive itself, since duplicates can sneak into the archive by hand, not just through Importer.

Each tool can be run independently from the terminal, or through the `chronovault.sh` menu, which ties all four together in one place.

### Smarter Dates

Figuring out when a photo or video was actually taken isn't always straightforward — EXIF data can be missing, wrong, or disagree with the file's own filesystem date. That logic lives in its own small package, `analyze_date/`, which Importer calls rather than working it out itself. Given whatever evidence is available for a file, it returns a chosen date, a **confidence score (0–100)**, and a short explanation of its reasoning — for example, `"EXIF (DateTimeOriginal) -- confirmed by filesystem creation date"`.

Files ChronoVault isn't confident about (currently: anything with no EXIF at all, or an implausible date) aren't guessed into a possibly-wrong date folder. Instead they're routed to `archive/_review_needed/`, so they're easy to find and sort out by hand later, rather than silently misfiled. `analyze_date` is deliberately built to combine *however many* pieces of evidence it's given — right now that's just EXIF and the filesystem date, but it's designed so that future signals (like a date embedded in the filename, or a camera's `.THM` sidecar file) can be added later without restructuring the scoring logic.

### Testing Without Real Photos

`generate_test_data/generate_test_data.py` generates a realistic, messy folder tree of small fake images — some with solid EXIF, some with EXIF that disagrees with the filesystem date, some with no EXIF at all, some with implausible dates, plus deliberate duplicates and a few unreadable junk files. It's useful for trying out any tool, or testing a change, without needing to risk real photos or wait on large files.

## Project Status

This is a personal, evolving project, currently very much a work in progress. All four core tools (Indexer, Importer, Audit Archive, Duplicate Finder) are functional, tied together by `chronovault.sh`, and have been tested against real-world messy data — phone dumps, browser caches, renamed and duplicated files, and all. Date determination has moved beyond a simple EXIF-or-fallback check into a scored, explainable confidence system, with a review bucket for anything uncertain. Development is happening in small, incremental, tested steps, with each addition validated before moving to the next.

## Roadmap / Future Work

**Done:**
- ~~Archive audit tool~~ — Audit Archive, reconciles the archive folder against the database.
- ~~Duplicate detection~~ — Duplicate Finder, SHA-256 based, covers both pre-import and archive-side duplicates.
- ~~Confidence-scored date determination~~ — `analyze_date` module, replacing the old binary "uncertain" flag.
- ~~Review bucket for low-confidence files~~ — `_review_needed/`, instead of guessing a possibly-wrong folder.
- ~~Repeatable test data~~ — `generate_test_data.py`, for testing without real photos.

**Still ahead:**
- **Additional date-evidence sources** — teaching `analyze_date` to also read dates out of filenames (e.g. `IMG_20260720_123957.jpg`) and camera `.THM` sidecar files, for even higher confidence when multiple sources agree.
- **Cross-copy duplicate date resolution** — when Duplicate Finder finds identical files sitting in two different date folders, there's currently no way to tell ChronoVault which one is "right." Planned as a GUI review step: show the copies side by side, let the user pick, with an option to apply that decision to future finds automatically.
- **"Apply fixes" tool** — a follow-up to Audit Archive that can act on its report: add undocumented files to the database, move misplaced files, clean up orphaned entries for files that no longer exist.
- **Qt GUI** — a graphical interface to orchestrate all the individual tools, configure filters, monitor progress, review low-confidence and duplicate files, and browse the archive, without needing the terminal.
- **AI-assisted labeling** — a future tool that analyzes archived media and applies searchable labels — people, places, things — following the same "hand it evidence, get back a scored answer" pattern as `analyze_date`, so a future labeling engine (e.g. a local AI model) can be swapped in without the rest of ChronoVault needing to know how it works.
- **Search and retrieval** — once labeling exists, a way to query the archive using those labels to quickly find specific memories again.
- **Minor cleanup** — some EXIF-reading code is currently duplicated between `importer.py` and `audit_archive.py`; low priority, since ChronoVault deliberately favors small independent tools over shared libraries unless a real need for one shows up.

## Project Structure

```
ChronoVault/
├── README.md              (this file)
├── Database_schema.md
├── .gitignore
├── chronovault.sh          (menu launcher for all four tools)
├── indexer/
│   ├── indexer.py
│   ├── config.json
│   └── README.md
├── importer/
│   ├── importer.py
│   ├── config.json
│   └── README.md
├── audit_archive/
│   ├── audit_archive.py
│   └── config.json
├── duplicate_finder/
│   ├── duplicate_finder.py
│   └── config.json
├── analyze_date/
│   ├── analyze_date.py     (date confidence scoring, used by Importer)
│   └── __init__.py
├── generate_test_data/
│   └── generate_test_data.py
├── located_files.db        (created by Indexer — not tracked in git)
├── archive/                 (created by Importer — not tracked in git)
│   └── _review_needed/      (low-confidence files land here, not a date folder)
└── test_data/                (created by generate_test_data.py — not tracked in git)
```

## Requirements

- Python 3
- [Pillow](https://pypi.org/project/Pillow/) (`pip install Pillow`) — used for reading and (for test data) writing EXIF metadata

## Getting Started

Run `./chronovault.sh` from the project root for a simple menu covering all four tools, or run any tool directly, e.g. `python3 importer/importer.py importer/config.json`. See the README inside each tool's subfolder for exact usage instructions, configuration options, and examples (note: Audit Archive and Duplicate Finder don't have their own README yet — still on the list).

Want to try things out without using real photos? Run `python3 generate_test_data/generate_test_data.py` first to build a sample folder tree, then point Indexer at it.

## Philosophy

ChronoVault is being built deliberately, in small steps: write a small piece, test it against real data, commit it, then move to the next piece. Nothing here is meant to be a finished product on day one — it's meant to grow carefully, tool by tool, into something genuinely useful for consolidating and preserving personal media over the long term. Shared code is only extracted into its own module when there's a real, proven reason to reuse it (like `analyze_date`) — not preemptively.
