"""
multi_tools/analyze_folder.py

Extracts a date from one of a file's containing folder names. Lives in
multi_tools/ alongside analyze_filename.py -- applies to any file type.

A folder named "2024" or "March 2024" is real evidence, but weaker than
a filename pattern: it's just as likely to reflect when someone SORTED
or IMPORTED files as when they were actually taken. Base confidence 40
in analyze_date -- the same tier as filesystem fallback, reflecting "a
real clue, but not a strong one." Always at day-level precision at best
(a folder can't tell you the time), often only month or year precision.
"""

import re
from pathlib import Path
from datetime import datetime

EARLIEST_PLAUSIBLE_YEAR = 1990

# Checked from the immediate parent folder outward, first match wins.
FOLDER_PATTERNS = [
    (r'^(\d{4})[-_](\d{2})$', 'ym'),                   # "2024-03" or "2024_03"
    (r'^(\d{4})$', 'y'),                                 # "2024"
    (r'^([A-Za-z]+)\s+(\d{4})$', 'month_name_year'),      # "March 2024"
]

MONTH_NAMES = {
    'january': 1, 'jan': 1, 'february': 2, 'feb': 2, 'march': 3, 'mar': 3,
    'april': 4, 'apr': 4, 'may': 5, 'june': 6, 'jun': 6, 'july': 7, 'jul': 7,
    'august': 8, 'aug': 8, 'september': 9, 'sep': 9, 'sept': 9,
    'october': 10, 'oct': 10, 'november': 11, 'nov': 11, 'december': 12, 'dec': 12,
}


def _is_plausible(year, month=1, day=1):
    if year < EARLIEST_PLAUSIBLE_YEAR or year > datetime.now().year + 1:
        return False
    try:
        datetime(year, month, day)
        return True
    except ValueError:
        return False


def get_date_from_path(file_path):
    """
    Try to extract a date from one of the file's containing folder names,
    checked from the immediate parent outward -- first match wins.
    Returns a datetime, or None.
    """
    for folder in Path(file_path).parents:
        folder_name = folder.name.strip()
        if not folder_name:
            continue
        for pattern, kind in FOLDER_PATTERNS:
            match = re.match(pattern, folder_name)
            if not match:
                continue
            try:
                if kind == 'ym':
                    year, month = int(match.group(1)), int(match.group(2))
                    if _is_plausible(year, month, 1):
                        return datetime(year, month, 1)
                elif kind == 'y':
                    year = int(match.group(1))
                    if _is_plausible(year, 1, 1):
                        return datetime(year, 1, 1)
                elif kind == 'month_name_year':
                    month = MONTH_NAMES.get(match.group(1).lower())
                    year = int(match.group(2))
                    if month and _is_plausible(year, month, 1):
                        return datetime(year, month, 1)
            except (ValueError, TypeError):
                continue
    return None
