"""
ChronoVault archiver module.

Handles copying of images to the vault archive with date-based organization
using EXIF data and stores metadata in the database.

Author: chronomicron@gmail.com
Created: 2025-05-04
Version History:
    v1.0.0 (2025-05-04): Initial version with multithreaded copying.
    v1.0.2 (2025-05-13): Fixed scan_results.json processing to handle list.
    v1.0.3 (2025-05-13): Added duplicate filename handling and verification.
    v1.0.4 (2025-05-13): Fixed string handling in get_unique_dest_path.
    v1.0.5 (2025-05-13): Use queue-based database insertions to fix locking.
"""

import json
import shutil
from pathlib import Path
from datetime import datetime
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
import chronovault.database as database
import chronovault.config as config
import logging
import sqlite3

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def init_archiver():
    """Initialize the archiver module."""
    return "Archiver module initialized"

def extract_exif_data(image_path):
    """Extract EXIF data including date and other metadata."""
    try:
        with Image.open(image_path) as img:
            exif_data = img.getexif()
            if not exif_data:
                logging.warning(f"No EXIF data found for {image_path}")
                return None, None, None

            # Extract date (prioritize DateTimeOriginal, then DateTime)
            date_taken = None
            date_str = exif_data.get(36867)  # DateTimeOriginal
            if date_str:
                date_taken = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
            else:
                date_str = exif_data.get(306)  # DateTime
                if date_str:
                    date_taken = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")

            # Extract camera model (EXIF tag 272)
            camera_model = exif_data.get(272, "Unknown")

            # Extract resolution (EXIF tags 282 and 283 for X/Y resolution)
            x_res = exif_data.get(282)
            y_res = exif_data.get(283)
            resolution = f"{x_res}x{y_res}" if x_res and y_res else "Unknown"

            return date_taken, camera_model, resolution
    except Exception as e:
        logging.warning(f"Failed to extract EXIF data from {image_path}: {e}")
        return None, None, None

def extract_image_date(image_path):
    """Extract the date an image was taken, with fallback to file metadata."""
    date_taken, _, _ = extract_exif_data(image_path)
    if date_taken:
        return date_taken

    # Fallback to file modification time
    try:
        mtime = Path(image_path).stat().st_mtime
        return datetime.fromtimestamp(mtime)
    except Exception as e:
        logging.error(f"Failed to get file modification time for {image_path}: {e}")
        return None

def get_unique_dest_path(dest_dir, src_name):
    """Generate a unique destination path by appending an index if needed."""
    src_path = Path(src_name)  # Convert string to Path object
    dest_path = dest_dir / src_path.name
    if not dest_path.exists():
        return dest_path

    base, ext = src_path.stem, src_path.suffix
    index = 1
    while True:
        new_name = f"{base}_{index}{ext}"
        new_path = dest_dir / new_name
        if not new_path.exists():
            return new_path
        index += 1

