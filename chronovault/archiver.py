"""
ChronoVault archiver module.

Handles copying images to the vault archive and updating the database.

Author: chronomicron@gmail.com
Created: 2025-05-03
Version: 1.0.0
"""

import json
import shutil
from pathlib import Path
from datetime import datetime
import logging
import chronovault.database as database

def init_archiver():
    """Initialize the archiver module."""
    return "Archiver module initialized"

def copy_images(vault_dir, delete_originals, status_callback):
    """Copy images to the vault archive and update the database."""
    vault_dir = Path(vault_dir)
    db_path = vault_dir / "Database" / "chronovault.db"
    archive_dir = vault_dir / "Archive"

    # Load scan results
    scan_results_file = Path("scan_results.json")
    if not scan_results_file.exists():
        status_callback("Error: No scan results found")
        return

    try:
        with scan_results_file.open() as f:
            images = json.load(f)
    except Exception as e:
        status_callback(f"Error reading scan results: {e}")
        return

    status_callback(f"Starting image copying to {vault_dir}")

    for image_info in images:
        try:
            src_path = Path(image_info["original_path"])
            if not src_path.exists():
                status_callback(f"Source image not found: {src_path}")
                continue

            # Determine destination path
            if image_info["date_taken"]:
                try:
                    date_taken = datetime.fromisoformat(image_info["date_taken"])
                    dest_dir = archive_dir / f"{date_taken.year}/{date_taken.month:02d}/{date_taken.day:02d}"
                except ValueError:
                    dest_dir = archive_dir / "Unknown"
            else:
                dest_dir = archive_dir / "Unknown"

            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / src_path.name
            relative_path = str(dest_path.relative_to(vault_dir))
            image_info["relative_path"] = relative_path

            # Copy image
            shutil.copy2(src_path, dest_path)
            status_callback(f"Copied image to {dest_path}")

            # Insert metadata into database
            database.insert_image_metadata(db_path, image_info, status_callback)

            # Delete original if requested
            if delete_originals:
                try:
                    src_path.unlink()
                    status_callback(f"Deleted original image: {src_path}")
                except Exception as e:
                    status_callback(f"Error deleting original image {src_path}: {e}")

        except Exception as e:
            status_callback(f"Error processing image {src_path}: {e}")

def init_module():
    """Initialize the archiver module (for compatibility)."""
    return init_archiver()