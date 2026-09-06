# ChronoVault GUI (v0.1)

A simple window with buttons that launch the existing terminal tools and stream their output live — a convenience layer, not a second way of running ChronoVault. Every tool is launched exactly as it would be from a terminal at the project root: same scripts, same `config.json` files, same working directory. Nothing about how the underlying tools work has changed to accommodate this.

## Installation

```
pip install PySide6 --break-system-packages
```

That's the only new dependency. PySide6 is the official Python binding for Qt, LGPL-licensed. No system packages needed beyond what your desktop environment already provides — see **Linux: Missing `libxcb-cursor0`**, below, if the window fails to open at all.

## Running It

From the `ChronoVault/` project root:

```
python3 chronovault.py
```

This is the recommended way — `chronovault.py` is a tiny launcher sitting at the project root (matching where `chronovault.sh` already lives). Running the GUI file directly also works identically:

```
python3 gui/chronovault_gui.py
```

If PySide6 isn't installed, either command prints a clear message and the install command, rather than a raw traceback.

### Linux: Missing `libxcb-cursor0`

If you see something like:

```
qt.qpa.plugin: Could not load the Qt platform plugin "xcb" in "" even though it was found.
Aborted (core dumped)
```

This is a missing **system** library, not a Python problem — since Qt 6.5, the `xcb` platform plugin needs `libxcb-cursor0` to handle cursor themes, and `pip install PySide6` has no way to bring along a system library. Fix:

```
sudo apt install libxcb-cursor0
```

(Debian/Ubuntu/Mint naming — check your distro's package manager if this doesn't apply.) If you're on Wayland, `QT_QPA_PLATFORM=wayland python3 chronovault.py` is a quick alternative, though installing the missing package is the more robust fix long-term.

## Layout

- **Left side** — the main pipeline: Source folder + Browse, Archive folder + Browse, **Index** and **Import** buttons, a status line, and a live-streaming read-only output panel.
- **Right side** — a narrow panel, grouped by how often you'd actually use each thing, not just logical category:
  - **Tools** — Condition Database, Audit Archive, Duplicate Finder (all touch `located_files.db` and/or the archive) — normal day-to-day pipeline use
  - *(separator)*
  - **Diagnostics** — Test Environment, Test Retrieve Data — occasional, read-only checks
  - *(separator)*
  - **Utilities** — Generate Test Data — one-off setup, not part of normal running
  - **Generate Report**, pinned to the very bottom via a stretch — only needed when something's gone wrong

Eight of the nine right/left-side action buttons (everything except Generate Report) disable together while any one is running — not a minor UI nicety, this is what prevents two tools ever writing to the same database at once. Generate Report is the one deliberate exception: it runs synchronously in plain Python, never touches the shared subprocess slot, and is meant to work even while another tool is mid-run.

## How the Archive Path Reaches Each Tool

Clicking a button that needs an archive location doesn't invent a new way of telling that tool where it is. Right before launching, the GUI reads the tool's own `config.json`, updates only its `archive_root` key, and writes it back — every other hand-configured key (`min_file_size_bytes`, `exclude_path_contains`, etc.) is read back and preserved untouched. This applies to **Importer, Audit Archive, and Duplicate Finder** — all three now sync from the same Archive field.

**Duplicate Finder is mode-aware.** Its `config.json` can be in `"source"` mode (comparing files in `located_files.db` against each other, no archive needed) or `"archive"` mode (scanning the archive folder directly). The sync logic checks this: in `source` mode, `archive_root` is left completely alone rather than getting an unused key written into it. The Archive field also isn't required to run Duplicate Finder at all — leave it blank and it just runs with whatever's already configured.

**A real bug this fixes:** an earlier version of this GUI deliberately left Audit Archive and Duplicate Finder *unsynced*, reasoning they were "supplementary" tools outside the main guided flow. In practice, this meant Importer could succeed against a real, custom archive path while these two tools silently checked the stale default (`"archive_root": "archive"`, relative to the project root) instead — both failed with a correct but confusing `Archive root 'archive' does not exist`. All three tools now consistently reflect whatever's actually in the Archive field.

## Safety Check: Refusing to Index an Existing Archive

Before Indexer does anything else, it checks whether the Source folder itself directly contains `archive_database.db` — the file only Importer ever creates. If found, it refuses, since indexing an archive and importing it again just re-copies every file into itself as `(1)`, `(2)` duplicates. The GUI shows a confirmation dialog (defaulting to **No**) instead of the terminal's plain error message; declining doesn't proceed. See `indexer/README.md` for the full detail and the `--allow-archive-source` override this uses under the hood.

## Persistent Activity Log and Crash Detection

`gui_settings.ini` keeps a rolling log of the last 50 events — every button press, every tool launch, every outcome — as a fixed-size circular buffer (50 numbered slots, a persisted index deciding which slot gets written next). This isn't just bookkeeping: it's the backbone of two real features.

