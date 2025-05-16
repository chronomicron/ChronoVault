"""
ChronoVault UI module.

Provides a PyQt-based GUI for managing image scanning, archiving, and database operations.

Author: chronomicron@gmail.com
Created: 2025-05-03
Version History:
    v1.0.0 (2025-05-03): Initial version with automated workflow.
    v1.0.1 (2025-05-16): Revamped UI with manual phase buttons and three-section layout.
    v1.0.2 (2025-05-16): Added shutil import for copy_images_to_archive.
    v1.0.3 (2025-05-16): Consolidated EXIF extraction and database insertion into copy_images_to_archive, removed update_database.
"""

import sys
import logging
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFileDialog, QTextEdit, QFrame, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from pathlib import Path
import chronovault.scanner as scanner
import chronovault.archiver as archiver
import chronovault.database as database
import json
import shutil
from datetime import datetime
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class StatusEmitter(QWidget):
    """Custom widget to emit status updates for thread-safe GUI updates."""
    status_updated = pyqtSignal(str)

    def __init__(self):
        super().__init__()

def init_ui():
    """Initialize the UI module."""
    return "UI module initialized"

def append_status(status_output, message):
    """Append a status message to the QTextEdit."""
    status_output.append(message)
    status_output.ensureCursorVisible()
    QApplication.processEvents()

def browse_directory(line_edit):
    """Open a file dialog to select a directory and update the QLineEdit."""
    directory = QFileDialog.getExistingDirectory(None, "Select Directory")
    if directory:
        line_edit.setText(directory)

def test_database_integrity(vault_input, status_output):
    """Test database existence and folder structure."""
    vault_path = vault_input.text().strip()
    if not vault_path:
        append_status(status_output, "Error: Vault directory not specified")
        return

    db_path = Path(vault_path) / "Database" / "chronovault.db"
    try:
        database.create_database(db_path, lambda msg: append_status(status_output, msg))
        database.test_database_integrity(db_path, lambda msg: append_status(status_output, msg))
    except Exception as e:
        append_status(status_output, f"Error testing database: {e}")
        logging.error(f"Error testing database: {e}")

def search_images(scan_input, vault_input, status_output):
    """Scan for images and write to scan_results.json."""
    scan_dir = scan_input.text().strip()
    vault_dir = vault_input.text().strip()
    if not scan_dir:
        append_status(status_output, "Error: Scan directory not specified")
        return
    if not vault_dir:
        append_status(status_output, "Error: Vault directory not specified")
        return

    try:
        scanner.scan_directory(scan_dir, vault_dir, lambda msg: append_status(status_output, msg))
    except Exception as e:
        append_status(status_output, f"Error scanning images: {e}")
        logging.error(f"Error scanning images: {e}")

