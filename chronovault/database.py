# ChronoVault - Database Module
# Description: This module provides the SQLite database interface for ChronoVault.
# It manages the photos table (path, capture_date, file_hash, camera_model,
# gps_info, labels, vault_path, etc.), creates schema on first use, and offers
# methods for insert, query by date/range, tag filtering, and metadata retrieval.
#
# Intended to be used by archiver.py (after archiving), ui.py (for browsing),
# and eventually ai.py (to store/update labels).
#
# Version History:
#   0.1.1 – Initial placeholder file with basic connection and schema stub
#

import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Optional


class PhotoDB:
    """SQLite database handler for ChronoVault photos."""

    def __init__(self, db_path: str | Path = "chronovault.db"):
        self.db_path = Path(db_path)
        self.conn = None
        self.cursor = None
        self._connect()
        self._ensure_schema()

    def _connect(self):
        """Establish connection to SQLite database."""
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

    def _ensure_schema(self):
        """Create photos table if it doesn't exist."""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS photos (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                original_path   TEXT NOT NULL UNIQUE,
                vault_path      TEXT,
                capture_date    TEXT,               -- ISO format: YYYY-MM-DD HH:MM:SS
                file_hash       TEXT,               -- SHA256 or similar for deduplication
                camera_make     TEXT,
                camera_model    TEXT,
                gps_latitude    REAL,
                gps_longitude   REAL,
                labels          TEXT,               -- comma-separated or JSON
                file_size       INTEGER,
                width           INTEGER,
                height          INTEGER,
                added_at        TEXT DEFAULT CURRENT_TIMESTAMP,
                CHECK (original_path != '')
            )
        """)
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_capture_date ON photos(capture_date)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_labels ON photos(labels)")
        self.conn.commit()

    def insert_photo(self, data: Dict[str, Any]) -> int:
        """Insert a single photo record. Returns row id."""
        # Placeholder – real implementation will map dict keys to columns
        self.cursor.execute("""
            INSERT OR IGNORE INTO photos (
                original_path, capture_date, file_hash, camera_make, camera_model
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            data.get("original_path"),
            data.get("capture_date"),
            data.get("file_hash"),
            data.get("camera_make"),
            data.get("camera_model")
        ))
        self.conn.commit()
        return self.cursor.lastrowid

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()


# For quick testing / CLI usage
if __name__ == "__main__":
    db = PhotoDB("test_chronovault.db")
    print("Database initialized at:", db.db_path)
    db.close()