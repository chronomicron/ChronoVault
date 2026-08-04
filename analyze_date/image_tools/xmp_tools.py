"""
image_tools/xmp_tools.py

XMP metadata extraction (xmp:CreateDate, photoshop:DateCreated,
xmp:ModifyDate). Moved here from analyze_date/analyze_date.py, unchanged.
"""

import xml.etree.ElementTree as ET
from datetime import datetime

from PIL import Image


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
    analyze_date.BASE_CONFIDENCE['xmp_modify_date']).

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
