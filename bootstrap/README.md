# ChronoVault Bootstrap

The bootstrap folder contains the first-run launchers and the Python initializer.
The launcher finds a usable Python interpreter; `initialize.py` checks Python
dependencies and validates the source and archive folders before the user runs
the pipeline.

## Linux and macOS

From the project root, run:

```bash
./bootstrap/bootstrap.sh
```

The script checks for Python 3.8 or newer, then starts `initialize.py`. If
Python is missing, too old, or cannot run, it prints next steps and stops. It
does not install Python or any other software.

You can pass the two folder paths as options:

```bash
./bootstrap/bootstrap.sh \
  --source-root "/media/me/Camera Drive" \
  --archive-root "/media/me/ChronoVault Archive"
```

If either option is omitted, the initializer asks for that path in the
terminal. The source folder must already exist and be readable. The archive
destination is created if needed and tested with a temporary write. Successful
paths are saved to the GUI's personal `gui/gui_settings.ini` so they appear as
the last-used Source and Archive paths when the GUI opens.

This is not yet a complete first-run pipeline setup. The saved paths are not
currently synchronized to every tool's database and report configuration, and
the initializer exits after saving instead of launching the GUI. The GUI still
uses its Test folder workflow to update those tool configurations.

## What initialization checks

- Python 3.8 or newer and the SQLite module.
- Pillow, which is required by the current image workflow.
- Optional packages used by OCR and ISO archive listing. Missing optional
  packages are reported with installation guidance but do not block setup.
- An offscreen Qt startup check that imports the ChronoVault GUI, constructs its
  main window, and processes a display event without opening a visible window
  or changing GUI settings. On Linux, it also checks the Qt XCB plugin for
  missing shared libraries and names the Debian/Ubuntu package for
  `libxcb-cursor0` when applicable.
- If a root `requirements.txt` is added, ordinary package-name requirements
  are checked for installation and missing packages are reported with a manual
  pip command. Version constraints are not evaluated yet.
- The selected source is a readable directory.
- The archive destination exists or can be created, and accepts a temporary
  file write.

Packages are never installed automatically. Install any required missing
dependency yourself, then run the bootstrap again. Initialization does not
create either database: Indexer creates `located_files.db`, and Importer
creates `archive_database.db` when it first imports into the archive.
The GUI check does not verify that the current desktop session can display a
window; it checks Qt and ChronoVault window startup without requiring a display.
Terminal use remains available when the optional GUI check fails.

## Windows

`bootstrap.bat` is currently a placeholder. Windows users must start the Python
initializer manually after installing Python 3.8 or newer:

```text
py bootstrap\initialize.py --source-root "D:\Photos" --archive-root "E:\ChronoVault"
```

## Files

| File | Purpose |
|---|---|
| `bootstrap.sh` | Python runtime check and launcher for Linux/macOS. |
| `bootstrap.bat` | Placeholder for a future native Windows runtime check and launcher. |
| `initialize.py` | Dependency checks, source/archive prompts and access checks, and GUI path persistence. |

This is setup assistance, not an installer. For dependency details, see the
root README and the relevant tool README files.
