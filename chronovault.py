# chronovault.py
# ChronoVault - Main Entry Point
# Description: Top-level launcher for the ChronoVault application.
# - When run directly: shows module availability and basic usage options
# - Later versions will: parse CLI arguments or launch the GUI (from chronovault/ui.py)
#
# This file lives in the project ROOT (not inside chronovault/ subfolder).
# It treats chronovault/ as a Python package so imports look like:
#   from chronovault.scanner import scan_directory
#
# Version History:
#   0.1.1 – Initial placeholder: import checker + minimal launcher skeleton

import sys
import argparse
from pathlib import Path

# ────────────────────────────────────────────────
# Try to import all modules to verify structure
# ────────────────────────────────────────────────

try:
    from chronovault import config
    from chronovault import scanner
    from chronovault import archiver
    from chronovault import database
    from chronovault import ai
    from chronovault import utils
    from chronovault import ui     # GUI will live here later

    MODULES_LOADED = {
        "config": config,
        "scanner": scanner,
        "archiver": archiver,
        "database": database,
        "ai": ai,
        "utils": utils,
        "ui": ui,
    }

    print("SUCCESS: All core modules are importable.")
    print("Available modules:")
    for name in MODULES_LOADED:
        print(f"  • chronovault.{name}")

except ImportError as e:
    print("ERROR: Cannot import one or more modules.")
    print("Make sure:")
    print("  1. You are running this file from the project ROOT directory")
    print("  2. The folder is named exactly 'chronovault' (lowercase)")
    print("  3. There is an __init__.py file inside chronovault/ (add empty one if missing)")
    print(f"Details: {e}")
    sys.exit(1)


# ────────────────────────────────────────────────
# Very basic CLI / usage demonstration
# ────────────────────────────────────────────────

def print_status():
    """Show quick status / help when run without arguments."""
    print("\nChronoVault (development skeleton)")
    print("===================================")
    print(f"Current directory: {Path.cwd()}")
    print(f"Python: {sys.version.split()[0]}")
    print("\nAvailable commands (not implemented yet):")
    print("  python chronovault.py --gui          → Launch GUI (coming soon)")
    print("  python chronovault.py --scan /path   → Scan folder (stub)")
    print("  python chronovault.py --help         → This message")


def main():
    parser = argparse.ArgumentParser(
        description="ChronoVault – Personal Photo Time Vault",
        add_help=False
    )
    parser.add_argument("--gui", action="store_true", help="Launch graphical interface")
    parser.add_argument("--scan", type=str, help="Scan a directory (placeholder)")
    parser.add_argument("--help", action="store_true", help="Show this help")

    args = parser.parse_args()

    if args.help or not any(vars(args).values()):
        print_status()
        return

    if args.gui:
        print("GUI launch requested → calling chronovault.ui.run_gui() ...")
        # Later: ui.run_gui()
        print("(GUI not implemented in v0.1.1)")

    elif args.scan:
        print(f"Scan requested for: {args.scan}")
        print("(scanner not wired up yet in main entry point)")
        # Later: items = scanner.scan_directory(args.scan)
        #        print(f"Found {len(items)} media files")

    else:
        print_status()


if __name__ == "__main__":
    main()