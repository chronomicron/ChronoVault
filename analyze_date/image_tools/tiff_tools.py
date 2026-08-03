"""
image_tools/tiff_tools.py

TIFF date extraction -- reads a TIFF file's own baseline DateTime tag
(306), distinct from EXIF's DateTimeOriginal. Moved here from
analyze_date/analyze_date.py, unchanged.
"""

from datetime import datetime
from PIL import Image


def get_tiff_datetime(file_path):
    """
    Pull a date out of a TIFF file's baseline DateTime tag (306) --
    TIFF's own native timestamp field, distinct from EXIF's
    DateTimeOriginal, and read via getexif() rather than _getexif()
    (which doesn't exist on TIFF images at all -- confirmed directly,
    not assumed; calling it raises AttributeError).

    Only meaningful for TIFF files -- callers should only invoke this for
    files identified as TIFF (by extension or explicit type override).
    """
    try:
        image = Image.open(file_path)
        exif = image.getexif()
        value = exif.get(306)
    except Exception:
        return None
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None
    