def copy_images_to_archive(vault_input, status_output):
    """Copy images to archive and insert EXIF data into database."""
    vault_dir = vault_input.text().strip()
    if not vault_dir:
        append_status(status_output, "Error: Vault directory not specified")
        return

    temp_file = Path("scan_results.json")
    if not temp_file.exists():
        append_status(status_output, "Error: No scan results found")
        return

    try:
        with temp_file.open('r') as f:
            results = json.load(f)
        images = [item["original_path"] for item in results]
        scanned_count = len(images)
        append_status(status_output, f"Found {scanned_count} images in scan results")

        vault_path = Path(vault_dir)
        archive_path = vault_path / "Archive"
        db_path = vault_path / "Database" / "chronovault.db"
        copied_count = 0
        current_year = datetime.now().year
        min_year = 1970  # Unix epoch start

        for image_path in images:
            src_path = Path(image_path)
            if not src_path.exists():
                append_status(status_output, f"Skipping non-existent image: {src_path}")
                logging.warning(f"Skipping non-existent image: {src_path}")
                continue

            # Step 1: Read EXIF data
            try:
                date_taken, camera_model, resolution = archiver.extract_exif_data(src_path)
                exif_data = {
                    "camera_model": camera_model or "Unknown",
                    "image_quality": resolution or "Unknown",
                    "shooting_mode": "",
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
            except Exception as e:
                append_status(status_output, f"Error reading EXIF data for {src_path}: {e}")
                logging.error(f"Error reading EXIF data for {src_path}: {e}")
                exif_data = {
                    "camera_model": "Unknown",
                    "image_quality": "Unknown",
                    "shooting_mode": "",
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
                date_taken = None

            # Step 2: Determine date taken
            if date_taken:
                year = date_taken.year
                if year < min_year or year > current_year:
                    append_status(status_output, f"Unreasonable date {date_taken} for {src_path}, trying fallback")
                    logging.warning(f"Unreasonable date {date_taken} for {src_path}")
                    date_taken = None

            if not date_taken:
                # Fallback to file modification time
                try:
                    mtime = src_path.stat().st_mtime
                    date_taken = datetime.fromtimestamp(mtime)
                    year = date_taken.year
                    if year < min_year or year > current_year:
                        append_status(status_output, f"Unreasonable file date {date_taken} for {src_path}, using Unknown")
                        logging.warning(f"Unreasonable file date {date_taken} for {src_path}")
                        date_taken = None
                except Exception as e:
                    append_status(status_output, f"Error getting file date for {src_path}: {e}")
                    logging.error(f"Error getting file date for {src_path}: {e}")
                    date_taken = None

            # Step 3: Determine destination folder
            if date_taken:
                year, month, day = date_taken.strftime("%Y"), date_taken.strftime("%m"), date_taken.strftime("%d")
                dest_dir = archive_path / year / month / day
                creation_date = date_taken.strftime("%Y-%m-%d %H:%M:%S")
            else:
                dest_dir = archive_path / "Unknown"
                creation_date = "Unknown"

            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = archiver.get_unique_dest_path(dest_dir, src_path.name)

            # Step 4: Copy image
            try:
                shutil.copy2(src_path, dest_path)
                append_status(status_output, f"Copied image to {dest_path}")
                logging.info(f"Copied image to {dest_path}")
            except Exception as e:
                append_status(status_output, f"Error copying {src_path} to {dest_path}: {e}")
                logging.error(f"Error copying {src_path} to {dest_path}: {e}")
                continue  # Skip database insertion if copy fails

            # Step 5: Insert EXIF data into database
            try:
                image_info = {
                    "relative_path": str(dest_path.relative_to(vault_path)),
                    "date_taken": creation_date,
                    "file_creation_date": creation_date,
                    **exif_data
                }
                database.enqueue_insert(db_path, image_info, lambda msg: append_status(status_output, msg))
                copied_count += 1
            except Exception as e:
                append_status(status_output, f"Error inserting {dest_path} into database: {e}")
                logging.error(f"Error inserting {dest_path} into database: {e}")

        # Wait for database queue to drain
        database.insert_queue.join()
        append_status(status_output, f"Copied and stored {copied_count}/{scanned_count} images")
        if copied_count != scanned_count:
            append_status(status_output, f"Warning: Not all images processed ({copied_count}/{scanned_count})")
    except Exception as e:
        append_status(status_output, f"Error processing images: {e}")
        logging.error(f"Error processing images: {e}")

def delete_original_images(status_output):
    """Delete original images after user confirmation."""
    temp_file = Path("scan_results.json")
    if not temp_file.exists():
        append_status(status_output, "Error: No scan results found")
        return

    reply = QMessageBox.question(
        None, "Confirm Deletion",
        "Are you sure you want to delete the original images?",
        QMessageBox.Yes | QMessageBox.No, QMessageBox.No
    )
    if reply != QMessageBox.Yes:
        append_status(status_output, "Deletion cancelled by user")
        return

    try:
        with temp_file.open('r') as f:
            results = json.load(f)
        images = [item["original_path"] for item in results]
        deleted_count = 0

        for image_path in images:
            src_path = Path(image_path)
            if src_path.exists():
                try:
                    src_path.unlink()
                    append_status(status_output, f"Deleted original image: {src_path}")
                    deleted_count += 1
                except Exception as e:
                    append_status(status_output, f"Error deleting {src_path}: {e}")
            else:
                append_status(status_output, f"Skipping non-existent image: {src_path}")

        append_status(status_output, f"Deleted {deleted_count}/{len(images)} original images")
    except Exception as e:
        append_status(status_output, f"Error deleting original images: {e}")
        logging.error(f"Error deleting original images: {e}")

def create_main_window():
    """Create the main application window."""
    window = QMainWindow()
    window.setWindowTitle("ChronoVault")
    window.setGeometry(100, 100, 800, 600)
    return window

def setup_ui(window):
    """Set up the UI components."""
    central_widget = QWidget()
    window.setCentralWidget(central_widget)
    main_layout = QVBoxLayout(central_widget)

    # Directory Input Section
    dir_frame = QFrame()
    dir_frame.setFrameShape(QFrame.Box)
    dir_frame.setFrameShadow(QFrame.Raised)
    dir_layout = QVBoxLayout(dir_frame)

    # Scan Directory
    scan_layout = QHBoxLayout()
    scan_label = QLabel("Scan Directory:")
    scan_input = QLineEdit()
    scan_browse = QPushButton("Browse")
    scan_browse.clicked.connect(lambda: browse_directory(scan_input))
    scan_layout.addWidget(scan_label)
    scan_layout.addWidget(scan_input)
    scan_layout.addWidget(scan_browse)
    dir_layout.addLayout(scan_layout)

    # Vault Directory
    vault_layout = QHBoxLayout()
    vault_label = QLabel("Image Vault Directory:")
    vault_input = QLineEdit()
    vault_browse = QPushButton("Browse")
    vault_browse.clicked.connect(lambda: browse_directory(vault_input))
    vault_layout.addWidget(vault_label)
    vault_layout.addWidget(vault_input)
    vault_layout.addWidget(vault_browse)
    dir_layout.addLayout(vault_layout)

    main_layout.addWidget(dir_frame)

    # Action Buttons Section
    action_frame = QFrame()
    action_frame.setFrameShape(QFrame.Box)
    action_frame.setFrameShadow(QFrame.Raised)
    action_layout = QVBoxLayout(action_frame)

    test_db_button = QPushButton("Test Database")
    test_db_button.clicked.connect(lambda: test_database_integrity(vault_input, status_output))
    action_layout.addWidget(test_db_button)

    search_button = QPushButton("Search Images")
    search_button.clicked.connect(lambda: search_images(scan_input, vault_input, status_output))
    action_layout.addWidget(search_button)

    copy_button = QPushButton("Import Images into Archive")
    copy_button.clicked.connect(lambda: copy_images_to_archive(vault_input, status_output))
    action_layout.addWidget(copy_button)

    delete_button = QPushButton("Remove Images from Original Location")
    delete_button.clicked.connect(lambda: delete_original_images(status_output))
    action_layout.addWidget(delete_button)

    main_layout.addWidget(action_frame)

    # Status Output Section
    status_frame = QFrame()
    status_frame.setFrameShape(QFrame.Box)
    status_frame.setFrameShadow(QFrame.Raised)
    status_layout = QVBoxLayout(status_frame)

    status_output = QTextEdit()
    status_output.setReadOnly(True)
    status_layout.addWidget(status_output)

    main_layout.addWidget(status_frame)

    status_emitter = StatusEmitter()
    status_emitter.status_updated.connect(lambda msg: append_status(status_output, msg))

    return scan_input, vault_input, test_db_button, search_button, status_output, status_emitter

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = create_main_window()
    scan_input, vault_input, test_db_button, start_scan_button, status_output, status_emitter = setup_ui(window)
    window.show()
    sys.exit(app.exec_())