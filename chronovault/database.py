"""
ChronoVault database module.

Manages SQLite database operations for storing and retrieving image metadata
(e.g., file paths, dates, people, locations).

Author: chronomicron@gmail.com
Created: 2025-05-03
"""

import sqlite3
from pathlib import Path

def init_database():
    """Initialize the database module."""
    return "Database module initialized"

def init_folders(vault_dir, status_callback):
    """Create folder structure for database and image archive."""
    try:
        vault_path = Path(vault_dir)
        db_dir = vault_path / "Database"
        archive_dir = vault_path / "Archive"

        # Create Database folder
        db_dir.mkdir(parents=True, exist_ok=True)
        status_callback(f"Created folder: {db_dir}")

        # Create Archive folder
        archive_dir.mkdir(parents=True, exist_ok=True)
        status_callback(f"Created folder: {archive_dir}")

    except PermissionError as e:
        status_callback(f"Error: Permission denied creating folders: {e}")
    except OSError as e:
        status_callback(f"Error: Cannot create folders (disk full or other issue): {e}")

def create_database(db_path, status_callback):
    """Initialize SQLite database with image metadata table."""
    try:
        db_path = Path(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create images table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                date_taken TEXT
            )
        """)
        conn.commit()
        status_callback(f"Database initialized: {db_path}")

    except sqlite3.OperationalError as e:
        status_callback(f"Error: Cannot initialize database (disk full or other issue): {e}")
    except PermissionError as e:
        status_callback(f"Error: Permission denied writing to database: {e}")
    except Exception as e:
        status_callback(f"Error: Failed to initialize database: {e}")
    finally:
        if 'conn' in locals():
            conn.close()