"""
test_analyze_date.py

A throwaway debugging script -- not a permanent ChronoVault tool, and NOT
a sign that analyze_date itself is becoming a terminal app. analyze_date
stays a library, called by Importer exactly as before; this is just a
convenient way to ask it "what would you decide for this one file?"

Usage (from the ChronoVault/ project root):
    python3 test_functions/test_analyze_date.py path/to/file.jpg
    python3 test_functions/test_analyze_date.py path/to/file.tiff --type .tiff
    python3 test_functions/test_analyze_date.py path/to/file.jpg --try-ocr
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyze_date.analyze_date import analyze_date

parser = argparse.ArgumentParser(description="Show what analyze_date resolves for one file.")
parser.add_argument("file_path", help="Path to the file to analyze")
parser.add_argument("--type", default=None,
                     help="Override the file type (e.g. .tiff) instead of inferring from the extension")
parser.add_argument("--try-ocr", action="store_true",
                     help="Also scan the image corners for a printed date stamp (slow, opt-in)")
args = parser.parse_args()

path = Path(args.file_path)
if not path.exists():
    print(f"No such file: {path}")
    sys.exit(1)

file_type = args.type or path.suffix.lower()

readable_exif = {}
if file_type in (".jpg", ".jpeg", ".thm"):
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS
        image = Image.open(path)
        raw = image._getexif()
        readable_exif = {TAGS.get(k, k): v for k, v in raw.items()} if raw else {}
    except Exception as e:
        print(f"(Could not read EXIF: {e})")

evidence = {
    "file_path": str(path),
    "readable_exif": readable_exif,
    "mismatch_threshold_days": 1,
    "try_ocr": args.try_ocr,
}
if args.type:
    evidence["file_type"] = args.type

result = analyze_date(evidence)

print(f"File: {path}")
print(f"Type used: {file_type}{'  (overridden)' if args.type else '  (from extension)'}")
print(f"OCR: {'attempted' if args.try_ocr else 'skipped (pass --try-ocr to enable)'}")
print("-" * 60)
print(f"date_taken:     {result['date_taken']}")
print(f"date_source:    {result['date_source']}")
print(f"confidence:     {result['confidence']}")
print(f"date_uncertain: {result['date_uncertain']}")
print(f"reason:         {result['reason']}")
print()
print("Full result:")
print(json.dumps({k: str(v) for k, v in result.items()}, indent=2))
