"""
test_ocr_date.py

A throwaway verification script -- not a permanent ChronoVault tool.
Runs find_date_in_corners() (now in analyze_date/image_tools/ocr_tools.py,
migrated from the old standalone ocr_date/ folder) against every image in
OCR_test_images/, so real-world date-stamp accuracy can be checked
against actual downloaded/scanned photos.

Usage (from the ChronoVault/ project root):
    python3 test_functions/test_ocr_date.py

Requires tesseract-ocr installed as a system package -- see
analyze_date/image_tools/ocr_tools.py's module docstring for setup.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyze_date.image_tools.ocr_tools import find_date_in_corners

IMAGE_FOLDER = "OCR_test_images"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
DEBUG_CROP_FOLDER = "OCR_test_images/_debug_crops"

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
              f"rotation={result['rotation']} degrees  variant={result['variant']}  "
              f"confidence={result['ocr_confidence']}")
        print(f"          matched from raw text: {result['raw_text']!r}")
    else:
        print(f"[NOTHING] {image_path.name}  -- no date pattern matched (or none met the confidence threshold)")

    for entry in result["checked"]:
        text_display = entry["raw_text"] if entry["raw_text"] else "(no text detected)"
        print(f"            {entry['corner']:14s} rot={entry['rotation']:>3}  {entry['variant']:>4}  "
              f"conf={entry['ocr_confidence']:>5}  raw OCR text: {text_display!r}")
    print()

print("-" * 60)
print(f"Summary: {found_count}/{len(images)} image(s) had a date successfully detected.")
