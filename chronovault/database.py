"""
ChronoVault database module.

Handles initialization and management of the SQLite database for storing
image metadata.

Author: chronomicron@gmail.com
Created: 2025-05-03
Version: 1.0.0
"""

import sqlite3
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def init_database():
    """Initialize the database module."""
    return "Database module initialized"

def init_folders(vault_path, status_callback):
    """Create necessary folders for database and archive."""
    vault_dir = Path(vault_path)
    db_dir = vault_dir / "Database"
    archive_dir = vault_dir / "Archive"

    try:
        db_dir.mkdir(parents=True, exist_ok=True)
        archive_dir.mkdir(parents=True, exist_ok=True)
        status_callback(f"Creating vault folders: {vault_path}")
        logging.info(f"Created vault folders: {vault_path}")
    except Exception as e:
        status_callback(f"Error: Failed to create vault folders: {e}")
        logging.error(f"Failed to create vault folders: {e}")
        raise

def create_database(db_path, status_callback):
    """Create the SQLite database with an images table."""
    try:
        db_path = Path(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create images table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                creation_date TEXT,
                camera_model TEXT,
                resolution TEXT
            )
        """)
        conn.commit()
        status_callback(f"Database created: {db_path}")
        logging.info(f"Database created: {db_path}")
    except sqlite3.Error as e:
        status_callback(f"Error: Failed to create database: {e}")
        logging.error(f"Failed to create database: {e}")
        raise
    finally:
        if conn:
            conn.close()

def insert_image(db_path, file_path, creation_date, camera_model, resolution, status_callback):
    """Insert image metadata into the database."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO images (file_path, creation_date, camera_model, resolution)
            VALUES (?, ?, ?, ?)
        """, (str(file_path), creation_date, camera_model, resolution))
        conn.commit()
        status_callback(f"Inserted image metadata: {file_path}")
        logging.info(f"Inserted image metadata: {file_path}")
    except sqlite3.Error as e:
        status_callback(f"Error: Failed to insert image metadata for {file_path}: {e}")
        logging.error(f"Failed to insert image metadata for {file_path}: {e}")
    finally:
        if conn:
            conn.close()