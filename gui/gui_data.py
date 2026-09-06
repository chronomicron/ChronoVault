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
import sys
import platform
import sqlite3
import configparser
from pathlib import Path
from datetime import datetime

GUI_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = GUI_DIR.parent
GUI_CONFIG_PATH = GUI_DIR / "gui_config.json"
GUI_SETTINGS_PATH = GUI_DIR / "gui_settings.ini"

PATHS_SECTION = 'paths'
LOG_SECTION = 'log'
MAX_LOG_ENTRIES = 50
CLEAN_SHUTDOWN_MARKER = "Application closed (clean shutdown)"


def load_settings():
    """
    Load gui_settings.ini (starting fresh if it doesn't exist yet),
    ensuring both expected sections exist. Centralized here rather than
    in chronovault_gui.py so this is testable without Qt, and so there's
    one place defining what a "valid" settings file looks like.
    """
    settings = configparser.ConfigParser()
    settings.read(GUI_SETTINGS_PATH)
    if not settings.has_section(PATHS_SECTION):
        settings.add_section(PATHS_SECTION)
    if not settings.has_section(LOG_SECTION):
        settings.add_section(LOG_SECTION)
    return settings


def save_settings(settings):
    with open(GUI_SETTINGS_PATH, 'w') as f:
        settings.write(f)


def _get_next_index(settings):
    try:
        return int(settings[LOG_SECTION].get('next_index', '0'))
    except ValueError:
        return 0


def get_log_entries(settings):
    """
    Return every recorded event, oldest first, ordered by each entry's
    own embedded timestamp -- NOT by slot number. Slots are a fixed-size
    circular buffer (see append_log_entry), so slot number stops
    matching chronological order as soon as the buffer wraps around even
    once; the timestamp inside each entry is the only reliable ordering
    signal. Microsecond precision means real, human-paced button
    presses will never collide, and sorting the "ISO-timestamp |
    description" strings directly works correctly without parsing them
    into datetime objects first -- ISO 8601 sorts correctly as plain text.
    """
    if not settings.has_section(LOG_SECTION):
        return []
    entries = [settings[LOG_SECTION][key] for key in settings[LOG_SECTION] if key.startswith('entry_')]
    entries.sort()
    return entries


def get_last_entry(settings):
    """
    The single most recently written entry, or None if nothing has ever
    been logged (a brand new install, or a fresh gui_settings.ini).
    """
    entries = get_log_entries(settings)
    return entries[-1] if entries else None


def append_log_entry(settings, description):
    """
    Record a timestamped event into a fixed-size circular buffer --
    MAX_LOG_ENTRIES (50) slots, each written via next_index modulo
    MAX_LOG_ENTRIES, with next_index itself persisted so it survives an
    app restart. Deliberately NOT a rewrite-the-whole-list-every-time
    approach: writing a new event only ever touches one slot plus the
    index counter.

    This is also what gives the crash-preservation property real
    meaning: after a crash, restarting does NOT reset the index back to
    zero -- the next entry continues from wherever the counter left off,
    so the specific slots that recorded events leading up to the crash
    aren't at risk of being overwritten until the buffer wraps all the
    way back around to them (50 more events later), not immediately.

    Does NOT write to disk itself -- the caller persists via
    save_settings(), same as everywhere else in this module.
    """
    if not settings.has_section(LOG_SECTION):
        settings.add_section(LOG_SECTION)

    next_index = _get_next_index(settings)
    slot = next_index % MAX_LOG_ENTRIES

    timestamp = datetime.now().isoformat(timespec='microseconds')
    settings[LOG_SECTION][f'entry_{slot}'] = f"{timestamp} | {description}"
    settings[LOG_SECTION]['next_index'] = str(next_index + 1)


