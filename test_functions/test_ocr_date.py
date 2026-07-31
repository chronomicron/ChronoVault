"""
test_ocr_date.py

A throwaway verification script -- not a permanent ChronoVault tool.
Runs ocr_date.find_date_in_corners() against every image in
OCR_test_images/, so real-world date-stamp accuracy can be checked
against actual downloaded/scanned photos, not just synthetic test
images generated in code.

Usage (from the ChronoVault/ project root):
    python3 test_functions/test_ocr_date.py

Requires tesseract-ocr installed as a system package (not just the
pytesseract Python bindings) -- see ocr_date/README.md.
"""

import sys
from pathlib import Path

# This script lives one folder down (test_functions/), so make the
# project root importable regardless of where it's actually run from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ocr_date.ocr_date import find_date_in_corners

IMAGE_FOLDER = "OCR_test_images"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
DEBUG_CROP_FOLDER = "OCR_test_images/_debug_crops"  # what OCR actually saw, for every corner checked

folder = Path(IMAGE_FOLDER)
if not folder.exists():
    print(f"No '{IMAGE_FOLDER}' folder found at the project root.")
    print(f"Put some real-world test images there and re-run this script.")
    sys.exit(1)

images = sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS)
if not images:
    print(f"'{IMAGE_FOLDER}' exists but has no image files in it.")
    sys.exit(0)

print(f"Found {len(images)} image(s) in '{IMAGE_FOLDER}'. Running OCR corner detection...")
print(f"(Saving what OCR actually sees for each corner to '{DEBUG_CROP_FOLDER}/' -- worth a look")
print(f" for anything marked [NOTHING], to check whether the crop is even landing on the stamp.)")
print("-" * 60)

found_count = 0
for image_path in images:
    result = find_date_in_corners(str(image_path), debug_dir=DEBUG_CROP_FOLDER)

    if result["date"]:
        found_count += 1
        print(f"[FOUND]   {image_path.name}")
        print(f"          date={result['date'].strftime('%Y-%m-%d')}  corner={result['corner']}  "
              f"rotation={result['rotation']} degrees  confidence={result['ocr_confidence']}")
        print(f"          matched from raw text: {result['raw_text']!r}")
    else:
        print(f"[NOTHING] {image_path.name}  -- no date pattern matched (or none met the confidence threshold)")

    # Always show what OCR actually read -- and how confident it was -- for
    # every corner/rotation combo checked, whether or not a date was found.
    # If any of it visibly looks like a date to a human but isn't listed
    # above as [FOUND], check its confidence: a low number means it was
    # deliberately rejected as too uncertain to trust, which is a MIN_OCR_
    # CONFIDENCE tuning question, not a pattern bug.
    for entry in result["checked"]:
        text_display = entry["raw_text"] if entry["raw_text"] else "(no text detected)"
        print(f"            {entry['corner']:14s} rot={entry['rotation']:>3}  "
              f"conf={entry['ocr_confidence']:>5}  raw OCR text: {text_display!r}")
    print()

print("-" * 60)
print(f"Summary: {found_count}/{len(images)} image(s) had a date successfully detected.")
if found_count < len(images):
    print("For any marked [NOTHING] above, check the per-corner raw OCR text -- if any of it")
    print("looks like a real date to you, that's a date_patterns gap in ocr_date.py to fix,")
    print("not just an OCR misread.")
    