"""
ChronoVault scanner module.

Scans directories for images, extracts EXIF data, and saves results.

Author: chronomicron@gmail.com
Created: 2025-05-03
Version: 1.0.3
"""

import logging
import os
from pathlib import Path
import json
from PIL import Image
from PIL.ExifTags import TAGS
from datetime import datetime
from PIL.TiffImagePlugin import IFDRational

def init_scanner():
    """Initialize the scanner module."""
    return "Scanner module initialized"

def get_exif_data(image_path):
    """Extract EXIF data from an image, ensuring JSON-serializable values."""
    try:
        with Image.open(image_path) as img:
            exif_data = img._getexif()
            if not exif_data:
                logging.info(f"No EXIF data found for {image_path}")
                return {}
            exif = {}
            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)
                # Convert IFDRational to float or string
                if isinstance(value, IFDRational):
                    try:
                        value = float(value)
                    except (TypeError, ZeroDivisionError):
                        value = str(value)
                # Ensure other values are serializable
                elif not isinstance(value, (str, int, float, bool, type(None))):
                    value = str(value)
                exif[tag] = value
            return exif
    except Exception as e:
        logging.error(f"Error reading EXIF data for {image_path}: {e}")
        return {}

def parse_date(exif_data):
    """Parse the date from EXIF data, handle invalid or missing dates."""
    date_fields = ["DateTimeOriginal", "DateTime"]
    for field in date_fields:
        if field in exif_data:
            try:
                date_str = exif_data[field]
                return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
            except (ValueError, TypeError) as e:
                logging.warning(f"Invalid date format in {field}: {e}")
    logging.info("No valid date found in EXIF data")
    return None

def get_file_creation_date(file_path):
    """Get file creation date from filesystem metadata."""
    try:
        ctime = os.stat(file_path).st_ctime
        return datetime.fromtimestamp(ctime).isoformat()
    except Exception as e:
        logging.warning(f"Error getting file creation date for {file_path}: {e}")
        return None

def parse_gps_data(exif_data):
    """Parse GPSInfo into latitude/longitude strings."""
    if "GPSInfo" not in exif_data:
        return None
    try:
        gps_info = exif_data["GPSInfo"]
        lat = gps_info.get(2)  # GPSLatitude
        lat_ref = gps_info.get(1)  # GPSLatitudeRef
        lon = gps_info.get(4)  # GPSLongitude
        lon_ref = gps_info.get(3)  # GPSLongitudeRef
        if not all([lat, lat_ref, lon, lon_ref]):
            return None
        # Convert degrees, minutes, seconds to decimal
        lat = float(lat[0]) + float(lat[1]) / 60 + float(lat[2]) / 3600
        lon = float(lon[0]) + float(lon[1]) / 60 + float(lon[2]) / 3600
        if lat_ref == "S":
            lat = -lat
        if lon_ref == "W":
            lon = -lon
        return f"{lat:.6f},{lon:.6f}"
    except Exception as e:
        logging.warning(f"Error parsing GPS data: {e}")
        return None

def scan_directory(scan_dir, vault_dir, status_callback):
    """Scan a directory for images and save results."""
    scan_dir = Path(scan_dir).resolve()  # Resolve to absolute path
    vault_dir = Path(vault_dir)
    results = []
    visited_paths = set()  # Track visited paths to prevent loops

    status_callback(f"Starting scan of {scan_dir}")

    for file_path in scan_dir.rglob("*"):
        try:
            # Check for symbolic links and resolve path
            if file_path.is_symlink():
                status_callback(f"Skipping symbolic link: {file_path}")
                continue
            resolved_path = file_path.resolve()
            # Skip if resolved path is already visited or points to parent
            if resolved_path in visited_paths or scan_dir in resolved_path.parents:
                status_callback(f"Skipping path to avoid loop: {file_path}")
                continue
            visited_paths.add(resolved_path)

            if file_path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
                exif_data = get_exif_data(file_path)
                date_taken = parse_date(exif_data)
                relative_path = file_path.relative_to(scan_dir)
                image_info = {
                    "original_path": str(file_path),
                    "relative_path": str(relative_path),
                    "date_taken": date_taken.isoformat() if date_taken else None,
                    "file_creation_date": get_file_creation_date(file_path),
                    "camera_model": exif_data.get("Model", ""),
                    "shooting_mode": exif_data.get("ExposureProgram", ""),
                    "image_quality": exif_data.get("Compression", ""),
                    "metering_mode": exif_data.get("MeteringMode", ""),
                    "af_mode": exif_data.get("FocusMode", ""),
                    "exposure_compensation": exif_data.get("ExposureCompensation", ""),
                    "white_balance": exif_data.get("WhiteBalance", ""),
                    "picture_style": exif_data.get("PictureStyle", ""),
                    "shutter_speed": exif_data.get("ExposureTime", ""),
                    "aperture": exif_data.get("FNumber", ""),
                    "focal_length": exif_data.get("FocalLength", ""),
                    "iso": exif_data.get("ISOSpeedRatings", ""),
                    "gps_data": parse_gps_data(exif_data),
                    "ai_labels": ""  # Placeholder for future AI labels
                }
                results.append(image_info)
                status_callback(f"Found image: {file_path}")
        except Exception as e:
            status_callback(f"Error processing {file_path}: {e}")

    # Save results to JSON
    output_file = Path("scan_results.json")
    try:
        with output_file.open("w") as f:
            json.dump(results, f, indent=4)
        status_callback(f"Scan results saved to {output_file}")
    except Exception as e:
        status_callback(f"Error saving scan results: {e}")

def init_module():
    """Initialize the scanner module (for compatibility)."""
    return init_scanner()