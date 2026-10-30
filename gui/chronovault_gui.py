"""ChronoVault's Qt workflow interface.

The GUI configures and launches the existing command-line tools. Pipeline
behavior stays in those tools; this module owns workflow presentation, current
path selections, and subprocess status/output.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

try:
    from PySide6.QtCore import QProcess, Qt
    from PySide6.QtGui import QPalette
    from PySide6.QtWidgets import (
        QApplication, QCheckBox, QFileDialog, QFrame, QGridLayout, QGroupBox,
        QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
        QPlainTextEdit, QPushButton, QSpinBox,
        QTabWidget, QVBoxLayout, QWidget,
    )
except ImportError:
    print("ERROR: PySide6 is not installed.")
    print("Install it with:  pip install PySide6 --break-system-packages")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gui_data import (
    PROJECT_ROOT, GUI_RUNTIME_PATH, append_log_entry, check_and_log_startup,
    check_archive_destination, check_looks_like_archive,
    generate_diagnostic_report, get_log_entries,
    load_gui_config, load_gui_runtime, load_settings, save_gui_runtime,
    save_settings, update_gui_runtime_paths, update_values_in_config,
)


MEDIA_TYPES = {
    "Photos": ("jpg", "jpeg", "bmp", "tif", "tiff", "png", "gif", "webp", "thm", "raw", "cr2", "arw"),
    "Videos": ("mp4", "mov", "avi", "mkv", "mpeg", "mpg", "3gp", "mts", "m2ts"),
    "Audio": ("mp3", "m4a", "wav", "flac", "ogg", "aac", "wma"),
}
IMAGE_EXTENSIONS = set(MEDIA_TYPES["Photos"])


class ChronoVaultWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ChronoVault — Archive workflow")
        self.resize(1120, 900)
        self.gui_config = load_gui_config() or {"tools": {}}
        self.gui_config_load_failed = not bool(self.gui_config.get("tools"))
        self.runtime_config = load_gui_runtime()
        save_gui_runtime(self.runtime_config)
        self.settings = load_settings()
        self.previous_session_crashed = check_and_log_startup(self.settings)
        save_settings(self.settings)
        self.process = None
        self.process_queue = []
        self.active_tool_name = ""
        self._stdout_event_buffer = ""
        self._build_ui()
        self._restore_settings()
        self._connect_setting_signals()
        self._save_settings()

    def _build_ui(self):
        checkmark_path = (Path(__file__).resolve().parent / "checkbox-check.svg").as_posix()
        self.setStyleSheet("""
            QMainWindow, QWidget#root, QWidget#workflowPage, QWidget#reviewPage,
            QWidget#settingsPage, QWidget#settingsSubpage { background: #f3f6fb; color: #202b3b; }
            QWidget { color: #202b3b; }
            QLabel { color: #202b3b; background: transparent; }
            QLabel#muted, QLabel#summary { color: #526176; }
            QLabel#appMark { background: #e7efff; color: #315eae; border-radius: 8px; padding: 5px 9px; font-weight: 700; }
            QLabel#statusPill { background: #e4f6ec; color: #236b4a; border: 1px solid #bfdfce; border-radius: 10px; padding: 5px 10px; }
            QGroupBox { background: #ffffff; color: #202b3b; border: 1px solid #d8e0ec; border-radius: 9px; margin-top: 12px; padding: 10px; font-weight: 600; }
            QGroupBox::title { color: #344257; subcontrol-origin: margin; left: 11px; padding: 0 5px; }
            QLineEdit, QSpinBox { background: #ffffff; color: #202b3b; selection-background-color: #315eae; selection-color: #ffffff; border: 1px solid #b9c6d8; border-radius: 5px; padding: 6px; }
            QLineEdit::placeholder { color: #68778c; }
            QCheckBox { color: #263449; spacing: 7px; background: transparent; }
            QCheckBox::indicator { width: 15px; height: 15px; border: 1px solid #7889a0; border-radius: 3px; background: #ffffff; }
            QCheckBox::indicator:checked { background: #315eae; border-color: #315eae; image: url("__CHECKMARK__"); }
            QPushButton { background: #ffffff; color: #263449; border: 1px solid #bfcbda; border-radius: 6px; padding: 7px 11px; }
            QPushButton:hover { background: #edf2f8; color: #172338; border-color: #8798ad; }
            QPushButton:disabled { background: #e9edf2; color: #536176; border-color: #c5ced9; }
            QPushButton#primaryIndex { background: #315eae; color: #ffffff; border-color: #315eae; font-weight: 600; }
            QPushButton#primaryPrepare { background: #7355b8; color: #ffffff; border-color: #7355b8; font-weight: 600; }
            QPushButton#primaryImport { background: #168b9a; color: #ffffff; border-color: #168b9a; font-weight: 600; }
            QPushButton#primaryVerify { background: #a85d14; color: #ffffff; border-color: #a85d14; font-weight: 600; }
            QPushButton#linkButton { color: #315eae; background: transparent; border-color: transparent; }
            QTabWidget::pane { background: #f3f6fb; border: 1px solid #d8e0ec; border-radius: 8px; top: -1px; }
            QTabBar::tab { background: #e9eef5; color: #48576c; border: 1px solid #d8e0ec; padding: 8px 15px; margin-right: 4px; border-top-left-radius: 6px; border-top-right-radius: 6px; }
            QTabBar::tab:selected { background: #ffffff; color: #202b3b; font-weight: 600; border-bottom-color: #ffffff; }
            QPlainTextEdit { background: #17232d; color: #e8eef3; selection-background-color: #315eae; selection-color: #ffffff; border: 1px solid #263846; border-radius: 7px; padding: 8px; font-family: monospace; }
            QToolTip { background: #202b3b; color: #ffffff; border: 1px solid #526176; padding: 4px; }
            QFrame#workspaceTile { background: #ffffff; border: 1px solid #d8e0ec; border-radius: 8px; }
            QFrame#stageIndex { background: #f5f8ff; border: 1px solid #d2def4; border-top: 4px solid #315eae; border-radius: 9px; }
            QFrame#stagePrepare { background: #faf7ff; border: 1px solid #e0d6f2; border-top: 4px solid #7355b8; border-radius: 9px; }
            QFrame#stageImport { background: #f2fbfc; border: 1px solid #c9e8eb; border-top: 4px solid #168b9a; border-radius: 9px; }
            QFrame#stageVerify { background: #fff9f1; border: 1px solid #efddc8; border-top: 4px solid #b66a1b; border-radius: 9px; }
            QFrame#pathGuidance { background: #fff4dc; color: #714b0f; border: 1px solid #ead29c; border-radius: 8px; }
            QLabel#warningText { color: #714b0f; }
        """.replace("__CHECKMARK__", checkmark_path))
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, self._qcolor("#f3f6fb"))
        palette.setColor(QPalette.ColorRole.WindowText, self._qcolor("#202b3b"))
        palette.setColor(QPalette.ColorRole.Base, self._qcolor("#ffffff"))
        palette.setColor(QPalette.ColorRole.AlternateBase, self._qcolor("#edf1f8"))
        palette.setColor(QPalette.ColorRole.Text, self._qcolor("#202b3b"))
        palette.setColor(QPalette.ColorRole.Button, self._qcolor("#ffffff"))
        palette.setColor(QPalette.ColorRole.ButtonText, self._qcolor("#263449"))
        palette.setColor(QPalette.ColorRole.Highlight, self._qcolor("#315eae"))
        palette.setColor(QPalette.ColorRole.HighlightedText, self._qcolor("#ffffff"))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, self._qcolor("#526176"))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, self._qcolor("#526176"))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, self._qcolor("#536176"))
        palette.setColor(QPalette.ColorRole.PlaceholderText, self._qcolor("#68778c"))
        self.setPalette(palette)
        QApplication.instance().setPalette(palette)

        root = QWidget()
        root.setObjectName("root")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(20, 14, 20, 14)
        outer.setSpacing(10)
        topbar = QHBoxLayout()
        mark = QLabel("CV")
        mark.setObjectName("appMark")
        brand = QLabel("ChronoVault")
        brand.setStyleSheet("font-size: 18px; font-weight: 700;")
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusPill")
        topbar.addWidget(mark)
        topbar.addWidget(brand)
        topbar.addStretch(1)
        self.stop_condition_button = QPushButton("Stop conditioning")
        self.stop_condition_button.setVisible(False)
        self.stop_condition_button.setEnabled(False)
        self.stop_condition_button.clicked.connect(self._request_condition_stop)
        topbar.addWidget(self.stop_condition_button)
        topbar.addWidget(self.status_label)
        outer.addLayout(topbar)

        self.main_tabs = QTabWidget()
        self.main_tabs.addTab(self._build_workflow_view(), "Workflow")
        self.main_tabs.addTab(self._build_review_view(), "Review")
        self.main_tabs.addTab(self._build_settings_view(), "Settings")
        outer.addWidget(self.main_tabs, 3)

        self.output_panel = QPlainTextEdit()
        self.output_panel.setReadOnly(True)
        self.output_panel.setPlaceholderText("Tool output will appear here.")
        self.output_panel.setMinimumHeight(190)
        outer.addWidget(self.output_panel, 2)
        self.setCentralWidget(root)

    @staticmethod
    def _qcolor(value):
        from PySide6.QtGui import QColor
        return QColor(value)

    def _build_workflow_view(self):
        page = QWidget()
        page.setObjectName("workflowPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(9)
        intro = QHBoxLayout()
        titles = QVBoxLayout()
        title = QLabel("Archive workflow")
        title.setStyleSheet("font-size: 20px; font-weight: 650;")
        subtitle = QLabel("Add a source drive to your ChronoVault archive.")
        subtitle.setObjectName("muted")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        intro.addLayout(titles)
        intro.addStretch(1)
        self.workflow_report_button = QPushButton("Run report")
        self.workflow_report_button.clicked.connect(self._run_diagnostic_report)
        intro.addWidget(self.workflow_report_button)
        layout.addLayout(intro)

        self.workspace_group = QWidget()
        paths = QHBoxLayout(self.workspace_group)
        paths.setContentsMargins(0, 0, 0, 0)
        paths.setSpacing(9)
        self.source_path_summary, source_tile = self._path_tile("Source drive", self._browse_source)
        self.archive_path_summary, archive_tile = self._path_tile("Archive destination", self._browse_archive)
        self.database_path_summary, database_tile = self._path_tile("Inventory database", self._browse_database)
        paths.addWidget(source_tile, 1)
        paths.addWidget(archive_tile, 1)
        paths.addWidget(database_tile, 1)
        layout.addWidget(self.workspace_group)

        self.path_guidance = QFrame()
        self.path_guidance.setObjectName("pathGuidance")
        guidance = QHBoxLayout(self.path_guidance)
        guidance.setContentsMargins(10, 6, 10, 6)
        self.path_guidance_label = QLabel()
        self.path_guidance_label.setObjectName("warningText")
        self.path_guidance_label.setWordWrap(True)
        guidance.addWidget(self.path_guidance_label, 1)
        self.guidance_source_button = QPushButton("Choose Source…")
        self.guidance_source_button.clicked.connect(self._browse_source)
        self.guidance_archive_button = QPushButton("Choose Archive…")
        self.guidance_archive_button.clicked.connect(self._browse_archive)
        guidance.addWidget(self.guidance_source_button)
        guidance.addWidget(self.guidance_archive_button)
        layout.addWidget(self.path_guidance)

        sequence = QLabel("1  Index source     ─────     2  Prepare inventory     ─────     3  Import selected files     ─────     4  Verify archive")
        sequence.setObjectName("muted")
        sequence.setStyleSheet("font-weight: 600; padding: 2px;")
        layout.addWidget(sequence)

        stages = QGridLayout()
        stages.setHorizontalSpacing(10)
        stages.setVerticalSpacing(10)
        stages.setColumnStretch(0, 1)
        stages.setColumnStretch(1, 1)
        self.index_group, self.index_summary = self._stage_card(
            "01", "Index source", "Record paths and file details from Source.",
            "Selected types: updating", "Index source", self._run_indexer,
            "Settings", lambda: self._open_stage_settings(1), "stageIndex", "primaryIndex")
        self.prepare_group, self.prepare_summary = self._stage_card(
            "02", "Prepare inventory", "Classify images, hash files, and analyze dates.",
            "Classify: on · OCR: off", "Prepare inventory", self._run_prepare,
            "Options", lambda: self._open_stage_settings(2), "stagePrepare", "primaryPrepare")
        self.import_group, self.import_summary = self._stage_card(
            "03", "Import selected files", "Copy selected inventory files into Archive.",
            "Selected types: updating", "Import selected files", self._run_importer,
            "Settings", lambda: self._open_stage_settings(3), "stageImport", "primaryImport")
        self.verify_group, self.verify_summary = self._stage_card(
            "04", "Verify archive", "Compare archive files with its database.",
            "Report only · no files moved", "Run archive audit", self._run_audit_archive,
            "Archive settings", lambda: self._open_stage_settings(0), "stageVerify", "primaryVerify")
        stages.addWidget(self.index_group, 0, 0)
        stages.addWidget(self.prepare_group, 0, 1)
        stages.addWidget(self.import_group, 1, 0)
        stages.addWidget(self.verify_group, 1, 1)
        layout.addLayout(stages)

        callout = QLabel("Your source files stay where they are. Import copies selected files into the archive.")
        callout.setStyleSheet("background: #fff4dc; color: #714b0f; border-radius: 7px; padding: 8px 10px;")
        layout.addWidget(callout)
        return page

    def _path_tile(self, heading, callback):
        tile = QFrame()
        tile.setObjectName("workspaceTile")
        layout = QVBoxLayout(tile)
        layout.setContentsMargins(10, 6, 10, 6)
        row = QHBoxLayout()
        label = QLabel(heading)
        label.setStyleSheet("font-weight: 650;")
        button = QPushButton("Change")
        button.setObjectName("linkButton")
        button.clicked.connect(callback)
        row.addWidget(label)
        row.addStretch(1)
        row.addWidget(button)
        self.path_values = getattr(self, "path_values", [])
        value = QLabel("")
        value.setObjectName("muted")
        value.setWordWrap(True)
        value.setTextInteractionFlags(value.textInteractionFlags() | Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addLayout(row)
        layout.addWidget(value)
        self.path_values.append(value)
        return value, tile

    def _stage_card(self, number, title, description, summary, run_text, run_callback,
                    settings_text, settings_callback, frame_name, button_name):
        card = QFrame()
        card.setObjectName(frame_name)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 7, 12, 7)
        layout.setSpacing(3)
        heading = QHBoxLayout()
        number_label = QLabel(number)
        number_label.setStyleSheet("font-size: 12px; font-weight: 700;")
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 15px; font-weight: 650;")
        heading.addWidget(number_label)
        heading.addWidget(title_label)
        heading.addStretch(1)
        layout.addLayout(heading)
        description_label = QLabel(description)
        description_label.setObjectName("muted")
        description_label.setWordWrap(True)
        layout.addWidget(description_label)
        summary_label = QLabel(summary)
        summary_label.setObjectName("summary")
        summary_label.setWordWrap(True)
        layout.addWidget(summary_label)
        actions = QHBoxLayout()
        run_button = QPushButton(run_text)
        run_button.setObjectName(button_name)
        run_button.clicked.connect(run_callback)
        settings_button = QPushButton(settings_text)
        settings_button.setObjectName("linkButton")
        settings_button.clicked.connect(settings_callback)
        actions.addWidget(run_button)
        actions.addWidget(settings_button)
        actions.addStretch(1)
        layout.addLayout(actions)
        return card, summary_label

    def _build_review_view(self):
        page = QWidget()
        page.setObjectName("reviewPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 15, 18, 15)
        layout.setSpacing(10)
        title = QLabel("After import")
        title.setStyleSheet("font-size: 19px; font-weight: 650;")
        layout.addWidget(title)
        note = QLabel("Review and analysis tools keep their own safety behavior. They do not delete or choose files.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        actions = QHBoxLayout()
        self.duplicate_button = QPushButton("Find duplicate groups")
        self.duplicate_button.clicked.connect(self._run_duplicate_finder)
        self.review_button = QPushButton("Review uncertain dates")
        self.review_button.clicked.connect(self._run_review_data)
        actions.addWidget(self.duplicate_button)
        actions.addWidget(self.review_button)
        actions.addStretch(1)
        layout.addLayout(actions)
        details = QLabel("Duplicate Finder reports matching hashes and may cache hashes in the archive database. Review lists uncertain-date rows through the existing read-only diagnostic.")
        details.setObjectName("muted")
        details.setWordWrap(True)
        layout.addWidget(details)
        report_row = QHBoxLayout()
        self.test_env_button = QPushButton("Check environment")
        self.test_env_button.clicked.connect(self._run_test_env)
        self.diagnostic_button = QPushButton("Generate diagnostic report")
        self.diagnostic_button.clicked.connect(self._run_diagnostic_report)
        report_row.addWidget(self.test_env_button)
        report_row.addWidget(self.diagnostic_button)
        report_row.addStretch(1)
        layout.addLayout(report_row)
        layout.addStretch(1)
        return page

    def _build_settings_view(self):
        page = QWidget()
        page.setObjectName("settingsPage")
        outer = QVBoxLayout(page)
        outer.setContentsMargins(12, 12, 12, 12)
        self.settings_tabs = QTabWidget()
        outer.addWidget(self.settings_tabs)
        self._build_workspace_settings()
        self._build_index_settings()
        self._build_prepare_settings()
        self._build_import_settings()
        return page

    def _build_workspace_settings(self):
        page = QWidget()
        page.setObjectName("settingsSubpage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        self.workspace_settings_group = QGroupBox("Workspace locations")
        grid = QGridLayout(self.workspace_settings_group)
        grid.setColumnStretch(1, 1)
        self.source_field = QLineEdit()
        self.source_field.setPlaceholderText("Drive or folder to scan")
        self.source_field.setToolTip("Indexer scans this drive or folder. Original source files are not moved or deleted.")
        self.archive_field = QLineEdit()
        self.archive_field.setPlaceholderText("Folder where imported files are stored")
        self.archive_field.setToolTip("Future imports use this archive folder. Selecting a different folder does not move an existing archive.")
        self.database_field = QLineEdit()
        self.database_field.setPlaceholderText("Located-files inventory database")
        self.database_field.setToolTip("Selecting another path does not move an existing database.")
        self.source_field.editingFinished.connect(self._path_changed)
        self.archive_field.editingFinished.connect(self._path_changed)
        self.database_field.editingFinished.connect(self._database_path_changed)
        for row, (label, field, callback) in enumerate((
            ("Source folder", self.source_field, self._browse_source),
            ("Archive destination", self.archive_field, self._browse_archive),
            ("Inventory database", self.database_field, self._browse_database),
        )):
            grid.addWidget(QLabel(label), row, 0)
            grid.addWidget(field, row, 1)
            choose = QPushButton("Choose…")
            choose.clicked.connect(callback)
            grid.addWidget(choose, row, 2)
        help_text = QLabel("Source files are read and copied. Changing Archive selects a destination; it does not relocate existing media.")
        help_text.setObjectName("muted")
        help_text.setWordWrap(True)
        layout.addWidget(self.workspace_settings_group)
        layout.addWidget(help_text)
        layout.addStretch(1)
        self.settings_tabs.addTab(page, "Workspace")

    def _build_index_settings(self):
        page = QWidget()
        page.setObjectName("settingsSubpage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        self.index_type_group = self._extension_controls(layout, "index")
        self.index_other_extensions = QLineEdit()
        self.index_other_extensions.setPlaceholderText("Additional extensions, comma separated (example: heic, pdf)")
        layout.addWidget(self.index_other_extensions)
        self.index_archives_check = QCheckBox("List matching files inside ZIP/TAR/ISO archives")
        layout.addWidget(self.index_archives_check)
        note = QLabel("Indexer records locations and metadata. Listing archive contents does not extract files.")
        note.setObjectName("muted")
        layout.addWidget(note)
        layout.addStretch(1)
        self.settings_tabs.addTab(page, "Index")

    def _build_prepare_settings(self):
        page = QWidget()
        page.setObjectName("settingsSubpage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        self.prepare_settings_group = QGroupBox("Preparation choices")
        choices = QVBoxLayout(self.prepare_settings_group)
        self.classify_check = QCheckBox("Classify supported images before conditioning")
        self.classify_check.setChecked(True)
        self.ocr_check = QCheckBox("Try OCR when image date signals are missing")
        choices.addWidget(self.classify_check)
        choices.addWidget(self.ocr_check)
        note = QLabel("Condition Database hashes and analyzes every eligible inventory row. It does not filter by file type. OCR may take longer and requires its optional dependencies.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(self.prepare_settings_group)
        layout.addWidget(note)
        layout.addStretch(1)
        self.settings_tabs.addTab(page, "Prepare")

    def _build_import_settings(self):
        page = QWidget()
        page.setObjectName("settingsSubpage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        self.import_type_group = self._extension_controls(layout, "import")
        self.import_other_extensions = QLineEdit()
        self.import_other_extensions.setPlaceholderText("Additional extensions, comma separated")
        layout.addWidget(self.import_other_extensions)
        self.import_advanced = QGroupBox("Import filters")
        filters = QGridLayout(self.import_advanced)
        self.min_size = QSpinBox()
        self.min_size.setRange(0, 2_000_000_000)
        self.min_size.setSuffix(" bytes minimum")
        self.max_size = QSpinBox()
        self.max_size.setRange(0, 2_000_000_000)
        self.max_size.setSpecialValueText("No maximum")
        self.max_size.setSuffix(" bytes maximum")
        self.require_exif_check = QCheckBox("Require EXIF data")
        self.exclude_thumbnails_check = QCheckBox("Skip thumbnail files")
        self.exclude_thumbnails_check.setChecked(True)
        self.excludes_field = QLineEdit()
        self.excludes_field.setPlaceholderText("Excluded path fragments, comma separated")
        filters.addWidget(self.min_size, 0, 0)
        filters.addWidget(self.max_size, 0, 1)
        filters.addWidget(self.require_exif_check, 1, 0)
        filters.addWidget(self.exclude_thumbnails_check, 1, 1)
        filters.addWidget(QLabel("Exclude paths"), 2, 0)
        filters.addWidget(self.excludes_field, 2, 1)
        layout.addWidget(self.import_advanced)
        layout.addStretch(1)
        self.settings_tabs.addTab(page, "Import")

    def _open_stage_settings(self, index):
        self.main_tabs.setCurrentIndex(2)
        self.settings_tabs.setCurrentIndex(index)

    def _connect_setting_signals(self):
        for checkbox in (*self.index_extension_checks.values(), *self.import_extension_checks.values(),
                          self.index_archives_check, self.classify_check, self.ocr_check,
                          self.require_exif_check, self.exclude_thumbnails_check):
            checkbox.toggled.connect(self._save_settings)
        self.min_size.valueChanged.connect(self._save_settings)
        self.max_size.valueChanged.connect(self._save_settings)
        self.excludes_field.editingFinished.connect(self._save_settings)
        self.index_other_extensions.editingFinished.connect(self._save_settings)
        self.import_other_extensions.editingFinished.connect(self._save_settings)

    @staticmethod
    def _muted(text):
        label = QLabel(text)
        label.setObjectName("muted")
        label.setWordWrap(True)
        return label

    def _extension_controls(self, parent_layout, kind):
        group = QGroupBox("File types and extensions")
        grid = QGridLayout(group)
        controls = {}
        row = 0
        for category, extensions in MEDIA_TYPES.items():
            grid.addWidget(QLabel(category), row, 0, 1, 4)
            row += 1
            for index, extension in enumerate(extensions):
                check = QCheckBox(f".{extension}")
                controls[extension] = check
                grid.addWidget(check, row + index // 4, index % 4)
            row += (len(extensions) + 3) // 4
        parent_layout.addWidget(group)
        setattr(self, f"{kind}_extension_checks", controls)
        return group

    def _extension_default_checks(self):
        indexer = self.runtime_config["tools"]["indexer"]
        importer = self.runtime_config["tools"].get("importer", {})
        for extension, checkbox in self.index_extension_checks.items():
            checkbox.setChecked(extension in {str(e).lower().lstrip(".") for e in indexer.get("extensions", [])})
        for extension, checkbox in self.import_extension_checks.items():
            checkbox.setChecked(extension in {str(e).lower().lstrip(".") for e in importer.get("extensions_to_copy", [])})
        known = set(self.index_extension_checks)
        self.index_other_extensions.setText(", ".join(str(e).lower().lstrip(".") for e in indexer.get("extensions", []) if str(e).lower().lstrip(".") not in known))
        known = set(self.import_extension_checks)
        self.import_other_extensions.setText(", ".join(str(e).lower().lstrip(".") for e in importer.get("extensions_to_copy", []) if str(e).lower().lstrip(".") not in known))

    def _restore_settings(self):
        self._extension_default_checks()
        gui = self.runtime_config["gui"]
        self.source_field.setText(gui.get("source_folder", ""))
        self.archive_field.setText(gui.get("archive_folder", ""))
        self.classify_check.setChecked(bool(gui.get("prepare_classify_images", True)))
        self.ocr_check.setChecked(bool(gui.get("prepare_try_ocr", False)))
        self.database_field.setText(self.runtime_config["tools"]["indexer"].get("database_path", "located_files.db"))
        indexer = self.runtime_config["tools"]["indexer"]
        importer = self.runtime_config["tools"].get("importer", {})
        self.index_archives_check.setChecked(bool(indexer.get("look_inside_archives", False)))
        self.min_size.setValue(int(importer.get("min_file_size_bytes", 0) or 0))
        self.max_size.setValue(int(importer.get("max_file_size_bytes", 0) or 0))
        self.require_exif_check.setChecked(bool(importer.get("require_exif", False)))
        self.exclude_thumbnails_check.setChecked(bool(importer.get("exclude_thumbnails", True)))
        self.excludes_field.setText(", ".join(importer.get("exclude_path_contains", [])))
        self._update_path_guidance()
        self._refresh_summaries()

    def _database_path(self):
        raw = self.database_field.text().strip() or "located_files.db"
        path = Path(raw).expanduser()
        return path if path.is_absolute() else PROJECT_ROOT / path

    def _reports_folder(self):
        return self._database_path().parent / "reports"

    def _save_settings(self):
        update_gui_runtime_paths(self.runtime_config, source_folder=self.source_field.text().strip(), archive_folder=self.archive_field.text().strip())
        self.runtime_config["gui"]["prepare_classify_images"] = self.classify_check.isChecked()
        self.runtime_config["gui"]["prepare_try_ocr"] = self.ocr_check.isChecked()
        self.runtime_config["tools"]["indexer"]["database_path"] = self.database_field.text().strip() or "located_files.db"
        self.runtime_config["tools"]["indexer"]["extensions"] = self._checked_extensions(self.index_extension_checks) + self._custom_extensions(self.index_other_extensions.text())
        self.runtime_config["tools"]["indexer"]["look_inside_archives"] = self.index_archives_check.isChecked()
        importer = self.runtime_config["tools"].setdefault("importer", {})
        importer.update({
            "database_path": str(self._database_path()),
            "archive_root": self.archive_field.text().strip(),
            "extensions_to_copy": self._checked_extensions(self.import_extension_checks) + self._custom_extensions(self.import_other_extensions.text()),
            "min_file_size_bytes": self.min_size.value(),
            "max_file_size_bytes": self.max_size.value() or None,
            "require_exif": self.require_exif_check.isChecked(),
            "exclude_thumbnails": self.exclude_thumbnails_check.isChecked(),
            "exclude_path_contains": [part.strip() for part in self.excludes_field.text().split(",") if part.strip()],
        })
        save_gui_runtime(self.runtime_config)
        if hasattr(self, "index_summary"):
            self._refresh_summaries()

    @staticmethod
    def _checked_extensions(controls):
        return [extension for extension, checkbox in controls.items() if checkbox.isChecked()]

    @staticmethod
    def _custom_extensions(value):
        return [extension.strip().lower().lstrip(".") for extension in value.split(",") if extension.strip()]

    def _format_type_summary(self, controls, other_text):
        selected = self._checked_extensions(controls) + self._custom_extensions(other_text)
        if not selected:
            return "No extensions selected"
        categories = []
        known_selected = set(selected)
        for category, extensions in MEDIA_TYPES.items():
            count = len(known_selected.intersection(extensions))
            if count:
                categories.append(f"{category}: {count}")
        if other_text.strip():
            categories.append(f"Other: {len(self._custom_extensions(other_text))}")
        ext_preview = ", ".join(f".{extension}" for extension in selected[:6])
        if len(selected) > 6:
            ext_preview += f", +{len(selected) - 6} more"
        return " · ".join(categories) + "\n" + ext_preview

    def _refresh_summaries(self):
        if not hasattr(self, "source_path_summary"):
            return
        values = (
            (self.source_path_summary, self.source_field.text().strip() or "Choose a source folder"),
            (self.archive_path_summary, self.archive_field.text().strip() or "Choose an archive folder"),
            (self.database_path_summary, str(self._database_path())),
        )
        for label, value in values:
            label.setText(value)
            label.setToolTip(value)
        self.index_summary.setText(self._format_type_summary(self.index_extension_checks, self.index_other_extensions.text()))
        self.prepare_summary.setText(
            f"Classify images: {'On' if self.classify_check.isChecked() else 'Off'} · OCR: {'On' if self.ocr_check.isChecked() else 'Off'}\n"
            "Conditioning processes all eligible inventory rows"
        )
        self.import_summary.setText(self._format_type_summary(self.import_extension_checks, self.import_other_extensions.text()))

    def _path_changed(self):
        self._save_settings()
        self._update_path_guidance()

    def _database_path_changed(self):
        self._save_settings()
        self._refresh_summaries()

    def _folder_problem(self, value, purpose):
        value = value.strip()
        if not value:
            return "not selected"
        folder = Path(value).expanduser()
        if not folder.exists():
            return "not available at this path"
        if not folder.is_dir():
            return "the path is not a folder"
        try:
            if purpose == "source":
                with os.scandir(folder) as entries:
                    next(entries, None)
            else:
                with tempfile.NamedTemporaryFile(prefix=".chronovault_path_check_", dir=folder, delete=True):
                    pass
        except OSError as exc:
            return f"cannot {('read' if purpose == 'source' else 'write to')} this folder ({exc})"
        return None

    def _update_path_guidance(self):
        source_problem = self._folder_problem(self.source_field.text(), "source")
        archive_problem = self._folder_problem(self.archive_field.text(), "archive")
        self.guidance_source_button.setVisible(source_problem is not None)
        self.guidance_archive_button.setVisible(archive_problem is not None)
        if source_problem is None and archive_problem is None:
            self.path_guidance.hide()
            return
        detail = []
        if source_problem:
            detail.append(f"Source: {source_problem}.")
        if archive_problem:
            detail.append(f"Archive: {archive_problem}.")
        self.path_guidance_label.setText("Source is the drive ChronoVault scans. Archive is where imported files are stored. Choose or reconnect the folders. " + " ".join(detail))
        self.path_guidance.show()

    def _browse_source(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose source folder")
        if folder:
            self.source_field.setText(folder)
            self._path_changed()
            self._log(f"Source folder set: {folder}")

    def _browse_archive(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose archive folder")
        if folder:
            self.archive_field.setText(folder)
            self._path_changed()
            self._log(f"Archive folder set: {folder}")

    def _browse_database(self):
        path, _ = QFileDialog.getSaveFileName(self, "Choose inventory database", self.database_field.text(), "SQLite database (*.db);;All files (*)")
        if path:
            self.database_field.setText(path)
            self._save_settings()
            self._refresh_summaries()
            self._log(f"Inventory database location set: {path}")

    def _log(self, description):
        append_log_entry(self.settings, description)
        save_settings(self.settings)

    def _set_running_state(self, running, tool_name=""):
        if running:
            self.active_tool_name = tool_name
        self.main_tabs.setEnabled(not running)
        self.status_label.setText(f"Running {tool_name}…" if running else "Ready")
        show_stop = running and tool_name == "Condition Database"
        self.stop_condition_button.setVisible(show_stop)
        self.stop_condition_button.setEnabled(show_stop)

    def _request_condition_stop(self):
        if self.process is None or self.active_tool_name != "Condition Database":
            return
        self.stop_condition_button.setEnabled(False)
        self.status_label.setText("Stopping Condition Database…")
        self.output_panel.appendPlainText("\nRequesting a safe stop after the current checkpoint…")
        self._log("Condition Database stop requested")
        self.process.terminate()

    def _consume_progress_line(self, line):
        prefix = "CHRONOVAULT_PROGRESS "
        # The shared hash helper prints an in-place byte counter with `\r`
        # immediately before its caller emits the machine-readable event.
        # Keep parsing the documented event when both arrive on one terminal
        # line, while leaving the combined text visible in the output panel.
        prefix_index = line.find(prefix)
        if prefix_index < 0:
            return
        try:
            event = json.loads(line[prefix_index + len(prefix):])
        except json.JSONDecodeError:
            return
        if event.get("version") != 1 or event.get("tool") != "condition_database":
            return
        if event.get("event") != "progress":
            return
        stage_names = {
            "hash_refresh": "Hash refresh",
            "date_conditioning": "Date conditioning",
            "duplicate_regrouping": "Duplicate regrouping",
        }
        stage = stage_names.get(event.get("stage"), event.get("stage", "Working"))
        completed = event.get("completed", 0)
        total = event.get("total", 0)
        progress = f"{completed}/{total}"
        file_bytes_total = event.get("file_bytes_total")
        if file_bytes_total:
            file_bytes_completed = event.get("file_bytes_completed", 0)
            progress += f" · {file_bytes_completed}/{file_bytes_total} bytes"
        self.status_label.setText(f"Condition Database · {stage} {progress}")

    def _append_output(self):
        if self.process is not None:
            data = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
            if data:
                self._stdout_event_buffer += data
                lines = self._stdout_event_buffer.split("\n")
                self._stdout_event_buffer = lines.pop()
                for line in lines:
                    line = line.rstrip("\r")
                    self._consume_progress_line(line)
                    if "CHRONOVAULT_PROGRESS " not in line:
                        self.output_panel.appendPlainText(line)

    def _flush_stdout_event_buffer(self):
        if not self._stdout_event_buffer:
            return
        line = self._stdout_event_buffer.rstrip("\r")
        self._stdout_event_buffer = ""
        self._consume_progress_line(line)
        if "CHRONOVAULT_PROGRESS " not in line:
            self.output_panel.appendPlainText(line)

    def _launch_tool(self, tool_name, script_relative_path, args, next_steps=None):
        if self.process is not None:
            QMessageBox.warning(self, "Busy", "Another tool is already running.")
            return
        script = PROJECT_ROOT / script_relative_path
        if not script.exists():
            QMessageBox.critical(self, "Tool not found", f"Could not find:\n{script}")
            return
        self.process_queue = list(next_steps or [])
        self._start_process(tool_name, script_relative_path, args)

    def _start_process(self, tool_name, script_relative_path, args):
        self.output_panel.appendPlainText(f"\n$ {Path(sys.executable).name} {script_relative_path} {' '.join(map(str, args))}")
        self._log(f"{tool_name} launched: {script_relative_path} {' '.join(map(str, args))}")
        self._set_running_state(True, tool_name)
        self._stdout_event_buffer = ""
        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(PROJECT_ROOT))
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._append_output)
        self.process.finished.connect(lambda code, status: self._process_finished(tool_name, code, status))
        self.process.start(sys.executable, [str(script_relative_path)] + list(map(str, args)))

    def _process_finished(self, tool_name, exit_code, exit_status):
        self._append_output()
        self._flush_stdout_event_buffer()
        self.process = None
        if (tool_name == "Condition Database"
                and exit_status == QProcess.ExitStatus.NormalExit
                and exit_code == 2):
            self.output_panel.appendPlainText("\n--- Condition Database stopped safely. ---")
            self._log("Condition Database stopped safely")
            self.process_queue.clear()
            self._set_running_state(False)
            self.status_label.setText("Condition Database stopped.")
            return
        if exit_status == QProcess.ExitStatus.CrashExit or exit_code != 0:
            self.output_panel.appendPlainText(f"\n--- {tool_name} failed (exit code {exit_code}). ---")
            self._log(f"{tool_name} failed (exit code {exit_code})")
            self.process_queue.clear()
            self._set_running_state(False)
            self.status_label.setText(f"{tool_name} failed.")
            return
        self.output_panel.appendPlainText(f"\n--- {tool_name} finished. ---")
        self._log(f"{tool_name} finished successfully")
        if self.process_queue:
            next_step = self.process_queue.pop(0)
            self._start_process(*next_step)
            return
        self._set_running_state(False)
        if tool_name == "Condition Database":
            self.status_label.setText("Condition Database completed.")

    def _tool(self, key):
        tool = self.gui_config.get("tools", {}).get(key)
        if not tool:
            QMessageBox.critical(self, "Not configured", f"No '{key}' entry in gui/gui_config.json.")
            return None
        return tool

    def _module_config_path(self, key):
        tool = self._tool(key)
        if not tool:
            return None
        return tool["config"]

    def _write_module_config(self, key, values):
        config = self._module_config_path(key)
        if config is None:
            return False
        try:
            update_values_in_config(config, values)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            QMessageBox.critical(self, "Configuration error", f"Could not update {config}:\n{exc}")
            return False
        return True

    def _common_config(self):
        self._save_settings()
        reports = self._reports_folder()
        reports.mkdir(parents=True, exist_ok=True)
        return str(self._database_path()), reports

    def _run_indexer(self):
        tool = self._tool("indexer")
        if not tool:
            return
        source = self.source_field.text().strip()
        if not source or not Path(source).is_dir():
            QMessageBox.warning(self, "Source unavailable", "Choose an available source folder first.")
            return
        extensions = self._checked_extensions(self.index_extension_checks)
        if not extensions:
            QMessageBox.warning(self, "No file types selected", "Select at least one extension to index.")
            return
        if check_looks_like_archive(source):
            answer = QMessageBox.question(self, "Existing archive selected", "This Source contains archive_database.db. Indexing an archive can create another copy of its files. Continue?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._save_settings()
        self._launch_tool("Indexer", tool["script"], [str(GUI_RUNTIME_PATH), source])

    def _run_prepare(self):
        db, reports = self._common_config()
        steps = []
        if self.classify_check.isChecked():
            tool = self._tool("classify_media")
            if not tool:
                return
            image_extensions = [e for e in self._checked_extensions(self.index_extension_checks) if e in IMAGE_EXTENSIONS]
            if not self._write_module_config("classify_media", {"database_path": db, "output_report_path": str(reports / "classification_report.json"), "image_extensions": image_extensions}):
                return
            steps.append(("Classify Media", tool["script"], [tool["config"]]))
        tool = self._tool("condition_database")
        if not tool:
            return
        if not self._write_module_config("condition_database", {"database_path": db, "output_report_path": str(reports / "condition_report.json"), "try_ocr": self.ocr_check.isChecked()}):
            return
        steps.append(("Condition Database", tool["script"], [tool["config"]]))
        first = steps.pop(0)
        self._launch_tool(*first, next_steps=steps)

    def _run_importer(self):
        tool = self._tool("importer")
        if not tool:
            return
        archive = self.archive_field.text().strip()
        if not archive:
            QMessageBox.warning(self, "Archive not selected", "Choose an Archive folder first.")
            return
        if not self._checked_extensions(self.import_extension_checks):
            QMessageBox.warning(self, "No file types selected", "Select at least one extension to import.")
            return
        status = check_archive_destination(archive)
        if status == "nonempty_no_archive":
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("Archive folder contains other files")
            box.setText("This folder has content but no archive database yet. Choose a dedicated archive folder, create an archive subfolder here, or continue only if this location is intended.")
            use_anyway = box.addButton("Use This Folder Anyway", QMessageBox.ButtonRole.AcceptRole)
            make_subfolder = box.addButton("Create 'archive' Subfolder", QMessageBox.ButtonRole.ActionRole)
            cancel = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(cancel)
            box.exec()
            clicked = box.clickedButton()
            if clicked not in (use_anyway, make_subfolder):
                return
            if clicked is make_subfolder:
                archive = str(Path(archive) / "archive")
                self.archive_field.setText(archive)
                self._path_changed()
        self._save_settings()
        self._launch_tool("Importer", tool["script"], [str(GUI_RUNTIME_PATH)])

    def _run_audit_archive(self):
        tool = self._tool("audit_archive")
        archive = self.archive_field.text().strip()
        if not tool or not archive:
            if not archive:
                QMessageBox.warning(self, "Archive not selected", "Choose an Archive folder first.")
            return
        _, reports = self._common_config()
        if self._write_module_config("audit_archive", {"archive_root": archive, "output_path": str(reports / "audit_result.json")}):
            self._launch_tool("Audit Archive", tool["script"], [tool["config"]])

    def _run_duplicate_finder(self):
        tool = self._tool("duplicate_finder")
        archive = self.archive_field.text().strip()
        if not tool or not archive:
            if not archive:
                QMessageBox.warning(self, "Archive not selected", "Choose an Archive folder first.")
            return
        _, reports = self._common_config()
        if self._write_module_config("duplicate_finder", {"mode": "archive", "archive_root": archive, "output_path": str(reports / "duplicate_report.json")}):
            self._launch_tool("Duplicate Finder", tool["script"], [tool["config"]])

    def _run_review_data(self):
        tool = self._tool("test_retrieve_data")
        archive = self.archive_field.text().strip()
        if not tool or not archive:
            if not archive:
                QMessageBox.warning(self, "Archive not selected", "Choose an Archive folder first.")
            return
        if self._write_module_config("test_retrieve_data", {"archive_root": archive}):
            self._launch_tool("Review uncertain dates", tool["script"], [tool["config"]])

    def _run_test_env(self):
        tool = self._tool("test_env")
        if tool:
            self._launch_tool("Environment check", tool["script"], [])

    def _run_diagnostic_report(self):
        try:
            report = generate_diagnostic_report(
                self.source_field.text().strip(), self.archive_field.text().strip(),
                log_entries=get_log_entries(self.settings), test_folder_value="",
                inventory_database_path=str(self._database_path()),
                runtime_config=self.runtime_config,
            )
            self.output_panel.appendPlainText("\n" + report)
            path = self._reports_folder() / "diagnostic_report.txt"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(report, encoding="utf-8")
            self.output_panel.appendPlainText(f"\n(Also saved to {path})")
            self._log("Diagnostic report generated")
        except Exception as exc:
            QMessageBox.critical(self, "Report failed", f"Could not generate the diagnostic report:\n\n{exc}")
            self._log(f"Diagnostic report failed: {exc}")

    def closeEvent(self, event):
        self._log("Application closed (clean shutdown)")
        self._save_settings()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    try:
        window = ChronoVaultWindow()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        QMessageBox.critical(None, "Runtime configuration error", f"Could not load GUI settings:\n\n{exc}")
        return 1
    if window.previous_session_crashed:
        window.output_panel.appendPlainText("The previous session did not record a clean shutdown. Generate a diagnostic report if something seems wrong.")
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