def check_and_log_startup(settings):
    """
    Call once at application startup, before any other logging this
    session. Looks at whatever the previous session's LAST recorded
    event was (before this call adds anything new): if it isn't the
    clean-shutdown marker, the previous session ended some other way --
    a crash, a force-kill, a lost connection, the machine losing power --
    and that's worth surfacing rather than silently starting fresh as if
    nothing happened.

    Always logs "Application started" (and, if a crash is detected, a
    second WARNING entry naming exactly what the last thing recorded
    was) before returning. Returns True if the previous session appears
    to have ended uncleanly, False otherwise -- including the case where
    there's no previous session at all (a fresh install has nothing to
    have crashed).
    """
    last_entry = get_last_entry(settings)
    crashed = last_entry is not None and CLEAN_SHUTDOWN_MARKER not in last_entry

    append_log_entry(settings, "Application started")
    if crashed:
        append_log_entry(
            settings,
            f"WARNING: previous session did not shut down cleanly (last recorded event: {last_entry})"
        )
    return crashed


def log_clean_shutdown(settings):
    """Call once, right before the application actually closes -- this marker is the whole basis of crash detection above."""
    append_log_entry(settings, CLEAN_SHUTDOWN_MARKER)


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


def check_folder_writable(folder):
    """
    Actually attempts a real write (a temp marker folder, created then
    immediately removed) rather than trusting os.access(), which is a
    known-unreliable predictor of real write capability in exactly the
    situations this project cares about most:

    - Root bypasses Unix permission bits entirely (DAC_OVERRIDE) --
      confirmed directly: os.access() reported a chmod 444 directory as
      writable while running as root, and an actual write attempt
      against it genuinely succeeded. Technically accurate for root,
      but a reminder that permission bits alone don't tell the whole
      story.
    - FAT32/exFAT removable drives -- the primary real-world case this
      whole project targets (USB keys, old external HDDs) -- often
      don't support Unix permission bits meaningfully at all; what
      stat() reports can be synthetic and unrelated to real write
      capability.
    - NAS/NFS/SMB shares can enforce permissions server-side in ways
      that don't match what the client reports locally.

    Actually attempting the operation sidesteps all three by testing
    the real thing directly, not inferring it from metadata that might
    not reflect reality.

    Returns (True, None) if the folder is genuinely writable, or
    (False, error_message) if not.
    """
    try:
        test_path = Path(folder) / ".chronovault_write_test"
        test_path.mkdir(exist_ok=True)
        test_path.rmdir()
        return True, None
    except OSError as e:
        return False, str(e)


def check_archive_destination(archive_path):
    """
    Classify an archive destination folder into one of three states, so
    the GUI can decide whether a confirmation is actually warranted
    before Importer writes into it for the first time -- creating
    archive_database.db and its YYYY/MM/DD folders there.

        'existing_archive'    -- archive_database.db already present;
                                  clearly an established archive,
                                  nothing to ask about.
        'empty_or_new'        -- the folder doesn't exist yet, or exists
                                  but is completely empty; clearly safe
                                  to create a new archive here, nothing
                                  to ask about.
        'nonempty_no_archive' -- the folder exists and has OTHER content
                                  in it, but no archive_database.db.
                                  This is the genuinely ambiguous case:
                                  was this folder really meant to BE the
                                  archive, or did a too-high-up folder
                                  get selected by mistake? Found via a
                                  real mistake, not a hypothetical:
                                  generating test data into a folder,
                                  then separately pointing Import at
                                  that SAME top-level folder, mixed the
                                  archive's own database and date
                                  folders directly alongside the
                                  unrelated generated test data.

    Only the third case is worth interrupting anyone for -- a blanket
    "are you sure?" on every brand-new archive would just be friction
    people click through without reading, defeating the point.
    """
    path = Path(archive_path)

    if (path / "archive_database.db").exists():
        return 'existing_archive'

    if not path.exists():
        return 'empty_or_new'

    try:
        has_content = any(path.iterdir())
    except OSError:
        # Can't even list it (permissions, a transient removable-media
        # hiccup) -- don't block on a check that can't actually be
        # performed; Importer's own error handling takes it from here.
        return 'empty_or_new'

    return 'nonempty_no_archive' if has_content else 'empty_or_new'


