"""
ocr_date.py

PROOF OF CONCEPT -- not yet wired into analyze_date or Importer.

Scans the four corners of an image for a printed/imprinted date -- the
kind of thing old date-stamp cameras burn directly into the photo
(commonly orange or red digits, bottom-right corner) or that shows up on
a scanned print. This is a real, useful signal for exactly the files
that need it most: old photos with no EXIF at all, where the file's
own printed date may be the *only* evidence of when it was actually
taken.

This module only extracts a candidate date from image pixels -- it does
not decide how much to trust that date relative to other evidence. That
combination logic belongs in analyze_date, once this is wired in as a
new signal source (see analyze_date's README for exactly how a new
source is meant to slot in).

Requires:
    - pytesseract (Python package)
    - tesseract-ocr (system binary -- `apt install tesseract-ocr` on
      Debian/Ubuntu/Mint)

Usage:
    from ocr_date.ocr_date import find_date_in_corners

    result = find_date_in_corners("old_photo.jpg")
    # {'date': datetime(1999, 7, 15) or None, 'corner': 'bottom_right' or None,
    #  'raw_text': '...' or None}
"""

import re
from datetime import datetime
from pathlib import Path

from PIL import Image
import pytesseract

# How much of the image's width/height each corner crop covers. Date
# stamps are almost always small and close to an edge -- cropping tight
# both speeds up OCR and avoids picking up unrelated text/noise from the
# rest of the photo.
CORNER_FRACTION = 0.25

# Corners are upscaled before OCR -- tesseract is generally much more
# reliable on larger text than on the small, low-contrast stamps typical
# of date-stamp cameras.
UPSCALE_FACTOR = 3

# Date patterns commonly burned in by consumer date-stamp cameras from
# the film and early-digital era, roughly in order of how common they are.
# All patterns are matched against the raw OCR text for each corner.
DATE_PATTERNS = [
    # '99 07 15  or  1999-07-15  or  1999:07:15  (year month day -- least ambiguous, checked first)
    (r"'?(\d{4}|\d{2})[\s\-\./:](\d{1,2})[\s\-\./:](\d{1,2})\b", "ymd"),
    # 07/15/1999  or  07-15-99                   (month day year -- common US date-stamp format)
    (r"\b(\d{1,2})[\s\-\./:](\d{1,2})[\s\-\./:]'?(\d{4}|\d{2})\b", "mdy"),
    # 15 07 '99  or  15.07.1999                  (day month year -- common international format)
    (r"\b(\d{1,2})[\s\-\./:](\d{1,2})[\s\-\./:]'?(\d{4}|\d{2})\b", "dmy"),
]

# Constrains Tesseract's output to just digits, the punctuation a date
# stamp could plausibly contain, and spaces -- cuts down on garbage/noise
# characters (stray letters, symbols) getting mixed in with real digits,
# which was a common failure pattern in real-world testing.
TESSERACT_CONFIG = '--psm 7 -c tessedit_char_whitelist="0123456789/:.-\' "'


def _parse_date_candidate(text):
    """Try every known date pattern against a block of OCR text; return the first match as a datetime, or None."""
    for pattern, order in DATE_PATTERNS:
        match = re.search(pattern, text)
        if not match:
            continue
        a, b, c = match.groups()
        try:
            if order == "dmy":
                day, month, year = int(a), int(b), int(c)
            elif order == "mdy":
                month, day, year = int(a), int(b), int(c)
            else:  # ymd
                year, month, day = int(a), int(b), int(c)
            if year < 100:
                # Two-digit year -- assume 1900s for anything that looks
                # like a plausible film-camera year, 2000s otherwise.
                year += 1900 if year > 30 else 2000
            return datetime(year, month, day)
        except ValueError:
            continue  # not a real date (e.g. month 34) -- keep looking
    return None


def _get_corner_crops(image):
    """Return {corner_name: cropped_image} for all four corners."""
    width, height = image.size
    cw, ch = int(width * CORNER_FRACTION), int(height * CORNER_FRACTION)
    return {
        "top_left": image.crop((0, 0, cw, ch)),
        "top_right": image.crop((width - cw, 0, width, ch)),
        "bottom_left": image.crop((0, height - ch, cw, height)),
        "bottom_right": image.crop((width - cw, height - ch, width, height)),
    }


def find_date_in_corners(file_path, debug_dir=None):
    """
    Look for an OCR-readable date stamp in each of the four corners of an
    image. Checks bottom_right first (the most common date-stamp
    location), then the others.

    If debug_dir is given, saves the actual (upscaled) crop fed to OCR
    for every corner checked, as PNG files named
    '<original filename>_<corner>.png' -- the single most useful thing
    to look at when OCR is reading pure garbage: is the crop region even
    landing on the stamp at all, or is CORNER_FRACTION cropping the
    wrong area entirely?

    Returns a dict:
        {'date': datetime or None, 'corner': str or None, 'raw_text': str or None,
         'checked': [{'corner': str, 'raw_text': str}, ...]}
    """
    image = Image.open(file_path).convert("L")  # grayscale -- helps OCR on colored stamp digits
    corners = _get_corner_crops(image)

    if debug_dir:
        Path(debug_dir).mkdir(parents=True, exist_ok=True)

    # Check the most likely corner first, then the rest.
    check_order = ["bottom_right", "bottom_left", "top_right", "top_left"]
    checked = []

    for corner_name in check_order:
        crop = corners[corner_name]
        upscaled = crop.resize(
            (crop.width * UPSCALE_FACTOR, crop.height * UPSCALE_FACTOR),
            Image.LANCZOS
        )

        if debug_dir:
            stem = Path(file_path).stem
            upscaled.save(Path(debug_dir) / f"{stem}_{corner_name}.png")

        raw_text = pytesseract.image_to_string(upscaled, config=TESSERACT_CONFIG).strip()
        checked.append({"corner": corner_name, "raw_text": raw_text})

        date = _parse_date_candidate(raw_text)
        if date:
            return {"date": date, "corner": corner_name, "raw_text": raw_text, "checked": checked}

    return {"date": None, "corner": None, "raw_text": None, "checked": checked}
