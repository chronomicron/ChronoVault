#!/usr/bin/env python3
"""
chronovault.py

Top-level launcher for the ChronoVault GUI. All the actual GUI code
lives in gui/chronovault_gui.py -- this file exists purely so the GUI
can be started as `python3 chronovault.py` from the project root,
matching the existing convention (chronovault.sh already lives here) of
running everything from ChronoVault/, rather than needing to know to
`cd gui/` first.

Running gui/chronovault_gui.py directly also still works identically --
this is a convenience, not a requirement. Path resolution inside the GUI
itself is based on the script's own location (Path(__file__).resolve()),
not the current working directory, so both launch methods behave exactly
the same regardless of which folder you happened to be sitting in when
you typed the command.

Usage:
    python3 chronovault.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "gui"))

try:
    from chronovault_gui import main
except ImportError as e:
    print(f"ERROR: Could not load the GUI ({e}).")
    print("Make sure PySide6 is installed:  pip install PySide6 --break-system-packages")
    sys.exit(1)

if __name__ == "__main__":
    main()
    