def check_looks_like_archive(source_path):
    """
    Mirrors indexer.py's own archive-source detection exactly, by
    importing and calling that SAME function rather than keeping a
    second copy here that could quietly drift out of sync if the
    detection logic is ever refined (e.g. to also check nested
    archives, not just the search root itself).
    """
    sys.path.insert(0, str(PROJECT_ROOT / "indexer"))
    from indexer import looks_like_chronovault_archive
    return looks_like_chronovault_archive(source_path)


def update_archive_root_in_config(config_relative_path, archive_path):
    """
    Write a chosen archive folder into a tool's config.json's
    archive_root -- done right before that tool is actually launched,
    not on every keystroke. The tool itself stays completely unaware a
    GUI exists; it just reads whatever archive_root its config.json
    says, same as if a person had edited the file by hand. Every other
    key already in the file is read back and preserved untouched.

    Mode-aware: if the config has a 'mode' key (currently only Duplicate
    Finder's config does) set to anything other than 'archive' (e.g.
    'source'), archive_root is left alone entirely -- it isn't relevant
    in that mode, and writing it would just be unused clutter. Configs
    with no 'mode' key at all (Importer, Audit Archive) are always
    updated -- they only ever have one interpretation of archive_root.

    Found necessary by a real failure, not a hypothetical: Audit Archive
    and Duplicate Finder were originally left deliberately unsynced,
    using whatever was already in their own config.json, on the
    reasoning that they were "supplementary" tools outside the main
    guided flow. In practice, a person using a custom archive location
    (the entire point of the GUI's Archive field) had Importer succeed
    against the real path while these two silently checked a stale
    default ("archive_root": "archive", relative to the project root)
    instead -- both failed cleanly with "Archive root 'archive' does not
    exist," a correct error, but a confusing and entirely avoidable one.
    """
    config_path = PROJECT_ROOT / config_relative_path
    with open(config_path, 'r') as f:
        config = json.load(f)

    mode = config.get('mode')  # None for configs with no concept of "mode" at all
    if mode is not None and mode != 'archive':
        return  # e.g. Duplicate Finder in 'source' mode -- archive_root isn't relevant here

    config['archive_root'] = archive_path
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=4)


def _describe_tool_config(tool_name, tool_entry):
    """
    One tool's diagnostic block: does its script/config exist on disk,
    and what do the keys that actually matter for this report
    (database_path, archive_root, mode) currently say -- including
    whether whatever path they point to actually exists. Not a full
    config dump; just the keys relevant to diagnosing "why did this
    tool fail," which is this report's entire purpose.
    """
    lines = [f"[{tool_name}]"]
    script_path = PROJECT_ROOT / tool_entry['script']
    config_path = PROJECT_ROOT / tool_entry['config']
    lines.append(f"  script: {tool_entry['script']}  (exists: {script_path.exists()})")
    lines.append(f"  config: {tool_entry['config']}  (exists: {config_path.exists()})")

    if not config_path.exists():
        return "\n".join(lines)

    try:
        with open(config_path) as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        lines.append(f"  ERROR: config.json is not valid JSON: {e}")
        return "\n".join(lines)

    for key in ('database_path', 'archive_root', 'mode'):
        if key not in config:
            continue
        value = config[key]
        line = f"  {key}: {value!r}"
        if key in ('database_path', 'archive_root'):
            resolved = Path(value)
            if not resolved.is_absolute():
                resolved = PROJECT_ROOT / resolved
            line += f"  (resolved: {resolved}, exists: {resolved.exists()})"
        lines.append(line)

    return "\n".join(lines)


