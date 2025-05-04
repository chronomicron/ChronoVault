"""
ChronoVault archiver module.

Handles copying of images to the vault archive with date-based organization
using EXIF data.

Author: chronomicron@gmail.com
Created: 2025-05-04
"""

import json
import shutil
from pathlib import Path
from datetime import datetime
from PIL import Image
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def init_archiver():
    """Initialize the archiver module."""
    return "Archiver module initialized"

def extract_image_date(image_path):
    """Extract the date an image was taken from EXIF or file metadata."""
    try:
        # Try EXIF data
        with Image.open(image_path) as img:
            exif_data = img.getexif()
            if exif_data:
                # EXIF tag 36867 is DateTimeOriginal
                date_str = exif_data.get(36867)
                if date_str:
                    return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
    except Exception as e:
        logging.warning(f"Failed to extract EXIF data from {image_path}: {e}")

    # Fallback to file modification time
    try:
        mtime = Path(image_path).stat().st_mtime
        return datetime.fromtimestamp(mtime)
    except Exception as e:
        logging.error(f"Failed to get file modification time for {image_path}: {e}")
        return None

def copy_images(vault_dir, delete_originals, status_callback):
    """Copy images from scan_results.json to vault archive with date-based folders."""
    logging.info(f"Starting image copying to {vault_dir}")
    vault_path = Path(vault_dir)
    archive_path = vault_path / "Archive"
    catchall_path = archive_path / "Unknown"
    
    # Create archive and catchall folders
    try:
        archive_path.mkdir(parents=True, exist_ok=True)
        catchall_path.mkdir(parents=True, exist_ok=True)
        status_callback(f"Created archive folder: {archive_path}")
    except Exception as e:
        status_callback(f"Error: Failed to create archive folder: {e}")
        logging.error(f"Failed to create archive folder: {e}")
        return

    # Read scan results
    temp_file = Path("scan_results.json")
    if not temp_file.exists():
        status_callback("Error: No scan results found")
        logging.error("No scan results found")
        return
    
    try:
        with temp_file.open('r') as f:
            results = json.load(f)
        images = results.get("images", [])
    except Exception as e:
        status_callback(f"Error: Failed to read scan results: {e}")
        logging.error(f"Failed to read scan results: {e}")
        return

    for image_path in images:
        src_path = Path(image_path)
        if not src_path.exists():
            status_callback(f"Skipping non-existent image: {src_path}")
            logging.warning(f"Non-existent image: {src_path}")
            continue

        # Extract date
        date_taken = extract_image_date(src_path)
        if date_taken:
            year, month, day = date_taken.strftime("%Y"), date_taken.strftime("%m"), date_taken.strftime("%d")
            dest_dir = archive_path / year / month / day
        else:
            dest_dir = catchall_path
            status_callback(f"No valid date for {src_path}, using catchall folder")

        # Create destination folder
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            status_callback(f"Error: Failed to create destination folder {dest_dir}: {e}")
            logging.error(f"Failed to create destination folder {dest_dir}: {e}")
            continue

        # Copy image
        dest_path = dest_dir / src_path.name
        try:
            shutil.copy2(src_path, dest_path)
            status_callback(f"Copied image to {dest_path}")
            logging.info(f"Copied image to {dest_path}")

            # Delete original if requested
            if delete_originals:
                try:
                    src_path.unlink()
                    status_callback(f"Deleted original image: {src_path}")
                    logging.info(f"Deleted original image: {src_path}")
                except Exception as e:
                    status_callback(f"Error: Failed to delete original {src_path}: {e}")
                    logging.error(f"Failed to delete original {src_path}: {e}")
        except Exception as e:
            status_callback(f"Error: Failed to copy {src_path} to {dest_path}: {e}")
            logging.error(f"Failed to copy {src_path} to {dest_path}: {e}")