def process_image(image_path, vault_dir, db_path, delete_originals, status_callback):
    """Process a single image: extract EXIF, copy, and enqueue metadata."""
    src_path = Path(image_path)
    if not src_path.exists():
        status_callback(f"Skipping non-existent image: {src_path}")
        logging.warning(f"Non-existent image: {src_path}")
        return False

    # Extract EXIF data
    date_taken, camera_model, resolution = extract_exif_data(src_path)
    if not date_taken:
        date_taken = extract_image_date(src_path)

    # Determine destination
    vault_path = Path(vault_dir)
    archive_path = vault_path / "Archive"
    if date_taken:
        year, month, day = date_taken.strftime("%Y"), date_taken.strftime("%m"), date_taken.strftime("%d")
        dest_dir = archive_path / year / month / day
        creation_date = date_taken.strftime("%Y-%m-%d %H:%M:%S")
    else:
        dest_dir = archive_path / "Unknown"
        creation_date = "Unknown"
        status_callback(f"No valid date for {src_path}, using catchall folder")

    # Create destination folder
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        status_callback(f"Error: Failed to create destination folder {dest_dir}: {e}")
        logging.error(f"Failed to create destination folder {dest_dir}: {e}")
        return False

    # Copy image to unique path
    dest_path = get_unique_dest_path(dest_dir, src_path.name)
    try:
        shutil.copy2(src_path, dest_path)
        status_callback(f"Copied image to {dest_path}")
        logging.info(f"Copied image to {dest_path}")

        # Prepare metadata for database
        image_info = {
            "relative_path": str(dest_path.relative_to(vault_path)),
            "date_taken": creation_date,
            "file_creation_date": creation_date,
            "camera_model": camera_model,
            "shooting_mode": "",
            "image_quality": resolution,
            "metering_mode": "",
            "af_mode": "",
            "exposure_compensation": "",
            "white_balance": "",
            "picture_style": "",
            "shutter_speed": "",
            "aperture": "",
            "focal_length": "",
            "iso": "",
            "gps_data": "",
            "ai_labels": ""
        }
        database.enqueue_insert(db_path, image_info, status_callback)

        # Delete original if requested
        if delete_originals:
            try:
                src_path.unlink()
                status_callback(f"Deleted original image: {src_path}")
                logging.info(f"Deleted original image: {src_path}")
            except Exception as e:
                status_callback(f"Error: Failed to delete original {src_path}: {e}")
                logging.error(f"Failed to delete original {src_path}: {e}")
        return True
    except Exception as e:
        status_callback(f"Error: Failed to copy {src_path} to {dest_path}: {e}")
        logging.error(f"Failed to copy {src_path} to {dest_path}: {e}")
        return False

def copy_images(vault_dir, delete_originals, status_callback):
    """Copy images from scan_results.json to vault archive with multithreading."""
    logging.info(f"Starting image copying to {vault_dir}")
    vault_path = Path(vault_dir)
    archive_path = vault_path / "Archive"
    catchall_path = archive_path / "Unknown"
    db_path = vault_path / "Database" / "chronovault.db"

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
        images = [item["original_path"] for item in results]
        scanned_count = len(images)
        status_callback(f"Found {scanned_count} images in scan results")
    except Exception as e:
        status_callback(f"Error: Failed to read scan results: {e}")
        logging.error(f"Failed to read scan results: {e}")
        return

    # Process images with thread pool
    config_data = config.load_config()
    max_threads = config_data.get("max_threads", 4)
    status_callback(f"Starting image processing with {max_threads} threads")
    logging.info(f"Starting image processing with {max_threads} threads")
    copied_count = 0
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        futures = [
            executor.submit(process_image, image_path, vault_dir, db_path, delete_originals, status_callback)
            for image_path in images
        ]
        for future in futures:
            if future.result():
                copied_count += 1

    # Wait for database queue to drain
    database.insert_queue.join()
    status_callback("All database insertions completed")
    logging.info("All database insertions completed")

    # Verify counts
    status_callback(f"Copied {copied_count}/{scanned_count} images")
    logging.info(f"Copied {copied_count}/{scanned_count} images")
    if copied_count != scanned_count:
        status_callback(f"Warning: Not all images copied ({copied_count}/{scanned_count})")
        logging.warning(f"Not all images copied ({copied_count}/{scanned_count})")

    # Verify database entries
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM images")
            db_count = cursor.fetchone()[0]
        status_callback(f"Stored {db_count}/{copied_count} images in database")
        logging.info(f"Stored {db_count}/{copied_count} images in database")
        if db_count != copied_count:
            status_callback(f"Warning: Database entries ({db_count}) do not match copied images ({copied_count})")
            logging.warning(f"Database entries ({db_count}) do not match copied images ({copied_count})")
    except Exception as e:
        status_callback(f"Error: Failed to verify database entries: {e}")
        logging.error(f"Failed to verify database entries: {e}")