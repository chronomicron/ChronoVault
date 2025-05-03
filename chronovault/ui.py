"""
ChronoVault UI module.

Handles the PyQt-based graphical user interface for ChronoVault, including
window creation, buttons, and image display.

Author: [chronomicron@gmail.com]
Created: 2025-05-03
"""

from PyQt5.QtWidgets import QMainWindow, QPushButton, QLineEdit, QVBoxLayout, QWidget, QFileDialog, QHBoxLayout, QLabel

def init_ui():
    """Initialize the UI module."""
    return "UI module initialized"

def create_main_window():
    """Create and configure the main PyQt window."""
    window = QMainWindow()
    window.setWindowTitle("ChronoVault")
    window.setGeometry(100, 100, 600, 200)
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

    # Database location input
    db_layout = QHBoxLayout()
    db_label = QLabel("Database Location:")
    db_input = QLineEdit()
    db_input.setPlaceholderText("Select database file")
    db_button = QPushButton("Browse")
    db_button.clicked.connect(lambda: browse_file(db_input))
    db_layout.addWidget(db_label)
    db_layout.addWidget(db_input)
    db_layout.addWidget(db_button)
    layout.addLayout(db_layout)

    # Central widget
    container = QWidget()
    container.setLayout(layout)
    window.setCentralWidget(container)

    return scan_input, db_input

def browse_directory(line_edit):
    """Open a directory selection dialog and update the line edit."""
    directory = QFileDialog.getExistingDirectory(None, "Select Scan Directory")
    if directory:
        line_edit.setText(directory)

def browse_file(line_edit):
    """Open a file selection dialog and update the line edit."""
    file_path, _ = QFileDialog.getOpenFileName(None, "Select Database File", "", "SQLite Database (*.db);;All Files (*)")
    if file_path:
        line_edit.setText(file_path)