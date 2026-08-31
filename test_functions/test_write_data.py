"""
test_write_data.py

A throwaway verification script -- not a permanent ChronoVault tool.
Confirms apply_date_correction() works end to end by comparing a fresh
Audit Archive report taken immediately before applying corrections
against one taken immediately after.

Usage (from the ChronoVault/ project root, or from anywhere via
chronovault.sh's containment cd trick -- see below):
    python3 test_functions/test_write_data.py
"""

import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

# This script lives one folder down (test_functions/), so make the
# project root importable regardless of where it's actually run from.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from retrieve_data.retrieve_data import list_review_items
from write_data.write_data import apply_date_correction

# ARCHIVE_ROOT and AUDIT_RESULT_PATH are deliberately relative to the
# CURRENT WORKING DIRECTORY -- they describe wherever the archive/report
# being tested actually lives (the project root for a real archive, or
# chronovault_test/ when run via chronovault.sh), matching the same
# CWD-relative convention every other ChronoVault tool already follows.
ARCHIVE_ROOT = "archive"
AUDIT_RESULT_PATH = Path("audit_result.json")

# AUDIT_SCRIPT and AUDIT_CONFIG are different: they point at the Audit
# Archive TOOL ITSELF, which always lives in the same place relative to
# this script (audit_archive/, next to test_functions/) regardless of
# what directory this script happens to be run from. Resolving these
# against PROJECT_ROOT rather than a bare relative string is what lets
# this script work correctly when invoked with a different working
# directory -- e.g. chronovault.sh cd-ing into chronovault_test/ before
# calling it, so all the ARCHIVE_ROOT/AUDIT_RESULT_PATH outputs above
# land in the contained test folder instead of the project root.
AUDIT_SCRIPT = str(PROJECT_ROOT / "audit_archive" / "audit_archive.py")
AUDIT_CONFIG = str(PROJECT_ROOT / "audit_archive" / "config.json")

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
          f"(chronovault.sh option [6], or `python3 {AUDIT_SCRIPT} {AUDIT_CONFIG}`), "
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
    print("Note: 'misplaced_count' went up. Audit Archive's placement check already prefers")
    print("'user_corrected_date' over 'date_taken' when present (see audit_archive.py), so this")
    print("would now genuinely indicate a real problem -- worth investigating rather than")
    print("assuming it's expected, unlike in an earlier version of this project.")
    