def _describe_database(db_path, label):
    """
    Table list and row counts by status, if the database exists.
    Read-only -- opens with sqlite3.connect() but only ever SELECTs,
    never writes. Catches sqlite3.OperationalError specifically (e.g.
    "database is locked"), since this report might reasonably be
    generated while another tool is mid-run.
    """
    path = Path(db_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path

    if not path.exists():
        return f"{label}: not found at {path}"

    lines = [f"{label}: {path}"]
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = sorted(row[0] for row in cursor.fetchall())
        lines.append(f"  tables: {tables}")

        if 'located_files' in tables:
            cursor.execute("SELECT status, COUNT(*) FROM located_files GROUP BY status")
            for status, count in cursor.fetchall():
                lines.append(f"    located_files.status='{status}': {count}")

        if 'located_archives' in tables:
            cursor.execute("SELECT COUNT(*) FROM located_archives")
            lines.append(f"    located_archives: {cursor.fetchone()[0]} row(s)")

        if 'archive_files' in tables:
            cursor.execute("SELECT COUNT(*) FROM archive_files")
            lines.append(f"    archive_files: {cursor.fetchone()[0]} row(s)")

        conn.close()
    except sqlite3.OperationalError as e:
        lines.append(f"  Could not read (possibly locked by a running tool): {e}")
    except sqlite3.Error as e:
        lines.append(f"  ERROR reading database: {e}")

    return "\n".join(lines)


def generate_diagnostic_report(source_field_value, archive_field_value, log_entries=None):
    """
    Builds a plain-text diagnostic report: environment info, the current
    Source/Archive field values, every configured tool's script/config
    status and key settings, database row counts, and (if provided) the
    recent event history from gui_settings.ini's rolling log -- exactly
    the sequence of button presses and outcomes that led up to whatever
    is being debugged, not just a snapshot of current state. Meant to be
    pasted directly when asking for help. Entirely read-only; never
    modifies anything.
    """
    lines = []
    lines.append("=" * 70)
    lines.append("ChronoVault GUI Diagnostic Report")
    lines.append(f"Generated: {datetime.now().isoformat()}")
    lines.append("=" * 70)
    lines.append("")

    lines.append("-- Environment --")
    lines.append(f"Python: {sys.version.split()[0]}")
    lines.append(f"Platform: {platform.platform()}")
    try:
        import PySide6
        lines.append(f"PySide6: {getattr(PySide6, '__version__', 'installed, version unknown')}")
    except ImportError:
        lines.append("PySide6: not installed (unexpected -- how is this report running?)")
    lines.append(f"Project root: {PROJECT_ROOT}")
    lines.append("")

    lines.append("-- Current GUI fields --")
    lines.append(f"Source folder: {source_field_value or '(empty)'}")
    if source_field_value:
        lines.append(f"  exists: {Path(source_field_value).exists()}")
    lines.append(f"Archive folder: {archive_field_value or '(empty)'}")
    if archive_field_value:
        lines.append(f"  exists: {Path(archive_field_value).exists()}")
    lines.append("")

    lines.append("-- Recent Activity (from gui_settings.ini's rolling log) --")
    if log_entries:
        for entry in log_entries:
            lines.append(f"  {entry}")
    else:
        lines.append("  (no recorded activity yet)")
    lines.append("")

    lines.append("-- Tool configuration status --")
    config = load_gui_config()
    if config is None:
        lines.append("COULD NOT LOAD gui_config.json -- see terminal output for why.")
    else:
        for tool_name, tool_entry in config.get('tools', {}).items():
            lines.append(_describe_tool_config(tool_name, tool_entry))
            lines.append("")

    lines.append("-- Databases --")
    located_db_path = "located_files.db"  # conventional default, overridden below if configured differently
    if config and 'indexer' in config.get('tools', {}):
        try:
            with open(PROJECT_ROOT / config['tools']['indexer']['config']) as f:
                located_db_path = json.load(f).get('database_path', located_db_path)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    lines.append(_describe_database(located_db_path, "located_files.db"))
    lines.append("")

    if archive_field_value:
        archive_db_path = str(Path(archive_field_value) / "archive_database.db")
        lines.append(_describe_database(archive_db_path, "archive_database.db"))
        lines.append("")

    lines.append("=" * 70)
    return "\n".join(lines)
