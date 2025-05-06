"""
ChronoVault database module.

Manages the SQLite database for storing image metadata.

Author: chronomicron@gmail.com
Created: 2025-05-03
Version: 1.0.3
"""

import sqlite3
import logging
from pathlib import Path

def init_database():
    """Initialize the database module."""
    return "Database module initialized"

def init_folders(vault_dir, status_callback):
    """Initialize the database and archive folders in the vault directory."""
    vault_dir = Path(vault_dir)
    db_dir = vault_dir / "Database"
    archive_dir = vault_dir / "Archive"
    unknown_dir = archive_dir / "Unknown"

    try:
        db_dir.mkdir(parents=True, exist_ok=True)
        archive_dir.mkdir(parents=True, exist_ok=True)
        unknown_dir.mkdir(parents=True, exist_ok=True)
        status_callback(f"Initialized folders: {db_dir}, {archive_dir}, {unknown_dir}")
    except Exception as e:
        status_callback(f"Error initializing folders: {e}")

def create_database(db_path, status_callback):
    """Create the SQLite database with an images table."""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL,
                    date_taken TEXT,
                    file_creation_date TEXT,
                    camera_model TEXT,
                    shooting_mode TEXT,
                    image_quality TEXT,
                    metering_mode TEXT,
                    af_mode TEXT,
                    exposure_compensation TEXT,
                    white_balance TEXT,
                    picture_style TEXT,
                    shutter_speed TEXT,
                    aperture TEXT,
                    focal_length TEXT,
                    iso TEXT,
                    gps_data TEXT,
                    ai_labels TEXT
                )
            """)
            conn.commit()
            status_callback(f"Database created at {db_path}")
    except Exception as e:
        status_callback(f"Error creating database: {e}")

def insert_image_metadata(db_path, image_info, status_callback):
    """Insert image metadata into the database."""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO images (
                    file_path, date_taken, file_creation_date, camera_model,
                    shooting_mode, image_quality, metering_mode, af_mode,
                    exposure_compensation, white_balance, picture_style,
                    shutter_speed, aperture, focal_length, iso, gps_data,
                    ai_labels
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                image_info["relative_path"],
                image_info["date_taken"],
                image_info["file_creation_date"],
                image_info["camera_model"],
                image_info["shooting_mode"],
                image_info["image_quality"],
                image_info["metering_mode"],
                image_info["af_mode"],
                image_info["exposure_compensation"],
                image_info["white_balance"],
                image_info["picture_style"],
                image_info["shutter_speed"],
                image_info["aperture"],
                image_info["focal_length"],
                image_info["iso"],
                image_info["gps_data"],
                image_info.get("ai_labels", "")  # Ensure ai_labels is included
            ))
            conn.commit()
            status_callback(f"Inserted image metadata: {image_info['relative_path']}")
    except Exception as e:
        status_callback(f"Error inserting image metadata: {e}")

def init_module():
    """Initialize the database module (for compatibility)."""
    return init_database()