**Crash detection.** Every clean shutdown writes a specific marker as the very last event. At startup, if the previous session's last recorded event *isn't* that marker, something else happened — a crash, a force-quit, a lost connection — and the GUI notes this in the output panel (not a blocking popup; a startup dialog for what might just be an ordinary force-quit would be more annoying than helpful). The exact last recorded event is preserved and shown via Generate Report.

**Why a circular buffer specifically, not a simple rewrite-the-list-every-time log:** the persisted index means a restart after a crash does *not* reset back to slot zero — the next new entry continues from wherever the counter left off. The specific slots that recorded events leading up to a crash aren't at risk of being overwritten until the buffer wraps all the way back around to them (50 more events later), not immediately on the next restart.

## Test Retrieve Data

Lists everything currently sitting in the review bucket (`date_uncertain = 1`), confirming `retrieve_data.py`'s read-only functions work and genuinely serialize to JSON. Requires the Archive field (like Audit Archive and Importer) and syncs it into `test_functions/test_retrieve_data_config.json` before running — this needed a real fix: the script originally hardcoded its archive location as a Python constant, which would have silently looked in the wrong place for anyone using a NAS, network share, or removable drive (exactly this project's real-world case, where the same physical drive can mount at a different path every time it's replugged). Now it reads `archive_root` from a config file, matching every other archive-aware tool, so the GUI's existing sync mechanism just works here too, unchanged.

## Generate Test Data

The one button that doesn't use the Source/Archive fields at all — clicking it opens its own folder picker, since generating test data is a one-off setup action unrelated to whatever the main pipeline is currently pointed at. Writes into a `test_data` **subfolder** of whatever you pick, not directly into the picked folder itself — `generate_test_data.py` scatters a dozen top-level folders (`DCIM/`, `Old_Backup_1/`, `Archives/`, etc.) into its output directory, and dumping those straight into an arbitrary chosen folder would mix them in with whatever's already there.

**Write-permission check, and a real fix along the way:** before launching, the GUI actually attempts a real write (a temp marker created then removed) rather than trusting `os.access()`. This isn't caution for its own sake — testing directly confirmed `os.access()` is unreliable in exactly the situations this project cares about most: it reports a folder as writable whenever the GUI happens to be run as root, regardless of actual permission bits (root bypasses Unix permissions entirely — confirmed by an actual write succeeding against a `chmod 444` directory), and it's also known to misreport on FAT32/exFAT removable drives — this project's primary real-world case — and NAS/NFS/SMB shares, where reported permission bits don't always reflect what's actually enforced server-side. Actually attempting the operation sidesteps all of that.

## Generate Report

Bottom-right button. Produces a plain-text report — meant to be pasted directly when asking for help — combining:

- Environment info (Python/Qt/platform versions)
- Current Source/Archive field values, and whether those paths currently exist
- The last 50 recorded events, in correct chronological order (sorted by each entry's own timestamp, not slot number, since slot order stops matching chronological order the moment the buffer wraps around even once)
- Every configured tool's script/config existence, and the actual current values of `database_path`/`archive_root`/`mode` in each `config.json` — including whether those resolved paths exist on disk
- Row counts from `located_files.db` (by status) and `archive_database.db`, if they exist

Shown inline in the output panel and saved to `gui/diagnostic_report.txt`. Entirely read-only — never modifies anything, and isn't blocked by another tool running (that's often exactly when you'd want to generate one). Reading the databases uses a read-only connection and catches "database is locked" gracefully, since it might run while another tool is mid-write.

## The Two Config Files, and Why They're Split

**`gui_config.json`** — static, developer-facing, checked into git. Where each tool's script and `config.json` live, as paths relative to the project root.

**`gui_settings.ini`** — dynamic, personal, **not** checked into git. Last-used Source/Archive paths, plus the rolling activity log described above. Safe to delete if it ever gets confused — the GUI just starts fresh with blank fields and an empty log.

## Files in This Folder

| File | Purpose |
|---|---|
| `chronovault_gui.py` | The window and all Qt-related code. |
| `gui_data.py` | Non-Qt logic — config loading, `archive_root` syncing, the activity log, diagnostic report generation — deliberately separated so it's fully testable without Qt installed at all. |
| `gui_config.json` | Static tool-location config (checked into git). |
| `gui_settings.ini` | Personal paths + activity log (not checked into git, created automatically). |
| `diagnostic_report.txt` | Generated on demand by the Diagnostic Report button; not checked into git. |

## Known Limitations (v0.1, Honestly Listed)

- No Stop button yet — closing the window while a tool is running doesn't cleanly terminate it.
- No live per-file progress during a scan — Indexer's own progress-printing improvements (checkpointing every ~100 files) aren't built yet.
- No formal Verify Status dialog yet — Generate Report covers much of the same need for now, but doesn't give a simple pass/fail checklist view.
- Condition Database has no archive-syncing need (it doesn't touch `archive_root` at all), so it's unaffected by anything described above.
- Styling is default Qt (Fusion/native) — a deliberate choice to get the mechanics right first; a visual polish pass is planned for later, not forgotten.
