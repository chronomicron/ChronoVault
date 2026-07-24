"""
analyze_date.py

Given evidence about a media file (its EXIF data and file path), work out
the most likely date it was created, where that date came from, and
whether it should be considered uncertain.

This module never moves, copies, or renames anything -- it only looks at
evidence and reports back a conclusion. Any tool that needs a date
decision (Importer today, possibly others later, e.g. an AI labeler
following the same "hand me evidence, get back a scored answer" pattern)
builds a small evidence bundle and calls analyze_date() with it.
"""

from pathlib import Path
from datetime import datetime

# No digital camera existed before this date, so any "date taken" earlier
# than this is treated as implausible. (Also happens to be the author's
# birthday -- also predates digital cameras. Small tribute, not a bug.)
EARLIEST_PLAUSIBLE_DATE = datetime(1972, 7, 26)


def get_photo_date_from_exif(readable_exif):
    """Pull DateTimeOriginal or DateTimeDigitized out of a readable EXIF dict."""
    for tag_name in ('DateTimeOriginal', 'DateTimeDigitized'):
        value = readable_exif.get(tag_name)
        if value:
            try:
                return datetime.strptime(value, "%Y:%m:%d %H:%M:%S"), tag_name
            except ValueError:
                continue
    return None, None


def get_filesystem_creation_date(file_path):
    """File system creation date, used as a fallback and for cross-checking EXIF."""
    try:
        stat = Path(file_path).stat()
        return datetime.fromtimestamp(stat.st_ctime)
    except Exception:
        return None


def analyze_date(evidence):
    """
    Work out the date to use for a file, where that date came from, and
    whether it should be flagged as uncertain.

    'evidence' is a dict describing what we know about the file:
        {
            'file_path': ...,               # required
            'readable_exif': {...},         # EXIF tag dict, or {} if none
            'mismatch_threshold_days': 1,   # days of EXIF/filesystem disagreement allowed
        }

    Returns a dict:
        {
            'date_taken': datetime or None,
            'date_source': 'exif_original' | 'exif_digitized' | 'filesystem_fallback',
            'filesystem_creation_date': datetime or None,
            'date_uncertain': bool,
        }

    (This is round 1: same logic Importer used to have, just moved here
    unchanged. Confidence scoring comes next, as its own follow-up step.)
    """
    file_path = evidence['file_path']
    readable_exif = evidence.get('readable_exif', {})
    mismatch_threshold_days = evidence.get('mismatch_threshold_days', 1)

    exif_date, exif_tag = get_photo_date_from_exif(readable_exif)
    fs_date = get_filesystem_creation_date(file_path)

    date_uncertain = False

    if exif_date:
        date_taken = exif_date
        date_source = 'exif_original' if exif_tag == 'DateTimeOriginal' else 'exif_digitized'

        # Trigger: EXIF date and filesystem date disagree by more than the threshold.
        if fs_date:
            delta_days = abs((exif_date - fs_date).days)
            if delta_days > mismatch_threshold_days:
                date_uncertain = True
    else:
        # Trigger: no EXIF date at all -- falling back to filesystem date.
        date_taken = fs_date
        date_source = 'filesystem_fallback'
        date_uncertain = True

    # Trigger: implausible date -- before digital cameras existed, or in the future.
    if date_taken:
        if date_taken < EARLIEST_PLAUSIBLE_DATE or date_taken > datetime.now():
            date_uncertain = True

    return {
        'date_taken': date_taken,
        'date_source': date_source,
        'filesystem_creation_date': fs_date,
        'date_uncertain': date_uncertain,
    }
