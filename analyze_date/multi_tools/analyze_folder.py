r"""
multi_tools/analyze_folder.py

Extracts a date from one of a file's containing folder names. Lives in
multi_tools/ alongside analyze_filename.py -- applies to any file type.

A folder named "2024" or "March 2024" is real evidence, but weaker than
a filename pattern: it's just as likely to reflect when someone SORTED
or IMPORTED files as when they were actually taken. Base confidence 40
in analyze_date -- the same tier as filesystem fallback, reflecting "a
real clue, but not a strong one." Always at day-level precision at best
(a folder can't tell you the time), often only month or year precision.

MONTH NAMES: English and French are both supported (see MONTH_NAMES
below). This required a real fix, not just a data addition -- the
month_name_year folder pattern originally matched [A-Za-z]+ only, which
cannot match accented letters at all (French "février" or "août" would
never match, silently, since a regex non-match just falls through to
"no date found" rather than raising anything). Fixed by matching any
non-digit, non-whitespace character instead ([^\W\d_]+), which works for
accented letters in any language, not just the two currently in
MONTH_NAMES -- so adding a third language's month names later needs no
further regex change, only new dictionary entries.
"""

import re
from pathlib import Path
from datetime import datetime

EARLIEST_PLAUSIBLE_YEAR = 1990

# Checked from the immediate parent folder outward, first match wins.
# [^\W\d_]+ matches one or more letters in ANY language/alphabet (not just
# ASCII) -- deliberately broader than [A-Za-z]+ so accented French month
# names (février, août, décembre) actually match, rather than silently
# falling through to "no date found" the way the original ASCII-only
# pattern did.
FOLDER_PATTERNS = [
    (r'^(\d{4})[-_](\d{2})$', 'ym'),                   # "2024-03" or "2024_03"
    (r'^(\d{4})$', 'y'),                                 # "2024"
    (r'^([^\W\d_]+)\s+(\d{4})$', 'month_name_year'),      # "March 2024" / "mars 2024" / "février 2024"
]

MONTH_NAMES = {
    # English
    'january': 1, 'jan': 1, 'february': 2, 'feb': 2, 'march': 3, 'mar': 3,
    'april': 4, 'apr': 4, 'may': 5, 'june': 6, 'jun': 6, 'july': 7, 'jul': 7,
    'august': 8, 'aug': 8, 'september': 9, 'sep': 9, 'sept': 9,
    'october': 10, 'oct': 10, 'november': 11, 'nov': 11, 'december': 12, 'dec': 12,
    # French. Both accented and unaccented spellings are included for
    # each name that has an accent, since real-world folder names survive
    # differently depending on the OS/filesystem/keyboard layout they were
    # created under -- a folder literally named "fevrier 2024" (accent
    # dropped) is just as real-world plausible as "février 2024".
    'janvier': 1,
    'février': 2, 'fevrier': 2, 'fév': 2, 'fev': 2,
    'mars': 3,
    'avril': 4, 'avr': 4,
    'mai': 5,
    'juin': 6,
    'juillet': 7, 'juil': 7,
    'août': 8, 'aout': 8, 'aoû': 8, 'aou': 8,
    'septembre': 9,
    'octobre': 10,
    'novembre': 11,
    'décembre': 12, 'decembre': 12, 'déc': 12, 'dec': 12,
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
