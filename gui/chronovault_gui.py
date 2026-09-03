"""
gui/chronovault_gui.py

ChronoVault GUI, v0.1 -- a simple window with buttons that launch the
existing terminal tools (Indexer, Importer) and stream their output live,
rather than replacing or duplicating any of their logic. Every tool is
launched exactly as chronovault.sh already launches it: same scripts,
same config.json files, same working directory (the project root) --
this is a convenience layer, not a second way of running ChronoVault
that could drift out of sync with the terminal-based one.

v0.1 scope, deliberately minimal: Index and Import only. No Stop button
yet (needs indexer.py's batch-commit fix first, so interrupting actually
preserves partial progress). No Verify Status yet (needs the shared
expected-keys list that will also drive the future --init flag, so the
two don't silently disagree about what "correct" looks like). Both are
natural next additions once this proves out.

Requirements:
    pip install PySide6 --break-system-packages

Usage:
    python3 chronovault.py          (from the project root -- recommended)
    python3 gui/chronovault_gui.py  (equivalent, works from any directory)
"""

import sys
import json
from pathlib import Path
from configparser import ConfigParser

try:
    from PySide6.QtCore import QProcess
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QLineEdit, QPushButton, QPlainTextEdit, QFileDialog,
        QMessageBox
    )
except ImportError:
    print("ERROR: PySide6 is not installed.")
    print("Install it with:  pip install PySide6 --break-system-packages")
    sys.exit(1)

# gui_data.py has no PySide6 dependency at all -- kept separate specifically
# so its logic is testable without Qt installed. See that file's docstring.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gui_data import (
    load_gui_config, update_archive_root_in_config, check_looks_like_archive,
    PROJECT_ROOT, GUI_SETTINGS_PATH
)


class ChronoVaultWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ChronoVault")
        self.resize(820, 600)

        self.gui_config = load_gui_config()
        self.gui_config_load_failed = self.gui_config is None
        if self.gui_config is None:
            # load_gui_config() already printed why to the terminal. The
            # visible dialog happens in main(), right after the window is
            # shown -- QMessageBox needs a window to exist first.
            self.gui_config = {"tools": {}}

        self.settings = ConfigParser()
        self.settings.read(GUI_SETTINGS_PATH)
        if not self.settings.has_section('paths'):
            self.settings.add_section('paths')

        self.process = None  # the currently-running QProcess, if any -- None means idle

        self._build_ui()
        self._restore_settings()

    def _build_ui(self):
        central = QWidget()
        layout = QVBoxLayout(central)

        # --- Source folder row ---
        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("Source folder:"))
        self.source_field = QLineEdit()
        self.source_field.setPlaceholderText("Folder to search and index (e.g. an old drive, USB key, phone backup)")
        source_row.addWidget(self.source_field)
        source_browse = QPushButton("Browse…")
        source_browse.clicked.connect(self._browse_source)
        source_row.addWidget(source_browse)
        layout.addLayout(source_row)

        # --- Archive folder row ---
        archive_row = QHBoxLayout()
        archive_row.addWidget(QLabel("Archive folder:"))
        self.archive_field = QLineEdit()
        self.archive_field.setPlaceholderText("Where ChronoVault builds the dated archive")
        archive_row.addWidget(self.archive_field)
        archive_browse = QPushButton("Browse…")
        archive_browse.clicked.connect(self._browse_archive)
        archive_row.addWidget(archive_browse)
        layout.addLayout(archive_row)

        # --- Action buttons ---
        action_row = QHBoxLayout()
        self.index_button = QPushButton("Index")
        self.index_button.clicked.connect(self._run_indexer)
        action_row.addWidget(self.index_button)

        self.import_button = QPushButton("Import")
        self.import_button.clicked.connect(self._run_importer)
        action_row.addWidget(self.import_button)

        action_row.addStretch(1)
        layout.addLayout(action_row)

        # --- Status line ---
        self.status_label = QLabel("Ready.")
        layout.addWidget(self.status_label)

        # --- Output panel: read-only, monospace, terminal-output feel ---
        self.output_panel = QPlainTextEdit()
        self.output_panel.setReadOnly(True)
        self.output_panel.setStyleSheet("font-family: monospace;")
        layout.addWidget(self.output_panel, stretch=1)

        self.setCentralWidget(central)

    def _restore_settings(self):
        """Pre-fill fields from the last session, if gui_settings.ini exists. Purely a convenience -- never required."""
        self.source_field.setText(self.settings['paths'].get('source_folder', ''))
        self.archive_field.setText(self.settings['paths'].get('archive_folder', ''))

    def _save_settings(self):
        self.settings['paths']['source_folder'] = self.source_field.text()
        self.settings['paths']['archive_folder'] = self.archive_field.text()
        with open(GUI_SETTINGS_PATH, 'w') as f:
            self.settings.write(f)

    def _browse_source(self):
        folder = QFileDialog.getExistingDirectory(self, "Select source folder to search")
        if folder:
            self.source_field.setText(folder)

    def _browse_archive(self):
        folder = QFileDialog.getExistingDirectory(self, "Select archive folder")
        if folder:
            self.archive_field.setText(folder)

    def _set_running_state(self, running, tool_name=""):
        """
        Disables BOTH action buttons while anything is running, not just
        the one that was clicked -- prevents two tools ever writing to
        the same database at once, which was an explicit design goal
        going into this GUI, not an incidental restriction.
        """
        self.index_button.setEnabled(not running)
        self.import_button.setEnabled(not running)
        self.status_label.setText(f"Running {tool_name}…" if running else "Ready.")

    def _append_output(self):
        if self.process is None:
            return
        data = bytes(self.process.readAllStandardOutput())
        text = data.decode('utf-8', errors='replace')
        if text:
            self.output_panel.appendPlainText(text.rstrip('\n'))

    def _process_finished(self, tool_name, exit_code, exit_status):
        """
        Distinguishes three real outcomes -- a clean finish, a nonzero
        exit (the tool ran but reported an error), and a crash -- rather
        than collapsing them all into one generic "done" message. This
        distinction becomes more important once a Stop button exists:
        the GUI will need to tell apart "the user stopped it" from "it
        crashed on its own" (e.g. a disconnected drive), and this is the
        one place that decision gets made.
        """
        if exit_status == QProcess.ExitStatus.CrashExit:
            self.output_panel.appendPlainText(f"\n--- {tool_name} was terminated or crashed. ---")
            self.status_label.setText(f"{tool_name} did not finish cleanly.")
        elif exit_code != 0:
            self.output_panel.appendPlainText(f"\n--- {tool_name} exited with an error (code {exit_code}). ---")
            self.status_label.setText(f"{tool_name} finished with an error.")
        else:
            self.output_panel.appendPlainText(f"\n--- {tool_name} finished. ---")
            self.status_label.setText(f"{tool_name} finished successfully.")

        self.process = None
        self._set_running_state(False)

    def _launch_tool(self, tool_name, script_relative_path, args):
        """
        Launch a tool as a subprocess, exactly as it would run from a
        terminal at the project root -- same script, same config.json,
        same working directory. Output streams live into the output
        panel as it's produced (via readyReadStandardOutput), rather
        than waiting for the tool to finish before showing anything.
        """
        if self.process is not None:
            QMessageBox.warning(self, "Busy", "Another tool is already running.")
            return

        full_script_path = PROJECT_ROOT / script_relative_path
        if not full_script_path.exists():
            QMessageBox.critical(
                self, "Tool not found",
                f"Could not find:\n{full_script_path}\n\n"
                f"Check gui_config.json's path for '{tool_name}'."
            )
            return

        self.output_panel.appendPlainText(f"\n$ python3 {script_relative_path} {' '.join(args)}")
        self._set_running_state(True, tool_name)

        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(PROJECT_ROOT))
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._append_output)
        self.process.finished.connect(
            lambda code, status: self._process_finished(tool_name, code, status)
        )
        self.process.start(sys.executable, [str(script_relative_path)] + args)

    def _run_indexer(self):
        if 'indexer' not in self.gui_config.get('tools', {}):
            QMessageBox.critical(self, "Not configured", "No 'indexer' entry found in gui_config.json.")
            return

        source = self.source_field.text().strip()
        if not source:
            QMessageBox.warning(self, "Missing source folder", "Choose a source folder to search first.")
            return
        if not Path(source).exists():
            QMessageBox.warning(self, "Folder not found", f"This folder doesn't exist:\n{source}")
            return

        args = []
        if check_looks_like_archive(source):
            proceed = QMessageBox.question(
                self, "This looks like a ChronoVault archive",
                f"'{source}' looks like it might already be a ChronoVault archive "
                f"(it contains archive_database.db).\n\n"
                f"Indexing an existing archive and importing it again would re-copy every "
                f"file into itself as duplicate copies -- almost certainly not what you "
                f"want, unless you're deliberately migrating or consolidating an archive.\n\n"
                f"Continue anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if proceed != QMessageBox.StandardButton.Yes:
                return
            args.append('--allow-archive-source')

        self._save_settings()
        tool = self.gui_config['tools']['indexer']
        self._launch_tool("Indexer", tool['script'], [tool['config'], source] + args)

    def _run_importer(self):
        if 'importer' not in self.gui_config.get('tools', {}):
            QMessageBox.critical(self, "Not configured", "No 'importer' entry found in gui_config.json.")
            return

        archive = self.archive_field.text().strip()
        if not archive:
            QMessageBox.warning(self, "Missing archive folder", "Choose an archive folder first.")
            return

        self._save_settings()
        tool = self.gui_config['tools']['importer']

        try:
            update_archive_root_in_config(tool['config'], archive)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            QMessageBox.critical(self, "Config error",
                                  f"Could not update {tool['config']}:\n{e}")
            return

        self._launch_tool("Importer", tool['script'], [tool['config']])

    def closeEvent(self, event):
        self._save_settings()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    window = ChronoVaultWindow()

    if window.gui_config_load_failed:
        QMessageBox.critical(
            window, "Missing configuration",
            "gui/gui_config.json was not found or could not be read.\n"
            "The Index and Import buttons won't work until it's restored."
        )

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
    