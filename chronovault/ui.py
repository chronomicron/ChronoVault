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
from PyQt5.QtCore import Qt
from pathlib import Path

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

    # Scan directory input
    scan_layout = QHBoxLayout()
    scan_label = QLabel("Scan Directory:")
    scan_input = QLineEdit()
    scan_input.setPlaceholderText("Select directory to scan")
    scan_button = QPushButton("Browse")
    scan_button.clicked.connect(lambda: browse_directory(scan_input))
    scan_layout.addWidget(scan_label)
    scan_layout.addWidget(scan_input)
    scan_layout.addWidget(scan_button)
    layout.addLayout(scan_layout)

    # Image vault directory input
    vault_layout = QHBoxLayout()
    vault_label = QLabel("Image Vault Directory:")
    vault_input = QLineEdit()
    vault_input.setPlaceholderText("Select directory for database and image archive")
    vault_button = QPushButton("Browse")
    vault_button.clicked.connect(lambda: browse_directory(vault_input))
    vault_layout.addWidget(vault_label)
    vault_layout.addWidget(vault_input)
    vault_layout.addWidget(vault_button)
    layout.addLayout(vault_layout)

    # Action buttons
    action_layout = QHBoxLayout()
    test_db_button = QPushButton("Test Database Integrity")
    test_db_button.clicked.connect(lambda: test_database_integrity(vault_input, status_output))
    start_scan_button = QPushButton("Start Scan")
    start_scan_button.clicked.connect(lambda: append_status(status_output, "Start Scan button pressed"))
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

    # Central widget
    container = QWidget()
    container.setLayout(layout)
    window.setCentralWidget(container)

    return scan_input, vault_input, test_db_button, start_scan_button, status_output

def browse_directory(line_edit):
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
            append_status(status_output, "Database creation requested (not implemented yet)")
            # TODO: Implement database creation in database.py
        else:
            append_status(status_output, "Database creation cancelled")

    # Check image library
    if archive_path.exists():
        append_status(status_output, "Image library found: " + str(archive_path))
    else:
        append_status(status_output, "Image library not found: " + str(archive_path))