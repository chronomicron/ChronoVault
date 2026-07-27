"""
test_retrieve_data.py

A throwaway verification script -- not a permanent ChronoVault tool.
Run once to confirm retrieve_data.py works against your real archive.

Usage (from the ChronoVault/ project root):
    python3 test_functions/test_retrieve_data.py
"""

import sys
import json
from pathlib import Path

# This script lives one folder down (test_functions/), so make the
# project root importable regardless of where it's actually run from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from retrieve_data.retrieve_data import list_review_items, get_file_details

ARCHIVE_ROOT = "archive"

print(f"Querying '{ARCHIVE_ROOT}' for review items...")
items = list_review_items(ARCHIVE_ROOT)
print(f"Found {len(items)} file(s) in the review bucket.")
print("-" * 60)

if not items:
    print("Nothing in the review bucket right now -- run Importer against "
          "some no-EXIF or low-confidence files first, then re-run this script.")
else:
    for item in items:
        exists_tag = "" if item["file_exists"] else "  [FILE MISSING ON DISK]"
        print(f"[{item['id']}] {item['archive_path']}{exists_tag}")
        print(f"    confidence={item['confidence']}  reason={item['date_reason']}")

    print("-" * 60)
    print("Full record for the first item, as a dict:")
    print(json.dumps(items[0], indent=2))

    print("-" * 60)
    first_id = items[0]["id"]
    details = get_file_details(ARCHIVE_ROOT, first_id)
    match_ok = details == items[0]
    print(f"get_file_details({first_id}) matches the list entry: {match_ok}")

    missing = get_file_details(ARCHIVE_ROOT, 999999)
    print(f"get_file_details(999999) for a nonexistent id returns: {missing}")

    # Confirm the whole list is genuinely JSON-serializable end to end --
    # this is the actual point of the design, not just a nice-to-have.
    as_json = json.dumps(items)
    print(f"Full list serializes to JSON cleanly: {len(as_json)} characters, no errors.")
    