"""
analyze_date.py

Given evidence about a media file (its EXIF data and file path), work out
the most likely date it was created, how confident it is in that date,
and why.

This module never moves, copies, or renames anything -- it only looks at
evidence and reports back a scored, explainable conclusion. Any tool that
needs a date decision (Importer today, possibly others later, e.g. an AI
labeler following the same "hand it evidence, get back a scored answer"
pattern) builds a small evidence bundle and calls analyze_date() with it.

DESIGN NOTE -- built for more evidence than we currently have:
There are currently three signals: EXIF GPS timestamp (from the satellite,
independent of the camera's clock), EXIF (DateTimeOriginal or
DateTimeDigitized), and the filesystem creation date. But cameras also
often bake the date into the filename (e.g. IMG_20260720_123957.jpg), and
some cameras (Canon SLRs, for instance) write a separate .THM sidecar file
per shot with its own embedded metadata. Both are realistic future
sources of evidence for the same date question.

Rather than write scoring logic that only knows about "EXIF vs.
filesystem", this module treats every date it's given as one signal in a
list, and combines however many signals show up. Adding a new source
later (filename parsing, sidecar files) just means appending one more
signal to the list built in gather_signals() -- the combination logic in
analyze_date() below doesn't change.
"""

from pathlib import Path
from datetime import datetime

from .image_tools.tiff_tools import get_tiff_datetime
from .image_tools.exif_tools import get_photo_date_from_exif
from .image_tools.gps_tools import get_gps_datetime
from .image_tools.xmp_tools import get_xmp_datetime
from .image_tools.ocr_tools import find_date_in_corners

# No digital camera existed before this date, so any "date taken" earlier
# than this is treated as implausible. (Also happens to be the author's
# birthday -- also predates digital cameras. Small tribute, not a bug.)
EARLIEST_PLAUSIBLE_DATE = datetime(1972, 7, 26)

# Starting confidence (0-100) for a signal, before any agreement/mismatch
# adjustment, based purely on how trustworthy that kind of source is.
BASE_CONFIDENCE = {
    'exif_gps': 98,          # from satellite time, not the camera's own clock -- see get_gps_datetime()
    'exif_original': 95,
    'exif_digitized': 85,
    'tiff_datetime': 90,     # TIFF's own baseline DateTime tag -- see get_tiff_datetime()
    'xmp_create_date': 80,   # xmp:CreateDate or photoshop:DateCreated -- see get_xmp_datetime()
    'ocr_corner_stamp': 60,  # OCR-read corner date stamp -- opt-in only, see find_date_in_corners()
    'filesystem_fallback': 30,
    'xmp_modify_date': 20,   # reflects a LATER edit, not original creation -- weak fallback only
    # Future sources will get their own entries here, e.g.:
    # 'filename_pattern': 70,
    # 'sidecar_thm': 90,
}

# How much confidence to add for each additional signal that agrees with
# the primary date (within mismatch_threshold_days), and to subtract for
# each one that disagrees.
AGREEMENT_BONUS = 5
MISMATCH_PENALTY = 25

# If the chosen date is outright implausible (before cameras existed, or
# in the future), confidence is capped this low regardless of source --
# multiple sources agreeing on an impossible date doesn't make it likely.
IMPLAUSIBLE_CONFIDENCE_CAP = 5

# Below this confidence, date_uncertain is set True (kept for any code
# that still wants a simple yes/no rather than reading the number).
UNCERTAIN_THRESHOLD = 50


def get_filesystem_creation_date(file_path):
    """File system creation date, used as a fallback and for cross-checking other signals."""
    try:
        stat = Path(file_path).stat()
        return datetime.fromtimestamp(stat.st_ctime)
    except Exception:
        return None


def describe_signal(signal):
    """Short human-readable label for a signal, used to build the 'reason' string."""
    labels = {
        'exif_gps': 'EXIF GPS timestamp',
        'exif_original': 'EXIF (DateTimeOriginal)',
        'exif_digitized': 'EXIF (DateTimeDigitized)',
        'tiff_datetime': 'TIFF DateTime tag',
        'xmp_create_date': 'XMP creation date',
        'ocr_corner_stamp': 'OCR corner date stamp',
        'xmp_modify_date': 'XMP modify date',
        'filesystem_fallback': 'filesystem creation date',
    }
    return labels.get(signal['source'], signal['source'])


# Extensions treated as "JPEG-family" (EXIF/GPS/XMP signals) vs TIFF
# (its own baseline DateTime tag). Add new types here as new evidence-
# gathering functions are built for them.
JPEG_LIKE_EXTENSIONS = {'.jpg', '.jpeg', '.thm'}
TIFF_EXTENSIONS = {'.tif', '.tiff'}
# Deliberately NOT adding '.raw' to TIFF_EXTENSIONS: while Adobe DNG really
# is TIFF-based, manufacturer RAW formats (Canon CR2, Nikon NEF, Sony ARW)
# are NOT, and ".raw" alone doesn't tell us which one a given file is. A
# caller that knows it's dealing with DNG specifically should pass
# file_type='.tiff' explicitly rather than this module guessing wrong for
# every other RAW format.


