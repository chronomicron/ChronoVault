# ChronoVault GUI

The PySide6 GUI presents the existing command-line tools as an ordered archive workflow. It owns path and option selection, launches tools as subprocesses from the repository root, and streams their output. Pipeline behavior stays in each tool.

## Run

```bash
python3 chronovault.py
```

Install PySide6 to use the desktop interface:

```bash
python3 -m pip install PySide6
```

The GUI can also be started with `python3 gui/chronovault_gui.py`. On Linux, Qt may need the system package `libxcb-cursor0` when the XCB platform plugin cannot start.

## Workflow

The window separates **Workflow**, **Review**, and **Settings**. Workflow keeps the three selected locations, ordered stages, concise type summaries, and primary actions visible without exposing every checkbox. The four stage cards stay compact; the terminal output panel below them grows with the window. Settings has Workspace, Index, Prepare, and Import subviews for advanced controls. Review contains duplicate analysis, uncertain-date access, environment checks, and diagnostic reporting. The stage cards use blue, violet, teal, and orange accents.

The main stages are:

1. **Index source** runs Indexer with the selected Source folder as its scan-root argument. Its exact extension selections and optional archive-member listing setting are saved in the central runtime config. Indexer records paths and metadata; it does not copy source files.
2. **Prepare inventory** optionally runs Classify Media, then runs Condition Database. Classification is limited to the image extensions selected for indexing. Conditioning hashes and analyzes all eligible inventory rows. The OCR option is passed to Condition Database. These stages update the source inventory and reports; they do not copy media.
3. **Import selected files** runs Importer using the separate extension selections and filter controls. Importer copies eligible files into the selected Archive and updates the archive and inventory databases. Source files remain in place.
4. **Verify archive** runs Audit Archive, which reports disk/database mismatches without repairing or moving files.

After import, **Find duplicate groups** runs Duplicate Finder in archive mode, and **Review uncertain dates** runs the existing read-only review-data diagnostic against the selected Archive. This is review-data access, not an interactive correction interface. Corrections remain the responsibility of `write_data` workflows.

The Settings subviews list individual extensions, including separate `.jpg` and `.jpeg` choices. Photo, video, and audio selections control Indexer and Importer inputs; they do not add type-specific date extraction. Audio and video date tools remain future work. Other extensions can be entered as comma-separated values.

Import filters expose minimum and maximum file size, EXIF requirement, thumbnail exclusion, and excluded path fragments. The Index stage exposes optional archive-member listing. OCR belongs to Prepare. These controls are written to the settings consumed by the relevant tool when that action is launched.

While a tool is running, the GUI disables workflow controls so two subprocesses cannot write the shared inventory or archive at once. Prepare runs its selected subprocesses in sequence and stops if one fails. During Condition Database, **Stop conditioning** requests a cooperative stop; the tool reports stage progress using `CHRONOVAULT_PROGRESS ` JSON events and exits with a distinct stopped code. The GUI displays the reported stage and completed/total row counts, plus byte progress for the source file currently being hashed, and treats stopped, completed, and failed runs separately. Machine progress events stay out of the output log; it shows commands and human-readable tool output.

## Workspace paths and configuration

The Workspace header contains:

- **Source** — the drive or folder Indexer scans.
- **Archive** — the folder where Importer stores dated copies and `archive_database.db`.
- **Inventory** — the `located_files.db` file shared by Indexer, Classify Media, Condition Database, Importer, and source-mode operations.

Source, Archive, and GUI preferences are saved in the ignored `gui/gui_runtime.json`; `gui/gui_runtime.example.json` is the tracked template. If the runtime file is first created, saved legacy Source/Archive/Test values are carried forward from `gui_settings.ini`. The database selector stores its path under `tools.indexer.database_path`. The optional Classify and OCR choices are GUI preferences under `gui`; at launch, the GUI writes them into the module configs those unmigrated tools actually read.

The current default database path remains `located_files.db`, relative to the repository working directory. The proposed per-user application-data defaults and XDG/macOS/Windows path rules are not implemented yet. The GUI currently lets the user choose a database file directly.

Indexer and Importer accept their section from the central runtime file and still accept their standalone module config JSON. Before launching Classify Media, Condition Database, Audit Archive, Duplicate Finder, and the review-data diagnostic, the GUI updates the supported keys in those tools' existing module configs. The central template may contain later-tool sections, but the GUI does not use those sections for these unmigrated tools.

`gui/gui_config.json` remains the checked-in script and module-config location map. `gui/gui_settings.ini` stores the rolling activity log and clean-shutdown marker. Diagnostic reports include the active Indexer/Importer runtime settings and selected inventory database, and are written under a `reports/` directory beside that database.

## Startup and safety behavior

The GUI shows an inline, non-blocking reminder when Source is missing or unavailable for reading, or Archive is missing or unavailable for writing. It explains the paths and provides folder chooser buttons. Database files do not have to exist at startup; Indexer and Importer create them as needed.

Before indexing, the GUI detects when Source is already a ChronoVault archive and asks before proceeding. Before importing, it checks whether the Archive folder has content but no `archive_database.db`. The user can cancel, create a dedicated `archive/` subfolder, or explicitly use the selected folder. Audit is report-only. Duplicate Finder reports matching hashes and may cache hashes in the archive database; it does not remove or choose files. Review lists uncertain-date records without changing them.

The normal pipeline reads and copies source files. It does not delete or move them. The GUI has no delete or repair actions.

## Current scope and limitations

- Indexer and Importer support both central runtime and standalone config files. Other launched tools still use module config files, which the GUI synchronizes immediately before their actions.
- Inventory and archive relocation controls are not implemented. Changing the Inventory field selects a database path; it does not move an existing database. Changing Archive selects a destination; it does not move an existing archive or its media.
- The GUI does not resolve a platform-specific application-data database default yet. Relative paths continue to depend on the repository working directory.
- Review uncertain dates is read-only command-line access, not an interactive date editor. Use the `write_data` interface for corrections.
- Classify Media currently provides image classification only. Indexing or importing video/audio files does not mean video/audio date analysis exists.
- Only Condition Database currently has a controlled Stop action with committed-work reuse and rollback-safe duplicate regrouping. Other tools can still only be interrupted by terminating their subprocess, and closing the GUI does not coordinate cancellation.
- Environment check runs the existing `test_env.py` diagnostic. Generate diagnostic report summarizes mapped tool configs, paths, activity, and database information.

## Related files

| File | Purpose |
|---|---|
| `chronovault_gui.py` | Qt workflow and subprocess coordination. |
| `gui_data.py` | Runtime settings, path checks, activity log, and diagnostic report logic. |
| `gui_config.json` | Checked-in script/config location map. |
| `checkbox-check.svg` | Small checkmark used to keep selected extension controls legible across Qt themes. |
| `gui_runtime.example.json` | Tracked template for personal GUI settings. |
| `gui_runtime.json` | Personal ignored runtime configuration. |
| `gui_settings.ini` | Personal activity log and shutdown marker. |
