"""
ChronoVault UI module.

Handles the PyQt-based graphical user interface for ChronoVault, including
window creation, buttons, and image display.

Author: chronomicron@gmail.com
Created: 2025-05-03
"""

from PyQt5.QtWidgets import QMainWindow, QPushButton, QLineEdit, QVBoxLayout, QWidget, QFileDialog, QHBoxLayout, QLabel, QDialogButtonBox

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

    # Central widget
    container = QWidget()
    container.setLayout(layout)
    window.setCentralWidget(container)

    return scan_input, vault_input

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