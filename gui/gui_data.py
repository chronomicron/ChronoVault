"""
gui/gui_data.py

Non-GUI logic for the ChronoVault GUI: locating the project root, loading
the static tool-location config (gui_config.json), and safely updating a
tool's config.json (currently just Importer's archive_root) before a run.

Deliberately has NO PySide6 import anywhere in this file -- kept separate
from chronovault_gui.py specifically so this logic is testable entirely
on its own, without Qt installed at all. This also means a future
non-Qt front end (unlikely, but the same reasoning already applied to
retrieve_data/write_data being UI-agnostic) could reuse it without
dragging in a GUI toolkit.
"""

import json
from pathlib import Path

GUI_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = GUI_DIR.parent
GUI_CONFIG_PATH = GUI_DIR / "gui_config.json"
GUI_SETTINGS_PATH = GUI_DIR / "gui_settings.ini"


def load_gui_config():
    """
    Load the static tool-location config -- which script and config.json
    each tool uses. Paths inside this file are relative to PROJECT_ROOT,
    exactly like you'd type them at a terminal after cd-ing into
    ChronoVault/ -- kept that way deliberately so a GUI-launched run and
    a terminal-launched run are indistinguishable to the underlying tool.

    Returns None (after printing why) rather than raising, so the caller
    (the GUI) can show a friendly dialog instead of a raw traceback.
    """
    if not GUI_CONFIG_PATH.exists():
        print(f"ERROR: {GUI_CONFIG_PATH} not found.")
        return None
    try:
        with open(GUI_CONFIG_PATH, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: {GUI_CONFIG_PATH} is not valid JSON: {e}")
        return None


def update_archive_root_in_config(config_relative_path, archive_path):
    """
    Write a chosen archive folder into a tool's config.json (currently
    only Importer has archive_root) -- done right before that tool is
    actually launched, not on every keystroke. The tool itself stays
    completely unaware a GUI exists; it just reads whatever archive_root
    its config.json says, same as if a person had edited the file by
    hand. Every other key already in the file is read back and preserved
    untouched -- this is a targeted update, not a fresh overwrite that
    could silently drop a setting a person configured by hand (extra
    filters, size limits, etc).
    """
    config_path = PROJECT_ROOT / config_relative_path
    with open(config_path, 'r') as f:
        config = json.load(f)
    config['archive_root'] = archive_path
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=4)
        