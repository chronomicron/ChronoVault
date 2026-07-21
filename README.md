# ChronoVault

Hey! Are you like me — with pictures and media scattered everywhere? Some on a DVD, some on an old HDD, some on a USB key, others on a NAS, and even more buried in Google Drive or Dropbox? ChronoVault is here for you.

ChronoVault searches through all of your storage locations, finds your media, and consolidates it into a single, organized, chronological archive. Later, it will also help you retrieve specific images and videos using search criteria like people, places, and things.

## The Problem

Photos and videos pile up across years of phones, cameras, cloud backups, and forgotten external drives. There's rarely one single place where everything lives, and duplicates, dumped phone exports, and messy folder structures make it worse over time. ChronoVault exists to pull all of that together into one clean, dated archive — without you having to sort through everything by hand.

## How It Works

ChronoVault is built as a set of small, focused, modular tools rather than one big application. Each tool does one job well, can be run on its own from the terminal, and will eventually be orchestrated together through a graphical interface. Keeping the tools separate means each piece can be tested, trusted, and improved independently.

The current pipeline:

1. **Indexer** — Given a JSON config (which file types to look for) and a starting folder, Indexer recursively scans the whole directory hierarchy and logs every matching file it finds into a database. It's non-destructive and purely additive — running it against several different locations (an old HDD, a USB key, a cloud-synced folder) builds up one combined inventory of everything found, skipping anything already logged.

2. **Importer** — Reads that inventory and copies the matching files into the archive, organized chronologically as `archive/YYYY/MM/DD/`. It determines the date using the best information available — photo EXIF data first, falling back to file system dates when EXIF isn't present. Importer also supports configurable filters, so you can exclude things that don't belong in a personal photo archive: browser cache thumbnails, files with no EXIF data at all, files outside a certain size range, camera thumbnail sidecar files, or anything living in a particular path. As files are copied, Importer also logs them into a second archive-specific database, tracking where each file ended up, when it was taken, and when it was added.

Each tool can be run independently from the terminal at any stage of development and testing, which keeps things simple while the project is still taking shape.

## Project Status

This is a personal, evolving project, currently very much a work in progress. The core pipeline (Indexer and Importer) is functional and has been tested against real-world messy data — phone dumps, browser caches, and all. Development is happening in small, incremental, tested steps, with each addition validated before moving to the next.

## Roadmap / Future Work

- **Archive audit tool** — a reconciliation utility that scans the archive folder directly and repairs the archive database if files were added or moved outside of ChronoVault's normal flow.
- **Duplicate detection** — using file hashing to identify and manage duplicate media across different source locations.
- **Qt GUI** — a graphical interface to orchestrate all the individual tools, configure filters, monitor progress, and browse the archive, without needing the terminal.
- **AI-assisted labeling** — a future parsing phase where an AI agent analyzes archived media and applies searchable labels — people, places, things — making it possible to later search your entire archive by content rather than just by date or filename.
- **Search and retrieval** — once labeling exists, a way to query the archive using those labels to quickly find specific memories again.

## Project Structure

```
ChronoVault/
├── README.md          (this file)
├── .gitignore
├── indexer/
│   ├── indexer.py
│   ├── config.json
│   └── README.md      (usage details for Indexer)
├── importer/
│   ├── importer.py
│   ├── config.json
│   └── README.md      (usage details for Importer)
├── located_files.db   (created by Indexer — not tracked in git)
└── archive/            (created by Importer — not tracked in git)
```

## Requirements

- Python 3
- [Pillow](https://pypi.org/project/Pillow/) (`pip install Pillow`) — used for reading EXIF metadata from photos

## Getting Started

See the README inside each tool's subfolder (`indexer/README.md` and `importer/README.md`) for exact usage instructions, configuration options, and examples.

## Philosophy

ChronoVault is being built deliberately, in small steps: write a small piece, test it against real data, commit it, then move to the next piece. Nothing here is meant to be a finished product on day one — it's meant to grow carefully, tool by tool, into something genuinely useful for consolidating and preserving personal media over the long term.
