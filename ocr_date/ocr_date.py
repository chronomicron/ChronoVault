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

import cv2
import numpy as np
from PIL import Image
import pytesseract
from pytesseract import Output

# Date stamps sit in a thin band along an edge, not a deep square region --
# real-world testing showed a wide-but-short crop finds them far more
# reliably than a square one, which dilutes the tiny text with too much
# unrelated photo content. Width is deliberately close to full-width: a
# combined date+time stamp can span nearly the entire photo width, and
# since height is already tightly constrained, a wide crop doesn't risk
# pulling in much unrelated content the way a wide-AND-tall one would.
CORNER_WIDTH_FRACTION = 0.95
CORNER_HEIGHT_FRACTION = 0.25

# Corners are upscaled before OCR -- tesseract is generally much more
# reliable on larger text than on the small, low-contrast stamps typical
# of date-stamp cameras.
UPSCALE_FACTOR = 3

# Rotations tried per corner, in order. 0 first, since most date stamps
# are printed right-side-up and most photos are landscape -- checking the
# native orientation first keeps the common case fast (an early match
# skips the rest entirely). The other three only get tried if 0 degrees
# doesn't produce a valid date -- this is what catches a stamp printed
# sideways along a photo's edge.
ROTATIONS_TO_TRY = [0, 90, 180, 270]

# Minimum average per-word OCR confidence (0-100) required before a
# regex-matched date is actually trusted, rather than discarded as noise.
# Found necessary after real-world testing: restricting Tesseract to a
# narrow character whitelist can make it guess a plausible-looking but
# WRONG digit sequence out of noise, rather than honestly outputting
# something that clearly fails to parse. A confident, correct read on a
# clean test image scored 90+ per digit; this threshold is deliberately
# well below that, to reject only genuinely low-confidence noise.
MIN_OCR_CONFIDENCE = 40

# Date patterns commonly burned in by consumer date-stamp cameras from
# the film and early-digital era, roughly in order of how common they are.
# All patterns are matched against the raw OCR text for each corner.
DATE_PATTERNS = [
    # '99 07 15  or  1999-07-15                 (year month day -- least ambiguous, checked first)
    (r"'?(\d{4}|\d{2})[\s\-\./](\d{1,2})[\s\-\./](\d{1,2})\b", "ymd"),
    # 07/15/1999  or  07-15-99                  (month day year -- common US date-stamp format)
    (r"\b(\d{1,2})[\s\-\./](\d{1,2})[\s\-\./]'?(\d{4}|\d{2})\b", "mdy"),
    # 15 07 '99  or  15.07.1999                 (day month year -- common international format)
    (r"\b(\d{1,2})[\s\-\./](\d{1,2})[\s\-\./]'?(\d{4}|\d{2})\b", "dmy"),
]
# Deliberately NOT including ':' as a separator -- real-world testing showed
# a colon in a date stamp means it's actually the clock time, not the date
# (e.g. "10:02"). Parsing a time as if it were a date risks a confident
# false match, which is worse than finding nothing.

# Constrains Tesseract's output to just digits, the punctuation a date
# stamp could plausibly contain, and spaces -- cuts down on garbage/noise
# characters (stray letters, symbols) getting mixed in with real digits,
# which was a common failure pattern in real-world testing.
TESSERACT_CONFIG = '--psm 7 -c tessedit_char_whitelist="0123456789/:.-\' "'


# A digit stamp is never going to predate consumer photography, or be in
# the future. This catches a specific real failure mode: a single-digit
# OCR misread (e.g. '2024' read as '1024') otherwise parses as a
# perfectly valid Python date with nothing to flag it as wrong -- silently
# confident and silently incorrect. Kept deliberately generous (not tied
# to analyze_date's stricter 1972 cutoff) since this module only cares
# about catching obviously-broken OCR reads, not judging plausibility the
# way analyze_date does once a date reaches Importer.
EARLIEST_PLAUSIBLE_YEAR = 1900


# A punctuation-free match (just digits and spaces, e.g. "24 11 26") has
# no structural evidence it's actually a date rather than three
# coincidentally date-shaped numbers OCR produced from noise -- unlike a
# match with real separators (., /, -, ') like "07.20.2010", which is a
# much stronger claim. Found necessary live: a bare-digit misread and a
# genuinely correct punctuated match had confidence scores only ~4 points
# apart (51.3 vs 55.0) -- too close to separate with one threshold, so
# bare-digit matches get held to a stricter one instead.
MIN_OCR_CONFIDENCE_NO_PUNCTUATION = 65


