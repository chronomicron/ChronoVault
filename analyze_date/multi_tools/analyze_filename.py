"""
multi_tools/analyze_filename.py

Extracts a date from a file's own filename. Lives in multi_tools/, not
any type-specific *_tools folder (image_tools, audio_tools, video_tools),
because a filename pattern means the same thing regardless of whether
the file is a photo, an MP3, or a PDF.

Cameras and phones consistently embed the capture date directly in the
filenames they generate (IMG_20240315_143022.jpg). Base confidence 70 in
analyze_date -- see analyze_date/README.md's confidence table.

Handles both US-style (month-day-year) and European-style (day-month-
year) orderings for bare numeric dates with the year last -- these are
genuinely ambiguous when both readings would be valid (e.g. 03-04-2024
could be March 4th or April 3rd), in which case the month-first (US)
reading is used as the default. When only one ordering actually produces
a valid date (e.g. the first number is 15, which can't be a month), that
one is used regardless of the default -- the same disambiguation-by-
plausibility approach already proven in ocr_tools.py's date parsing.

Known tradeoff, honestly noted rather than hidden: a filename like
"chapter-1-2-2020.docx" is structurally identical to a real date pattern
and would be read as one (Jan 2, 2020) even though it might just be
sequential numbering. This is why filename_pattern's base confidence
(70) is moderate, not high -- a single ambiguous filename match isn't
meant to dominate on its own; agreement or disagreement with other
signals is what actually settles it.
"""

import re
from pathlib import Path
from datetime import datetime

EARLIEST_PLAUSIBLE_YEAR = 1990

# Fixed-convention camera/phone filenames -- these specific conventions
# (IMG_/VID_/PXL_/Screenshot_ prefixes, no separator inside the date
# itself) are well-documented, fixed Android/iOS/camera software
# conventions that are ALWAYS year-first (YYYYMMDD) worldwide, regardless
# of the user's regional date format -- not ambiguous the way a
# manually-typed date is, so these are checked first and trusted as-is.
FIXED_YMD_PATTERNS = [
    # IMG_20240315_143022.jpg / VID_20240315_143022.mp4 / PXL_20240315_143022.jpg
    r'(?:^|[_-])(\d{4})(\d{2})(\d{2})[_-](\d{2})(\d{2})(\d{2})(?:$|[_.-])',
    # Screenshot_20240315-143022.png
    r'(?:^|[_-])(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})(?:$|[_.-])',
    # 2024-03-15 14.30.22  or  2024-03-15_14-30-22  (WhatsApp / desktop export style)
    r'(\d{4})-(\d{2})-(\d{2})[ _](\d{2})[.:-](\d{2})[.:-](\d{2})',
]

# A bare numeric date with the year FIRST is also unambiguous by
# position -- the 4-digit group can only be the year, regardless of
# separator style. Boundary accepts a leading word/prefix followed by
# '_', '-', space, or '(' -- covers "2024-03-15.pdf" and
# "photo-2024-03-15.jpg" alike.
YMD_DATE_ONLY_PATTERN = r'(?:^|[_\-\s(])(\d{4})[-_](\d{1,2})[-_](\d{1,2})(?:$|[_\-\s).])'

# A bare numeric date with the year LAST is genuinely ambiguous --
# handled separately below, trying both month-first and day-first
# readings. Same boundary reasoning as above -- covers both
# "03-15-2024.jpg" and "photo-03-15-2024.jpg".
YEAR_LAST_DATE_PATTERN = r'(?:^|[_\-\s(])(\d{1,2})[-_.](\d{1,2})[-_.](\d{4})(?:$|[_\-\s).])'


def _is_plausible(year, month=1, day=1):
    if year < EARLIEST_PLAUSIBLE_YEAR or year > datetime.now().year + 1:
        return False
    try:
        datetime(year, month, day)
        return True
    except ValueError:
        return False


def get_date_from_filename(file_path):
    """
    Try to extract a date from the file's own filename (not its folder).
    Returns a datetime, or None.
    """
    name = Path(file_path).stem

    for pattern in FIXED_YMD_PATTERNS:
        match = re.search(pattern, name)
        if match:
            year, month, day, hour, minute, second = (int(g) for g in match.groups())
            if _is_plausible(year, month, day):
                try:
                    return datetime(year, month, day, hour, minute, second)
                except ValueError:
                    pass

    match = re.search(YMD_DATE_ONLY_PATTERN, name)
    if match:
        year, month, day = (int(g) for g in match.groups())
        if _is_plausible(year, month, day):
            return datetime(year, month, day)

    match = re.search(YEAR_LAST_DATE_PATTERN, name)
    if match:
        a, b, year = (int(g) for g in match.groups())
        mdy_valid = _is_plausible(year, a, b)   # a = month, b = day (US)
        dmy_valid = _is_plausible(year, b, a)   # b = month, a = day (European)
        if mdy_valid:
            return datetime(year, a, b)
        elif dmy_valid:
            return datetime(year, b, a)

    return None
