"""
image_tools/gps_tools.py

EXIF GPS timestamp extraction. Moved here from analyze_date/analyze_date.py,
unchanged.
"""

from datetime import datetime


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
    