def _parse_date_candidate(text):
    """
    Try every known date pattern against a block of OCR text.
    Returns (datetime or None, has_punctuation: bool) -- has_punctuation
    reflects whether the actual matched text included a real separator
    character, not just whitespace, and is meaningless when the date is
    None.
    """
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
            candidate = datetime(year, month, day)
            if candidate.year < EARLIEST_PLAUSIBLE_YEAR or candidate > datetime.now():
                # This is a STRUCTURALLY valid date (real month, real day)
                # with an implausible year -- almost certainly a single
                # OCR digit misread (2024 -> 1024), not evidence the text
                # should be reinterpreted a different way. Stop here rather
                # than falling through to a weaker pattern, which risks
                # matching unrelated leftover digits (e.g. from a time
                # stamp) into a second, different, also-wrong date.
                return None, False
            has_punctuation = any(ch in match.group(0) for ch in "-./'")
            return candidate, has_punctuation
        except ValueError:
            continue  # not a real date at all (e.g. month 34) -- worth trying a different pattern
    return None, False


def _ocr_with_confidence(image):
    """
    Run OCR on an image and return (text, average_confidence).

    Uses image_to_data() rather than image_to_string() specifically to
    get per-word confidence scores back -- image_to_string() only ever
    returns text, with no way to tell a confident read from a desperate
    guess. Words Tesseract didn't attach a real confidence to (conf == -1,
    its convention for "not applicable") are excluded from the average
    rather than counted as zero.
    """
    data = pytesseract.image_to_data(image, config=TESSERACT_CONFIG, output_type=Output.DICT)
    words = []
    confidences = []
    for text, conf in zip(data["text"], data["conf"]):
        if text.strip():
            words.append(text)
            conf = float(conf)
            if conf >= 0:
                confidences.append(conf)

    combined_text = " ".join(words)
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    return combined_text, avg_confidence


def _otsu_threshold(pil_image):
    """
    Apply Otsu's automatic thresholding -- picks its own black/white cutoff
    based on the image's own brightness histogram, rather than a fixed
    guessed number. Dramatically improved real-world recognition of small,
    low-contrast dot-matrix stamps (the kind security cameras and baby
    monitors burn in) in testing -- these produced no readable text at all
    without it. Only actually helps once the crop is already tight around
    just the text (see CORNER_HEIGHT_FRACTION) -- Otsu on a crop with a lot
    of unrelated content picks a threshold dominated by that content
    instead of the tiny text.
    """
    arr = np.array(pil_image)
    _, binarized = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return Image.fromarray(binarized)


def _get_corner_crops(image):
    """Return {corner_name: cropped_image} for all four corners -- wide, short strips."""
    width, height = image.size
    cw = int(width * CORNER_WIDTH_FRACTION)
    ch = int(height * CORNER_HEIGHT_FRACTION)
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
    location), then the others. Within each corner, tries every rotation
    in ROTATIONS_TO_TRY (0 degrees first) -- this is what catches a stamp
    printed sideways along a photo's edge, without needing to know in
    advance which way it's rotated.

    If debug_dir is given, saves the actual (upscaled, rotated) crop fed
    to OCR for every corner/rotation combination actually tried, as PNG
    files named '<original filename>_<corner>_rot<degrees>.png' -- the
    single most useful thing to look at when OCR is reading pure garbage:
    is the crop region even landing on the stamp at all, or is
    CORNER_FRACTION cropping the wrong area entirely?

    Returns a dict:
        {'date': datetime or None, 'corner': str or None, 'rotation': int or None,
         'raw_text': str or None, 'checked': [{'corner': str, 'rotation': int, 'raw_text': str}, ...]}
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

        for rotation in ROTATIONS_TO_TRY:
            rotated = upscaled.rotate(rotation, expand=True) if rotation else upscaled

            # Try the plain grayscale crop first, then an Otsu-thresholded
            # (black/white) version of the same crop -- thresholding helps
            # a lot on small, low-contrast dot-matrix text, but isn't
            # always better (it can occasionally hurt a clean, high-
            # contrast stamp), so both get a chance rather than committing
            # to one.
            variants = [("raw", rotated), ("otsu", _otsu_threshold(rotated))]

            for variant_name, variant_image in variants:
                if debug_dir:
                    stem = Path(file_path).stem
                    variant_image.save(Path(debug_dir) / f"{stem}_{corner_name}_rot{rotation}_{variant_name}.png")

                raw_text, confidence = _ocr_with_confidence(variant_image)
                checked.append({"corner": corner_name, "rotation": rotation, "variant": variant_name,
                                 "raw_text": raw_text, "ocr_confidence": round(confidence, 1)})

                date, has_punctuation = _parse_date_candidate(raw_text)
                required_confidence = MIN_OCR_CONFIDENCE if has_punctuation else MIN_OCR_CONFIDENCE_NO_PUNCTUATION
                if date and confidence >= required_confidence:
                    return {"date": date, "corner": corner_name, "rotation": rotation, "variant": variant_name,
                             "raw_text": raw_text, "ocr_confidence": round(confidence, 1), "checked": checked}
                # A date-shaped match on low-confidence OCR is exactly the
                # dangerous case (a plausible-looking wrong guess) --
                # deliberately NOT returned here, so the search keeps
                # going instead of accepting it.

    return {"date": None, "corner": None, "rotation": None, "variant": None,
            "raw_text": None, "ocr_confidence": None, "checked": checked}
