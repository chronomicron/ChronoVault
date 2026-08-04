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

import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime

from PIL import Image

from .image_tools.tiff_tools import get_tiff_datetime
from .image_tools.exif_tools import get_photo_date_from_exif

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


def get_gps_datetime(readable_exif):
    """
    Pull a date/time out of EXIF GPSDateStamp + GPSTimeStamp, if present.

    This comes from the satellite signal at the moment of capture, not
    the camera's own internal clock -- so it's immune to a wrong or
    never-set camera clock, a common real-world source of bad
    DateTimeOriginal values. Note the result is in UTC, while
    DateTimeOriginal is typically local time; a several-hour difference
    near a timezone boundary is expected, not necessarily a disagreement
    (the existing mismatch_threshold_days tolerance already absorbs a
    small gap like this in most cases).
    """
    from PIL.ExifTags import GPSTAGS

    gps_info = readable_exif.get('GPSInfo')
    if not gps_info:
        return None

    gps_tags = {GPSTAGS.get(key, key): value for key, value in gps_info.items()}
    date_stamp = gps_tags.get('GPSDateStamp')
    time_stamp = gps_tags.get('GPSTimeStamp')
    if not date_stamp:
        return None

    try:
        year, month, day = (int(part) for part in date_stamp.split(':'))
        if time_stamp:
            hour, minute, second = (int(float(part)) for part in time_stamp)
        else:
            hour = minute = second = 0
        return datetime(year, month, day, hour, minute, second)
    except (ValueError, TypeError):
        return None


def _parse_xmp_date_string(text):
    """
    Parse an XMP date string. Follows ISO 8601, but XMP allows several
    levels of precision (date-only, with time, with/without a timezone
    offset) -- this handles all of them.

    Any timezone offset is deliberately stripped after parsing, so the
    result is a naive datetime like every other signal in this module
    (EXIF and filesystem dates are already naive/local, un-normalized --
    this keeps XMP consistent with that existing looseness rather than
    introducing a new kind of inconsistency).
    """
    text = text.strip()
    if text.endswith('Z'):
        text = text[:-1] + '+00:00'
    try:
        parsed = datetime.fromisoformat(text)
        return parsed.replace(tzinfo=None)
    except ValueError:
        pass
    try:
        return datetime.strptime(text, '%Y-%m-%d')
    except ValueError:
        return None


def get_xmp_datetime(file_path):
    """
    Pull a date out of XMP metadata, if present -- the kind of thing
    editors like Photoshop and Lightroom embed, separate from EXIF.

    Tries xmp:CreateDate and photoshop:DateCreated first (treated as
    equivalent -- both claim to represent creation), falling back to
    xmp:ModifyDate only if neither is present. ModifyDate reflects a
    LATER edit, not the original creation, so it's a meaningfully weaker
    claim -- callers should treat it with much lower confidence (see
    BASE_CONFIDENCE['xmp_modify_date']).

    Uses a hand-rolled XML parser (xml.etree.ElementTree on the raw XMP
    bytes), not Pillow's getxmp() convenience method -- getxmp() works in
    testing, but its behavior isn't something this module wants to depend
    on being consistent across Pillow versions (the same lesson learned
    the hard way with Image.Exif() writing). It also flattens namespaces
    into one dict, risking a silent collision between two different
    namespaced fields that happen to share a local name -- staying with
    explicit namespaces here avoids that.

    Returns (date, source) where source is 'xmp_create_date' or
    'xmp_modify_date', or (None, None) if no usable date was found.
    """
    try:
        image = Image.open(file_path)
        raw_xmp = image.info.get('xmp')
    except Exception:
        return None, None

    if not raw_xmp:
        return None, None

    try:
        xmp_text = raw_xmp.decode('utf-8') if isinstance(raw_xmp, bytes) else raw_xmp
        root = ET.fromstring(xmp_text)
    except ET.ParseError:
        return None, None

    ns = {
        'xmp': 'http://ns.adobe.com/xap/1.0/',
        'photoshop': 'http://ns.adobe.com/photoshop/1.0/',
    }

    for tag, source in [
        ('xmp:CreateDate', 'xmp_create_date'),
        ('photoshop:DateCreated', 'xmp_create_date'),
        ('xmp:ModifyDate', 'xmp_modify_date'),
    ]:
        element = root.find(f'.//{tag}', ns)
        if element is not None and element.text:
            date = _parse_xmp_date_string(element.text.strip())
            if date:
                return date, source

    return None, None


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
        'xmp_modify_date': 'XMP modify date',
        'filesystem_fallback': 'filesystem creation date',
    }
    return labels.get(signal['source'], signal['source'])


# Extensions treated as "JPEG-family" (EXIF/GPS/XMP signals) vs TIFF
# (its own baseline DateTime tag). Add new types here as new evidence-
# gathering functions are built for them.
JPEG_LIKE_EXTENSIONS = {'.jpg', '.jpeg'}
TIFF_EXTENSIONS = {'.tif', '.tiff'}


def gather_signals(file_path, readable_exif, file_type):
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
        }

    'file_type', if given, determines which evidence-gathering functions
    run (see gather_signals()) -- pass this when the caller already knows
    the real type and it might not match the extension. If omitted, the
    type is inferred from the file's own extension.

    Returns a dict:
        {
            'date_taken': datetime or None,
            'date_source': 'exif_original' | 'exif_digitized' | 'tiff_datetime' | 'filesystem_fallback' | None,
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

    signals, fs_date = gather_signals(file_path, readable_exif, file_type)

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
