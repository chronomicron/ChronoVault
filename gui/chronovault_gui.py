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

try:
    from PySide6.QtCore import QProcess
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QLineEdit, QPushButton, QPlainTextEdit, QFileDialog,
        QMessageBox, QFrame
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
    load_settings, save_settings, check_and_log_startup, log_clean_shutdown,
    append_log_entry, get_log_entries, generate_diagnostic_report,
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

        self.settings = load_settings()
        self.previous_session_crashed = check_and_log_startup(self.settings)
        save_settings(self.settings)

        self.process = None  # the currently-running QProcess, if any -- None means idle

        self._build_ui()
        self._restore_settings()

    def _build_ui(self):
        central = QWidget()
        outer_layout = QHBoxLayout(central)

        # --- Left column: the main pipeline flow (unchanged from before) ---
        left_widget = QWidget()
        layout = QVBoxLayout(left_widget)
        layout.setContentsMargins(0, 0, 0, 0)

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

        outer_layout.addWidget(left_widget, 1)  # stretch factor 1 -- takes the remaining width

        # --- Right column: narrow panel of additional tool/test buttons.
        # Deliberately separate from the main Index/Import flow above --
        # this is where every other tool (Condition Database, Audit
        # Archive, Duplicate Finder today; test_functions scripts later)
        # gets a button as it's wired in, without reworking the main
        # flow's layout each time. Fixed narrow width, buttons stacked
        # top to bottom, extra vertical space absorbed by the stretch at
        # the end so buttons cluster together rather than spreading out.
        right_widget = QWidget()
        right_widget.setMaximumWidth(170)
        right_layout = QVBoxLayout(right_widget)

        right_layout.addWidget(QLabel("Tools"))

        self.condition_button = QPushButton("Condition Database")
        self.condition_button.clicked.connect(self._run_condition_database)
        right_layout.addWidget(self.condition_button)

        self.audit_button = QPushButton("Audit Archive")
        self.audit_button.clicked.connect(self._run_audit_archive)
        right_layout.addWidget(self.audit_button)

        self.duplicate_button = QPushButton("Duplicate Finder")
        self.duplicate_button.clicked.connect(self._run_duplicate_finder)
        right_layout.addWidget(self.duplicate_button)

        # Section separator -- groups form as more tools get wired in.
        # Above: the main pipeline tools (all act on located_files.db
        # and/or the archive). Below: diagnostics (read-only, no
        # pipeline data touched).
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        right_layout.addWidget(separator)

        right_layout.addWidget(QLabel("Diagnostics"))

        self.test_env_button = QPushButton("Test Environment")
        self.test_env_button.clicked.connect(self._run_test_env)
        right_layout.addWidget(self.test_env_button)

        right_layout.addStretch(1)  # pushes everything below this down to the bottom of the panel

        self.diagnostic_button = QPushButton("Generate Report")
        self.diagnostic_button.clicked.connect(self._run_diagnostic_report)
        right_layout.addWidget(self.diagnostic_button)

        outer_layout.addWidget(right_widget)

        self.setCentralWidget(central)

    def _restore_settings(self):
        """Pre-fill fields from the last session, if gui_settings.ini exists. Purely a convenience -- never required."""
        self.source_field.setText(self.settings['paths'].get('source_folder', ''))
        self.archive_field.setText(self.settings['paths'].get('archive_folder', ''))

    def _save_settings(self):
        self.settings['paths']['source_folder'] = self.source_field.text()
        self.settings['paths']['archive_folder'] = self.archive_field.text()
        save_settings(self.settings)

    def _log(self, description):
        """
        Records an event to the persistent rolling log in
        gui_settings.ini, saved to disk IMMEDIATELY -- not batched until
        the next natural save point -- so the entry survives even if
        something crashes right after it's recorded. This is exactly
        the data the Diagnostic Report button draws on to show what
        actually happened, not just current state.
        """
        append_log_entry(self.settings, description)
        save_settings(self.settings)

    def _browse_source(self):
        folder = QFileDialog.getExistingDirectory(self, "Select source folder to search")
        if folder:
            self.source_field.setText(folder)
            self._log(f"Source folder set to: {folder}")

    def _browse_archive(self):
        folder = QFileDialog.getExistingDirectory(self, "Select archive folder")
        if folder:
            self.archive_field.setText(folder)
            self._log(f"Archive folder set to: {folder}")

    def _set_running_state(self, running, tool_name=""):
        """
        Disables EVERY action button while anything is running, not just
        the one that was clicked -- prevents two tools ever writing to
        the same database at once, which was an explicit design goal
        going into this GUI, not an incidental restriction. Test
        Environment is included here too, even though it's read-only --
        it still launches through the same shared QProcess slot as
        everything else, so leaving it visually enabled while another
        tool runs would be misleading (clicking it would just trigger
        _launch_tool()'s "Another tool is already running" warning
        rather than doing anything useful). Generate Report is
        deliberately NOT included -- it runs synchronously in plain
        Python, never touches self.process, and is meant to work even
        while another tool is mid-run.
        """
        for button in (self.index_button, self.import_button, self.condition_button,
                       self.audit_button, self.duplicate_button, self.test_env_button):
            button.setEnabled(not running)
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
            self._log(f"{tool_name} crashed or was terminated")
        elif exit_code != 0:
            self.output_panel.appendPlainText(f"\n--- {tool_name} exited with an error (code {exit_code}). ---")
            self.status_label.setText(f"{tool_name} finished with an error.")
            self._log(f"{tool_name} exited with an error (code {exit_code})")
        else:
            self.output_panel.appendPlainText(f"\n--- {tool_name} finished. ---")
            self.status_label.setText(f"{tool_name} finished successfully.")
            self._log(f"{tool_name} finished successfully")

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
        self._log(f"{tool_name} launched: python3 {script_relative_path} {' '.join(args)}")
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

    def _run_condition_database(self):
        """
        Launched with its own config.json completely unchanged -- same
        as chronovault.sh's own Condition Database step. Unlike Importer,
        this tool has no archive_root concept at all (it operates on
        located_files.db directly), so there's nothing for the GUI to
        sync before running it.
        """
        if 'condition_database' not in self.gui_config.get('tools', {}):
            QMessageBox.critical(self, "Not configured", "No 'condition_database' entry found in gui_config.json.")
            return
        tool = self.gui_config['tools']['condition_database']
        self._launch_tool("Condition Database", tool['script'], [tool['config']])

    def _run_audit_archive(self):
        """
        Now syncs the Archive field before running -- reversed from an
        earlier version that deliberately left this unsynced. That
        turned out to be wrong in practice: Importer would succeed
        against a custom archive path while this tool silently checked
        the stale default instead, failing with "Archive root 'archive'
        does not exist" -- a correct error, but a confusing, avoidable
        one. Same requirement as Importer: needs a real archive path,
        since this tool has no meaningful way to run without one.
        """
        if 'audit_archive' not in self.gui_config.get('tools', {}):
            QMessageBox.critical(self, "Not configured", "No 'audit_archive' entry found in gui_config.json.")
            return

        archive = self.archive_field.text().strip()
        if not archive:
            QMessageBox.warning(self, "Missing archive folder", "Choose an archive folder first.")
            return

        tool = self.gui_config['tools']['audit_archive']
        try:
            update_archive_root_in_config(tool['config'], archive)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            QMessageBox.critical(self, "Config error", f"Could not update {tool['config']}:\n{e}")
            return

        self._launch_tool("Audit Archive", tool['script'], [tool['config']])

    def _run_duplicate_finder(self):
        """
        Also now syncs, same reversal and reasoning as Audit Archive
        above -- but the Archive field is NOT required here, unlike
        Audit Archive/Importer. Duplicate Finder is dual-mode: in
        'source' mode it doesn't need an archive_root at all, so forcing
        the field would incorrectly block a legitimate source-mode run.
        If the field is empty, this just launches with whatever mode and
        settings are already in the config file, same as chronovault.sh
        would. update_archive_root_in_config() is itself mode-aware, so
        even when the field IS filled in, a source-mode config is left
        alone rather than getting an unused archive_root written into it.
        """
        if 'duplicate_finder' not in self.gui_config.get('tools', {}):
            QMessageBox.critical(self, "Not configured", "No 'duplicate_finder' entry found in gui_config.json.")
            return

        tool = self.gui_config['tools']['duplicate_finder']
        archive = self.archive_field.text().strip()

        if archive:
            try:
                update_archive_root_in_config(tool['config'], archive)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                QMessageBox.critical(self, "Config error", f"Could not update {tool['config']}:\n{e}")
                return

        self._launch_tool("Duplicate Finder", tool['script'], [tool['config']])

    def _run_test_env(self):
        """
        No config file and no arguments at all -- test_env.py takes
        neither. It resolves every path it checks (its own project root,
        located_files.db, archive/) relative to its own script location,
        not the current working directory, so unlike several other
        tools here, there's no archive-path syncing concern at all.
        """
        if 'test_env' not in self.gui_config.get('tools', {}):
            QMessageBox.critical(self, "Not configured", "No 'test_env' entry found in gui_config.json.")
            return
        tool = self.gui_config['tools']['test_env']
        self._launch_tool("Test Environment", tool['script'], [])

    def _run_diagnostic_report(self):
        """
        Read-only, and deliberately NOT gated by _set_running_state --
        this should work even while another tool is mid-run (that's
        often exactly when you'd want it), and it never writes to
        anything the pipeline tools care about. Shows the report inline
        in the output panel (consistent with everything else appearing
        there) and also saves it to a file, since a file is easier to
        copy in full or attach than scrolling back through the panel.
        """
        self._log("Diagnostic Report generated")
        report = generate_diagnostic_report(
            self.source_field.text().strip(),
            self.archive_field.text().strip(),
            log_entries=get_log_entries(self.settings)
        )
        self.output_panel.appendPlainText("\n" + report)

        report_path = PROJECT_ROOT / "gui" / "diagnostic_report.txt"
        try:
            with open(report_path, 'w') as f:
                f.write(report)
            self.output_panel.appendPlainText(f"\n(Also saved to {report_path})")
        except OSError as e:
            self.output_panel.appendPlainText(f"\n(Could not save report to file: {e})")

    def closeEvent(self, event):
        log_clean_shutdown(self.settings)
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

    if window.previous_session_crashed:
        # Not a blocking dialog on purpose -- a startup popup for
        # something that may well have been an ordinary force-quit is
        # more annoying than helpful. A visible note in the same output
        # panel everything else appears in is enough; the full detail
        # (exactly what the last recorded event was) is one click away
        # via Generate Diagnostic Report.
        window.output_panel.appendPlainText(
            "Note: the previous session didn't shut down cleanly (no clean-exit record found). "
            "If something seems off, use 'Generate Diagnostic Report' on the right for details."
        )

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
    