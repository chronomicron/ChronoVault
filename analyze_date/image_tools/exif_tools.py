"""
image_tools/exif_tools.py

EXIF DateTimeOriginal/DateTimeDigitized extraction. Moved here from
analyze_date/analyze_date.py, unchanged.
"""

from datetime import datetime


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
