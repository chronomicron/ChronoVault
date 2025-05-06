"""
ChronoVault archiver module.

Handles copying of images to the vault archive with date-based organization
using EXIF data and stores metadata in the database.

Author: chronomicron@gmail.com
Created: 2025-05-04
Version: 1.0.0
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

# Set up logging
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

def process_image(image_path, vault_dir, db_path, delete_originals, status_callback):
    """Process a single image: extract EXIF, copy, and store in database."""
    src_path = Path(image_path)
    if not src_path.exists():
        status_callback(f"Skipping non-existent image: {src_path}")
        logging.warning(f"Non-existent image: {src_path}")
        return

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
        return

    # Copy image
    dest_path = dest_dir / src_path.name
    try:
        shutil.copy2(src_path, dest_path)
        status_callback(f"Copied image to {dest_path}")
        logging.info(f"Copied image to {dest_path}")

        # Insert metadata into database
        database.insert_image(db_path, str(dest_path), creation_date, camera_model, resolution, status_callback)

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
        images = results.get("images", [])
    except Exception as e:
        status_callback(f"Error: Failed to read scan results: {e}")
        logging.error(f"Failed to read scan results: {e}")
        return

    # Process images with thread pool
    config_data = config.load_config()
    max_threads = config_data.get("max_threads", 4)
    status_callback(f"Starting image processing with {max_threads} threads")
    logging.info(f"Starting image processing with {max_threads} threads")
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        futures = [
            executor.submit(process_image, image_path, vault_dir, db_path, delete_originals, status_callback)
            for image_path in images
        ]
        for future in futures:
            future.result()  # Wait for all threads to complete