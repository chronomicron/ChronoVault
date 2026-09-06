"""
test_retrieve_data.py

A throwaway verification script -- not a permanent ChronoVault tool.
Confirms retrieve_data.py's two read-only functions (list_review_items,
get_file_details) work against a real archive, and that the results
genuinely serialize to JSON with no errors.

ARCHIVE LOCATION: read from a config.json, not hardcoded. A real archive
is at least as likely to live on a NAS, a network share, or a removable
drive that gets a different mount path every time it's unplugged and
replugged back in, as it is to sit at a fixed local folder -- so this
follows the same config.json + archive_root pattern already used by
every other archive-aware tool in this project (Importer, Audit Archive,
Duplicate Finder). That consistency is the actual point: the GUI's
existing archive-path syncing (update_archive_root_in_config) works here
completely unchanged, with zero special-casing for this tool.

Usage (from the ChronoVault/ project root):
    python3 test_functions/test_retrieve_data.py test_functions/test_retrieve_data_config.json
"""

import sys
import json
from pathlib import Path

# This script lives one folder down (test_functions/), so make the
# project root importable regardless of where it's actually run from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from retrieve_data.retrieve_data import list_review_items, get_file_details


def load_config(config_file):
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"Error: Configuration file '{config_file}' not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Configuration file '{config_file}' is not valid JSON.")
        sys.exit(1)

    archive_root = config.get('archive_root')
    if not archive_root:
        print("Error: 'archive_root' must be specified in config.")
        sys.exit(1)
    return archive_root


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 test_retrieve_data.py <config.json>")
        print("Example: python3 test_functions/test_retrieve_data.py test_functions/test_retrieve_data_config.json")
        sys.exit(1)

    archive_root = load_config(sys.argv[1])

    print(f"Querying '{archive_root}' for review items...")
    items = list_review_items(archive_root)
    print(f"Found {len(items)} file(s) in the review bucket.")
    print("-" * 60)

    if not items:
        print("Nothing in the review bucket right now -- run Importer against "
              "some no-EXIF or low-confidence files first, then re-run this script.")
        return

    for item in items:
        exists_tag = "" if item["file_exists"] else "  [FILE MISSING ON DISK]"
        print(f"[{item['id']}] {item['archive_path']}{exists_tag}")
        print(f"    confidence={item['confidence']}  reason={item['date_reason']}")

    print("-" * 60)
    print("Full record for the first item, as a dict:")
    print(json.dumps(items[0], indent=2))

    print("-" * 60)
    first_id = items[0]["id"]
    details = get_file_details(archive_root, first_id)
    match_ok = details == items[0]
    print(f"get_file_details({first_id}) matches the list entry: {match_ok}")

    missing = get_file_details(archive_root, 999999)
    print(f"get_file_details(999999) for a nonexistent id returns: {missing}")

    # Confirm the whole list is genuinely JSON-serializable end to end --
    # this is the actual point of the design, not just a nice-to-have.
    as_json = json.dumps(items)
    print(f"Full list serializes to JSON cleanly: {len(as_json)} characters, no errors.")


if __name__ == "__main__":
    main()
    