def gather_signals(file_path, readable_exif, file_type, try_ocr=False):
    """
    Collect every date signal we currently know how to read for a file --
    dispatched by file_type, since different file types carry evidence in
    completely different places (EXIF/GPS/XMP live in JPEG's APP1
    segments; TIFF has its own baseline DateTime tag; a future MP3/MP4
    signal would come from ID3 tags or a container atom, nothing like
    either of these).

    Returns (signals, filesystem_creation_date) where signals is a list of
    dicts: {'date': datetime, 'source': str, 'base_confidence': int}.
    filesystem_creation_date always applies, regardless of file type.

    Adding a new file type means adding a new branch here that calls its
    own evidence-gathering function(s) -- everything in analyze_date()
    itself already knows how to combine however many signals end up in
    the list, with no changes needed there.
    """
    signals = []

    if file_type in JPEG_LIKE_EXTENSIONS:
        gps_date = get_gps_datetime(readable_exif)
        if gps_date:
            signals.append({
                'date': gps_date,
                'source': 'exif_gps',
                'base_confidence': BASE_CONFIDENCE['exif_gps'],
            })

        exif_date, exif_tag = get_photo_date_from_exif(readable_exif)
        if exif_date:
            source = 'exif_original' if exif_tag == 'DateTimeOriginal' else 'exif_digitized'
            signals.append({
                'date': exif_date,
                'source': source,
                'base_confidence': BASE_CONFIDENCE[source],
            })

        xmp_date, xmp_source = get_xmp_datetime(file_path)
        if xmp_date:
            signals.append({
                'date': xmp_date,
                'source': xmp_source,
                'base_confidence': BASE_CONFIDENCE[xmp_source],
            })

    elif file_type in TIFF_EXTENSIONS:
        tiff_date = get_tiff_datetime(file_path)
        if tiff_date:
            signals.append({
                'date': tiff_date,
                'source': 'tiff_datetime',
                'base_confidence': BASE_CONFIDENCE['tiff_datetime'],
            })

    # OCR is deliberately opt-in only -- slow (multiple corners x rotations
    # x preprocessing variants), and only useful for files with weak or no
    # other evidence. Never run unless explicitly requested via try_ocr,
    # and only makes sense for actual images.
    if try_ocr and (file_type in JPEG_LIKE_EXTENSIONS or file_type in TIFF_EXTENSIONS):
        ocr_result = find_date_in_corners(file_path)
        if ocr_result['date']:
            signals.append({
                'date': ocr_result['date'],
                'source': 'ocr_corner_stamp',
                'base_confidence': BASE_CONFIDENCE['ocr_corner_stamp'],
            })

    fs_date = get_filesystem_creation_date(file_path)
    if fs_date:
        signals.append({
            'date': fs_date,
            'source': 'filesystem_fallback',
            'base_confidence': BASE_CONFIDENCE['filesystem_fallback'],
        })

    return signals, fs_date


def analyze_date(evidence):
    """
    Work out the date to use for a file, how confident we are in it, and why.

    'evidence' is a dict describing what we know about the file:
        {
            'file_path': ...,               # required
            'readable_exif': {...},         # EXIF tag dict, or {} if none -- only used for JPEG-family files
            'mismatch_threshold_days': 1,   # days of disagreement allowed before signals "disagree"
            'file_type': '.mp3',            # optional -- overrides extension-based type detection
            'try_ocr': False,               # optional -- explicitly opt in to (slow) OCR corner-stamp scanning
        }

    'file_type', if given, determines which evidence-gathering functions
    run (see gather_signals()) -- pass this when the caller already knows
    the real type and it might not match the extension. If omitted, the
    type is inferred from the file's own extension.

    'try_ocr' defaults to False -- OCR is slow and only useful for files
    already known to have weak or no other evidence (e.g. items already
    sitting in a review bucket). Never runs unless explicitly requested.

    Returns a dict:
        {
            'date_taken': datetime or None,
            'date_source': 'exif_original' | 'exif_digitized' | 'tiff_datetime' | 'ocr_corner_stamp' | 'filesystem_fallback' | None,
            'filesystem_creation_date': datetime or None,
            'confidence': int (0-100),
            'reason': str,               # short human-readable explanation
            'date_uncertain': bool,      # confidence < UNCERTAIN_THRESHOLD, kept for convenience
        }
    """
    file_path = evidence['file_path']
    readable_exif = evidence.get('readable_exif', {})
    mismatch_threshold_days = evidence.get('mismatch_threshold_days', 1)
    file_type = evidence.get('file_type') or Path(file_path).suffix.lower()
    try_ocr = evidence.get('try_ocr', False)

    signals, fs_date = gather_signals(file_path, readable_exif, file_type, try_ocr)

    if not signals:
        return {
            'date_taken': None,
            'date_source': None,
            'filesystem_creation_date': None,
            'confidence': 0,
            'reason': 'No date evidence available (no EXIF, no filesystem date)',
            'date_uncertain': True,
        }

    # The strongest single signal becomes the date actually used.
    primary = max(signals, key=lambda s: s['base_confidence'])
    others = [s for s in signals if s is not primary]

    agreeing = [
        s for s in others
        if abs((s['date'] - primary['date']).days) <= mismatch_threshold_days
    ]
    disagreeing = [s for s in others if s not in agreeing]

    confidence = primary['base_confidence']
    confidence += AGREEMENT_BONUS * len(agreeing)
    confidence -= MISMATCH_PENALTY * len(disagreeing)
    confidence = max(0, min(100, confidence))

    reason = describe_signal(primary)
    if agreeing:
        reason += " -- confirmed by " + ", ".join(describe_signal(s) for s in agreeing)
    if disagreeing:
        reason += " -- disagrees with " + ", ".join(describe_signal(s) for s in disagreeing)

    date_taken = primary['date']
    if date_taken < EARLIEST_PLAUSIBLE_DATE or date_taken > datetime.now():
        confidence = min(confidence, IMPLAUSIBLE_CONFIDENCE_CAP)
        reason += " -- date is implausible (before cameras existed, or in the future)"

    return {
        'date_taken': date_taken,
        'date_source': primary['source'],
        'filesystem_creation_date': fs_date,
        'confidence': confidence,
        'reason': reason,
        'date_uncertain': confidence < UNCERTAIN_THRESHOLD,
    }
    