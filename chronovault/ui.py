"""
ChronoVault UI module.

Handles the PyQt-based graphical user interface for ChronoVault, including
window creation, buttons, and image display.

Author: chronomicron@gmail.com
Created: 2025-05-03
"""

from PyQt5.QtWidgets import (QMainWindow, QPushButton, QLineEdit, QVBoxLayout, QWidget, 
                            QFileDialog, QHBoxLayout, QLabel, QDialogButtonBox, 
                            QTextEdit, QFrame, QMessageBox)
from PyQt5.QtCore import Qt, QObject, pyqtSignal
from pathlib import Path
import chronovault.config as config
import chronovault.database as database
import chronovault.scanner as scanner
import chronovault.archiver as archiver

class StatusEmitter(QObject):
    """Emitter for thread-safe status updates."""
    status_updated = pyqtSignal(str)

def init_ui():
    """Initialize the UI module."""
    return "UI module initialized"

def create_main_window():
    """Create and configure the main PyQt window."""
    window = QMainWindow()
    window.setWindowTitle("ChronoVault")
    window.setGeometry(100, 100, 600, 400)
    return window

def setup_ui(window):
    """Set up the UI layout with widgets."""
    layout = QVBoxLayout()

    # Load config
    config_data = config.load_config()
    scan_dir = config_data.get("scan_dir", "")
    vault_dir = config_data.get("vault_dir", "")

    # Scan directory input
    scan_layout = QHBoxLayout()
    scan_label = QLabel("Scan Directory:")
    scan_input = QLineEdit()
    scan_input.setPlaceholderText("Select directory to scan")
    scan_input.setText(scan_dir)
    scan_button = QPushButton("Browse")
    scan_button.clicked.connect(lambda: browse_directory(scan_input, status_output, is_scan_dir=True))
    scan_layout.addWidget(scan_label)
    scan_layout.addWidget(scan_input)
    scan_layout.addWidget(scan_button)
    layout.addLayout(scan_layout)

    # Image vault directory input
    vault_layout = QHBoxLayout()
    vault_label = QLabel("Image Vault Directory:")
    vault_input = QLineEdit()
    vault_input.setPlaceholderText("Select directory for database and image archive")
    vault_input.setText(vault_dir)
    vault_button = QPushButton("Browse")
    vault_button.clicked.connect(lambda: browse_directory(vault_input, status_output, is_scan_dir=False))
    vault_layout.addWidget(vault_label)
    vault_layout.addWidget(vault_input)
    vault_layout.addWidget(vault_button)
    layout.addLayout(vault_layout)

    # Action buttons
    action_layout = QHBoxLayout()
    test_db_button = QPushButton("Test Database Integrity")
    test_db_button.clicked.connect(lambda: test_database_integrity(vault_input, status_output))
    start_scan_button = QPushButton("Start Scan")
    start_scan_button.clicked.connect(lambda: start_scan(scan_input, vault_input, status_output, status_emitter))
    action_layout.addWidget(test_db_button)
    action_layout.addWidget(start_scan_button)
    layout.addLayout(action_layout)

    # Status output area
    status_frame = QFrame()
    status_frame.setFrameShape(QFrame.StyledPanel)
    status_layout = QVBoxLayout()
    status_output = QTextEdit()
    status_output.setReadOnly(True)
    status_output.setFixedHeight(150)
    status_layout.addWidget(status_output)
    status_frame.setLayout(status_layout)
    layout.addWidget(status_frame)

    # Set up thread-safe status updates
    status_emitter = StatusEmitter()
    status_emitter.status_updated.connect(lambda msg: append_status(status_output, msg))

    # Central widget
    container = QWidget()
    container.setLayout(layout)
    window.setCentralWidget(container)

    return scan_input, vault_input, test_db_button, start_scan_button, status_output, status_emitter

