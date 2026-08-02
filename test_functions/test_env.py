"""
test_env.py

Verifies the ChronoVault environment -- checks that everything the
current tools actually depend on is installed and reachable, before
running any of them for real. Meant to be the first thing run on a new
machine, or whenever something mysteriously doesn't work (e.g. "OCR
doesn't work") -- run this first instead of chasing dependency issues by
hand for half an hour.

Usage (from the ChronoVault/ project root):
    python3 test_functions/test_env.py
"""

import os
import sys
import shutil
import sqlite3
import subprocess
from pathlib import Path

CHECK = "\u2713"  # checkmark
CROSS = "\u2717"  # cross

# Each entry: (passed: bool, label: str, detail: str, required: bool)
results = []


def check(label, passed, detail="", required=True):
    results.append((passed, label, detail, required))


def run_command(args, timeout=5):
    """Run a command, returning (success, stdout) -- never raises."""
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return True, result.stdout
    except Exception:
        return False, ""


PROJECT_ROOT = Path(__file__).resolve().parent.parent

# --- Python itself ---
v = sys.version_info
check("Python", v >= (3, 8), f"{v.major}.{v.minor}.{v.micro}", required=True)

# --- SQLite (part of the Python standard library, so this basically always passes --
# checked anyway since a broken system Python install is exactly the kind of thing
# worth catching on a new machine) ---
check("SQLite", True, sqlite3.sqlite_version, required=True)

# --- Pillow -- used by every tool that reads or writes image files ---
try:
    import PIL
    check("Pillow", True, PIL.__version__, required=True)
except ImportError:
    check("Pillow", False, "not installed -- pip install Pillow --break-system-packages", required=True)

# --- NumPy -- used by ocr_date's Otsu thresholding preprocessing ---
try:
    import numpy
    check("NumPy", True, numpy.__version__, required=True)
except ImportError:
    check("NumPy", False, "not installed -- needed by ocr_date's OpenCV preprocessing", required=True)

# --- OpenCV -- used by ocr_date for Otsu thresholding ---
try:
    import cv2
    check("OpenCV", True, cv2.__version__, required=True)
except ImportError:
    check("OpenCV", False,
          "not installed -- pip install opencv-python-headless --break-system-packages (required for ocr_date)",
          required=True)

# --- Tesseract OCR engine (system binary, separate from the Python bindings) ---
tesseract_path = shutil.which("tesseract")
if tesseract_path:
    ok, output = run_command(["tesseract", "--version"])
    version_line = output.splitlines()[0] if output else "version unknown"
    check("Tesseract executable", True, version_line, required=True)
else:
    check("Tesseract executable", False,
          "not found -- sudo apt install tesseract-ocr (required for ocr_date)", required=True)

# --- pytesseract -- Python bindings for Tesseract ---
try:
    import pytesseract
    version = getattr(pytesseract, "__version__", "installed")
    check("pytesseract", True, version, required=True)
except ImportError:
    check("pytesseract", False,
          "not installed -- apt install python3-pytesseract, or pip install pytesseract --break-system-packages",
          required=True)

# --- OCR language packs (only meaningful if Tesseract itself is present) ---
if tesseract_path:
    ok, output = run_command(["tesseract", "--list-langs"])
    langs = [line.strip() for line in output.splitlines()[1:] if line.strip()]
    check("Tesseract language: eng", "eng" in langs,
          "" if "eng" in langs else "missing -- needed for all current OCR", required=True)
    check("Tesseract language: jpn", "jpn" in langs,
          "" if "jpn" in langs else "not installed -- only needed for future Japanese date-stamp support",
          required=False)

# --- ffmpeg -- NOT used by any current ChronoVault tool. Checked here purely as a
# forward-looking placeholder for future video-processing features. ---
ffmpeg_path = shutil.which("ffmpeg")
check("ffmpeg", ffmpeg_path is not None,
      "not currently used by any ChronoVault tool -- checked for future video features"
      if not ffmpeg_path else "", required=False)

# --- exiftool -- NOT used today; Pillow handles all current EXIF reading/writing.
# Checked as a placeholder in case a future tool needs deeper metadata support
# than Pillow provides. ---
exiftool_path = shutil.which("exiftool")
check("exiftool", exiftool_path is not None,
      "not currently used -- Pillow handles all EXIF reading today" if not exiftool_path else "",
      required=False)

# --- Write permission on the project root ---
check(f"Write permission ({PROJECT_ROOT})", os.access(PROJECT_ROOT, os.W_OK), required=True)

# --- Archive folder / database integrity (informational on a fresh setup --
# nothing to check yet if Importer has never been run) ---
archive_dir = PROJECT_ROOT / "archive"
if archive_dir.exists():
    check("Archive folder", True, str(archive_dir), required=False)
    archive_db_path = archive_dir / "archive_database.db"
    if archive_db_path.exists():
        try:
            conn = sqlite3.connect(archive_db_path)
            result = conn.execute("PRAGMA integrity_check").fetchone()
            conn.close()
            check("archive_database.db integrity", result[0] == "ok", result[0], required=True)
        except Exception as e:
            check("archive_database.db integrity", False, str(e), required=True)

located_db_path = PROJECT_ROOT / "located_files.db"
if located_db_path.exists():
    try:
        conn = sqlite3.connect(located_db_path)
        result = conn.execute("PRAGMA integrity_check").fetchone()
        conn.close()
        check("located_files.db integrity", result[0] == "ok", result[0], required=True)
    except Exception as e:
        check("located_files.db integrity", False, str(e), required=True)


# --- Print results ---
print("ChronoVault Environment Check")
print("-" * 30)
print()

for passed, label, detail, required in results:
    mark = CHECK if passed else CROSS
    tag = "" if required else "  (optional)"
    line = f"{mark} {label}"
    if detail:
        line += f"  {detail}"
    line += tag
    print(line)

print()
required_failures = [r for r in results if not r[0] and r[3]]
optional_gaps = [r for r in results if not r[0] and not r[3]]

if required_failures:
    print(f"{len(required_failures)} REQUIRED check(s) failed -- fix these before relying on ChronoVault:")
    for passed, label, detail, required in required_failures:
        print(f"  - {label}: {detail}")
    sys.exit(1)
else:
    print("All required checks passed.")

if optional_gaps:
    print()
    print(f"{len(optional_gaps)} optional feature(s) unavailable (not blocking anything today):")
    for passed, label, detail, required in optional_gaps:
        print(f"  - {label}")
        