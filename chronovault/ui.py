# ChronoVault - User Interface Module
# Description: This module contains all PyQt5-based GUI code for ChronoVault.
# It defines the main application window, layout (folder tree, thumbnail grid,
# metadata sidebar, filters), and event handlers. It imports and calls other
# modules (scanner, archiver, database, config, utils) to perform actions
# triggered by user interaction.
#
# The GUI follows an Adobe Bridge-inspired layout: left pane for folders,
# central thumbnail grid (chrono-aware), right metadata/details panel,
# bottom filters/search.
#
# Version History:
#   0.1.1 – Initial placeholder file with basic QMainWindow skeleton
#

import sys
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QSplitter,
    QWidget,
    QVBoxLayout,
    QLabel,
    QStatusBar,
    QMenuBar,
    QAction
)
from PyQt5.QtCore import Qt


class ChronoVaultWindow(QMainWindow):
    """Main application window for ChronoVault."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ChronoVault ⏳📸")
        self.resize(1200, 800)

        self._setup_ui()
        self._setup_menu()

    def _setup_ui(self):
        """Initialize the main layout with splitters."""
        # Central widget with horizontal splitter
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # Top-level horizontal splitter (left | center | right)
        h_splitter = QSplitter(Qt.Horizontal)

        # Left: Folder tree placeholder
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("Folders / Sources (TreeView placeholder)"))
        h_splitter.addWidget(left_panel)

        # Center: Thumbnail grid / content area
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.addWidget(QLabel("Thumbnail Grid / Timeline View (QGraphicsView or Grid placeholder)"))
        h_splitter.addWidget(center_panel)

        # Right: Metadata / details panel
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(QLabel("Metadata / EXIF / Labels (FormLayout or Tabs placeholder)"))
        h_splitter.addWidget(right_panel)

        main_layout.addWidget(h_splitter)

        # Status bar
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")

    def _setup_menu(self):
        """Set up basic menu bar."""
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")
        scan_action = QAction("&Scan Directory...", self)
        scan_action.triggered.connect(self.on_scan_triggered)
        file_menu.addAction(scan_action)

        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def on_scan_triggered(self):
        """Placeholder handler for Scan action."""
        self.statusBar().showMessage("Scan triggered (placeholder) – not implemented yet")


def run_gui():
    """Launch the ChronoVault GUI application."""
    app = QApplication(sys.argv)
    window = ChronoVaultWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    run_gui()