def browse_directory(line_edit, status_output, is_scan_dir):
    """Open a directory selection dialog with a 'Select Current Folder' button."""
    dialog = QFileDialog(None, "Select Directory")
    dialog.setFileMode(QFileDialog.Directory)
    dialog.setOption(QFileDialog.ShowDirsOnly, True)

    # Add custom button to select current folder
    button_box = dialog.findChild(QDialogButtonBox)
    if button_box:
        select_current = button_box.addButton("Select Current Folder", QDialogButtonBox.AcceptRole)
        select_current.clicked.connect(dialog.accept)

    if dialog.exec_():
        selected_dir = dialog.selectedFiles()[0]
        if selected_dir:
            line_edit.setText(selected_dir)
            config_data = config.load_config()
            key = "scan_dir" if is_scan_dir else "vault_dir"
            config_data[key] = selected_dir
            config.save_config(config_data)
            append_status(status_output, f"{'Scan' if is_scan_dir else 'Vault'} directory updated: {selected_dir}")

def append_status(status_output, message):
    """Append a message to the status output area."""
    status_output.append(f"[INFO] {message}")

def test_database_integrity(vault_input, status_output):
    """Check if database and image library exist in the vault directory."""
    vault_path = vault_input.text()
    if not vault_path:
        append_status(status_output, "Error: No vault directory selected")
        return

    vault_dir = Path(vault_path)
    db_path = vault_dir / "Database" / "chronovault.db"
    archive_path = vault_dir / "Archive"

    # Check database
    if db_path.exists():
        append_status(status_output, "Database found: " + str(db_path))
    else:
        append_status(status_output, "Database not found: " + str(db_path))
        reply = QMessageBox.question(
            None,
            "Create Database",
            f"No database found at {db_path}. Create one?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            database.init_folders(vault_path, lambda msg: append_status(status_output, msg))
            database.create_database(db_path, lambda msg: append_status(status_output, msg))
        else:
            append_status(status_output, "Database creation cancelled")

    # Check image library
    if archive_path.exists():
        append_status(status_output, "Image library found: " + str(archive_path))
    else:
        append_status(status_output, "Image library not found: " + str(archive_path))

def start_scan(scan_input, vault_input, status_output, status_emitter):
    """Handle Start Scan button press."""
    append_status(status_output, "Start Scan initiated")

    # Validate vault directory and database
    vault_path = vault_input.text()
    if not vault_path:
        append_status(status_output, "Error: No vault directory selected")
        return
    vault_dir = Path(vault_path)
    db_path = vault_dir / "Database" / "chronovault.db"
    if not db_path.exists():
        append_status(status_output, "Error: No database found at " + str(db_path))
        reply = QMessageBox.question(
            None,
            "Create Database",
            f"No database found at {db_path}. Create one to proceed with scanning?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            database.init_folders(vault_path, lambda msg: append_status(status_output, msg))
            database.create_database(db_path, lambda msg: append_status(status_output, msg))
        else:
            append_status(status_output, "Error: Scan cancelled, database required")
            return

    # Save current paths to config
    config_data = config.load_config()
    config_data["scan_dir"] = scan_input.text()
    config_data["vault_dir"] = vault_input.text()
    config.save_config(config_data)
    append_status(status_output, "Scan and vault directories saved to config")

    # Start the scan
    scan_dir = scan_input.text()
    if not scan_dir:
        append_status(status_output, "Error: No scan directory selected")
        return
    scanner.scan_directory(scan_dir, vault_path, status_emitter.status_updated.emit)

    # Prompt for copying images
    reply = QMessageBox.question(
        None,
        "Copy Images",
        "Copy found images to vault archive?",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.Yes
    )
    if reply == QMessageBox.Yes:
        delete_originals = QMessageBox.question(
            None,
            "Delete Originals",
            "Delete original images after copying?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        ) == QMessageBox.Yes
        append_status(status_output, "Starting image copying")
        archiver.copy_images(vault_path, delete_originals, status_emitter.status_updated.emit)
        append_status(status_output, "Image copying completed")
    else:
        append_status(status_output, "Image copying skipped")
    
    append_status(status_output, "Scan completed")