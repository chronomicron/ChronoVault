"""
test_write_data.py

A throwaway verification script -- not a permanent ChronoVault tool.
Confirms apply_date_correction() works end to end by comparing a fresh
Audit Archive report taken immediately before applying corrections
against one taken immediately after.

Usage (from the ChronoVault/ project root):
    python3 test_functions/test_write_data.py
"""

import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

# This script lives one folder down (test_functions/), so make the
# project root importable regardless of where it's actually run from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from retrieve_data.retrieve_data import list_review_items
from write_data.write_data import apply_date_correction

ARCHIVE_ROOT = "archive"
AUDIT_SCRIPT = "audit_archive/audit_archive.py"
AUDIT_CONFIG = "audit_archive/config.json"
AUDIT_RESULT_PATH = Path("audit_result.json")
MAX_CORRECTIONS = 3  # keep the test run quick, and leave some review items behind for further manual testing


def run_audit():
    """Run Audit Archive fresh and return its parsed summary dict."""
    subprocess.run(
        [sys.executable, AUDIT_SCRIPT, AUDIT_CONFIG],
        check=True, capture_output=True, text=True
    )
    with open(AUDIT_RESULT_PATH) as f:
        return json.load(f)


def print_summary(label, report):
    print(f"--- {label} ---")
    for key, value in report['summary'].items():
        print(f"  {key}: {value}")
    print()


# Verify a prior Audit report exists before doing anything -- if Audit
# Archive has never been run, there's nothing meaningful to compare.
print(f"Checking for an existing Audit report at '{AUDIT_RESULT_PATH}'...")
if not AUDIT_RESULT_PATH.exists():
    print(f"No '{AUDIT_RESULT_PATH}' found. Run Audit Archive first "
          f"(./chronovault.sh option [3], or `python3 {AUDIT_SCRIPT} {AUDIT_CONFIG}`), "
          f"then re-run this script.")
    sys.exit(1)
print("Found it. Running Audit Archive fresh now to capture an accurate 'before' snapshot...")
print("-" * 60)

before = run_audit()
print_summary("BEFORE corrections", before)

items = list_review_items(ARCHIVE_ROOT)
if not items:
    print("Nothing in the review bucket to correct -- nothing to test here. "
          "Run Importer against some low-confidence files first.")
    sys.exit(0)

to_correct = items[:MAX_CORRECTIONS]
print(f"Found {len(items)} review item(s); correcting {len(to_correct)} of them.")
print("(Using a deliberately different date than each file's original algorithmic guess --")
print(" not the same date it already had -- since that's the realistic case: a real person")
print(" correcting a date the algorithm got wrong, not confirming one it already had right.)")
print("-" * 60)

for i, item in enumerate(to_correct):
    # A fixed, deliberately different test date per item, so this is
    # reproducible and clearly not just echoing back date_taken.
    corrected_date = datetime(2019, 6, 15) + timedelta(days=i * 40)
    result = apply_date_correction(ARCHIVE_ROOT, item['id'], corrected_date)
    status = "OK" if result['success'] else "FAILED"
    print(f"[{item['id']}] {status} -> {result['new_archive_path'] or result['error']}")

print("-" * 60)
print("Running Audit Archive again to capture the 'after' snapshot...")
after = run_audit()
print_summary("AFTER corrections", after)

print("--- Differences ---")
any_diff = False
for key in before['summary']:
    b, a = before['summary'][key], after['summary'][key]
    if b != a:
        any_diff = True
        print(f"  {key}: {b} -> {a}")
if not any_diff:
    print("  No differences in the summary counts.")

if after['summary']['misplaced_count'] > before['summary']['misplaced_count']:
    print()
    print("Note: 'misplaced_count' going up here is expected with the current design, not a")
    print("bug in this test. apply_date_correction() deliberately leaves 'date_taken' untouched")
    print("to preserve the original algorithmic evidence, but Audit Archive's placement check")
    print("only ever compares a file's location against 'date_taken' -- it doesn't know")
    print("'user_corrected_date' exists yet. So a real correction (one that actually differs")
    print("from the original guess) will currently get flagged as misplaced, even though a")
    print("person deliberately put it there. Worth deciding whether Audit Archive should be")
    print("updated to prefer 'user_corrected_date' over 'date_taken' when present.")
    