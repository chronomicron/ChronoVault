# ChronoVault GUI (v0.1)

A simple window with buttons that launch the existing terminal tools (currently Indexer and Importer) and stream their output live — a convenience layer, not a second way of running ChronoVault. Every tool is launched exactly as it would be from a terminal at the project root: same scripts, same `config.json` files, same working directory. Nothing about how Indexer or Importer themselves work has changed to accommodate this.

## Installation

```
pip install PySide6 --break-system-packages
```

That's the only new dependency. PySide6 is the official Python binding for Qt, LGPL-licensed. No system packages needed — this is a pure Python install, unlike Tesseract/OpenCV for OCR.

## Running It

From the `ChronoVault/` project root:

```
python3 chronovault.py
```

This is the recommended way — `chronovault.py` is a tiny launcher sitting at the project root (matching where `chronovault.sh` already lives), so running the GUI feels consistent with everything else in this project always being run from the root.

Running the GUI file directly also works identically:

```
python3 gui/chronovault_gui.py
```

Both end up in exactly the same place — `chronovault.py`'s only job is finding `gui/chronovault_gui.py` and calling its `main()`.

If PySide6 isn't installed, either command prints a clear message and the install command, rather than a raw traceback.

## What v0.1 Actually Does

- **Source folder** field + Browse — pick any real folder on disk to search. Not sandboxed to `chronovault_test/` — this GUI is meant to work against real locations from day one, since none of the tools it drives (Indexer, Importer) delete or modify anything.
- **Archive folder** field + Browse — pick where the dated archive should be built.
- **Index** button — runs Indexer against the source folder.
- **Import** button — runs Importer against the archive folder.
- Both buttons disable while either tool is running — this isn't a minor UI nicety, it's there specifically to prevent two tools ever writing to the same database at once.
- A status line shows what's currently happening.
- A read-only output panel streams each tool's terminal output live as it runs, not just after it finishes.

**Deliberately not in v0.1:** a Stop button (needs a fix to `indexer.py`'s commit behavior first, so interrupting a scan actually preserves the files found so far rather than losing the whole run), and a Verify Status dialog (needs a shared "expected config keys" definition that a future `--init` flag will also use, so the two never quietly disagree about what "correct" looks like). Both are natural next additions.

## The Two Data Files, and Why They're Split

**`gui_config.json`** — static, developer-facing, checked into git. Says where each tool's script and `config.json` live, as paths relative to the project root. You'd only ever touch this if you moved a script somewhere else in the repo.

**`gui_settings.ini`** — dynamic, personal, **not** checked into git (see `.gitignore`). Remembers your last-used Source and Archive folders between sessions, purely so the fields aren't empty every time you open the window. Created automatically the first time you close the app; safe to delete if it ever gets confused — the GUI just starts with blank fields again.

## How the Archive Path Actually Reaches Importer

Worth understanding, since it's a deliberate design choice: clicking **Import** doesn't invent a new way of telling Importer where the archive is. Instead, right before launching, the GUI reads `importer/config.json`, updates only its `archive_root` key, and writes it back — every other key you might have hand-configured (`min_file_size_bytes`, `exclude_path_contains`, etc.) is read back and preserved untouched. Importer itself has no idea a GUI exists; it just reads its config file exactly as it always has. This means anything that works from the terminal keeps working identically, and the GUI can never drift out of sync with what the config file actually says.

## Files in This Folder

| File | Purpose |
|---|---|
| `chronovault_gui.py` | The actual window and all Qt-related code. |
| `gui_data.py` | Non-Qt logic (loading `gui_config.json`, updating `archive_root`) — deliberately separated so it's testable without Qt installed at all, and reusable if a different front end is ever built. |
| `gui_config.json` | Static tool-location config (checked into git). |
| `gui_settings.ini` | Your personal last-used paths (not checked into git, created automatically). |

## Known Limitations (v0.1, Honestly Listed)

- No Stop button yet — closing the window while a tool is running doesn't cleanly terminate it.
- No live per-file progress during a scan — Indexer's own progress-printing improvements (checkpointing every ~100 files) aren't built yet, so a genuinely deep hierarchy will look idle for a while, with only the indeterminate sense that "it's still working."
- No crash/interrupted-scan detection or resume-prompt yet — depends on the `indexer_runs` tracking table design (see `roadmap.md`), not yet implemented.
- Styling is default Qt (Fusion/native) — a deliberate choice to get the mechanics right first; a visual polish pass is planned for later, not forgotten.
