"""
ChronoVault database module.

Manages SQLite database for storing image metadata with thread-safe insertions.

Author: chronomicron@gmail.com
Created: 2025-05-03
Version History:
    v1.0.0 (2025-05-03): Initial version with SQLite database setup.
    v1.0.1 (2025-05-03): Added metadata insertion function.
    v1.0.2 (2025-05-13): Added thread-safe queue for database insertions.
    v1.0.3 (2025-05-13): Added init_folders for vault directory setup.
    v1.0.4 (2025-05-13): Added create_database for UI compatibility.
    v1.0.5 (2025-05-16): Fixed db_worker to catch queue.Empty exception.
"""

import sqlite3
import logging
from pathlib import Path
from queue import Queue
import threading
import queue

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Thread-safe queue and database connection
insert_queue = Queue()
db_connection = None
db_thread = None
stop_event = threading.Event()

def init_database():
    """Initialize the database module."""
    return "Database module initialized"

def init_folders(vault_path, status_callback):
    """Initialize vault directory structure."""
    vault_path = Path(vault_path)
    archive_path = vault_path / "Archive"
    db_dir = vault_path / "Database"
    
    try:
        archive_path.mkdir(parents=True, exist_ok=True)
        db_dir.mkdir(parents=True, exist_ok=True)
        status_callback(f"Initialized vault folders: {archive_path}, {db_dir}")
        logging.info(f"Initialized vault folders: {archive_path}, {db_dir}")
    except Exception as e:
        status_callback(f"Error initializing vault folders: {e}")
        logging.error(f"Error initializing vault folders: {e}")
        raise

def setup_database(db_path, status_callback):
    """Set up the SQLite database and create tables."""
    db_path = Path(db_path)
    vault_path = db_path.parent.parent  # Database/ -> Vault/
    
    # Initialize folders
    init_folders(vault_path, status_callback)
    
    try:
        global db_connection
        db_connection = sqlite3.connect(db_path, check_same_thread=False)
        cursor = db_connection.cursor()
        
        # Create images table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE,
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
        db_connection.commit()
        status_callback(f"Database initialized at {db_path}")
        logging.info(f"Database initialized at {db_path}")
        
        # Start database worker thread
        start_db_thread()
    except Exception as e:
        status_callback(f"Error initializing database: {e}")
        logging.error(f"Error initializing database: {e}")
        raise

def create_database(db_path, status_callback):
    """Create the database by setting up the SQLite database and tables."""
    setup_database(db_path, status_callback)

def start_db_thread():
    """Start a thread to process database insertions from the queue."""
    global db_thread
    if db_thread is None or not db_thread.is_alive():
        db_thread = threading.Thread(target=db_worker, daemon=True)
        db_thread.start()

def db_worker():
    """Process insert requests from the queue."""
    while not stop_event.is_set():
        try:
            # Get item from queue with timeout to check stop_event
            image_info, db_path, status_callback = insert_queue.get(timeout=1.0)
            try:
                cursor = db_connection.cursor()
                cursor.execute("""
                    INSERT OR IGNORE INTO images (
                        file_path, date_taken, file_creation_date, camera_model,
                        shooting_mode, image_quality, metering_mode, af_mode,
                        exposure_compensation, white_balance, picture_style,
                        shutter_speed, aperture, focal_length, iso, gps_data, ai_labels
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
                    image_info["ai_labels"]
                ))
                db_connection.commit()
                status_callback(f"Inserted image metadata: {image_info['relative_path']}")
                logging.info(f"Inserted image metadata: {image_info['relative_path']}")
            except Exception as e:
                status_callback(f"Error inserting image metadata: {e}")
                logging.error(f"Error inserting image metadata: {e}")
            finally:
                insert_queue.task_done()
        except queue.Empty:
            continue

def enqueue_insert(db_path, image_info, status_callback):
    """Enqueue image metadata for database insertion."""
    try:
        insert_queue.put((image_info, db_path, status_callback))
    except Exception as e:
        status_callback(f"Error enqueuing image metadata: {e}")
        logging.error(f"Error enqueuing image metadata: {e}")

def close_database():
    """Close the database connection and stop the worker thread."""
    stop_event.set()
    if db_thread is not None:
        db_thread.join()
    if db_connection is not None:
        db_connection.close()
        logging.info("Database connection closed")

def insert_image_metadata(db_path, image_info, status_callback):
    """Legacy function for compatibility; use enqueue_insert instead."""
    enqueue_insert(db_path, image_info, status_callback)

def test_database_integrity(db_path, status_callback):
    """Test database integrity."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()[0]
        conn.close()
        if result == "ok":
            status_callback("Database integrity check passed")
            logging.info("Database integrity check passed")
        else:
            status_callback(f"Database integrity check failed: {result}")
            logging.error(f"Database integrity check failed: {result}")
    except Exception as e:
        status_callback(f"Error checking database integrity: {e}")
        logging.error(f"Error checking database integrity: {e}")