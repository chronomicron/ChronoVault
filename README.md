# ChronoVault ⏳📸

**Personal Photo Time Vault**  
A modular, privacy-first photo management tool that scans scattered drives and folders, extracts metadata (EXIF, GPS, etc.), archives images chronologically into a clean vault structure (YYYY/MM/DD), and offers an intuitive browsing interface with powerful metadata viewing.

**Current Development Branch:** `rewrite` (v2 redesign – modular architecture, modern PyQt5 GUI, CLI support)

---

## 🎯 Project Goals

- **Organize chaos** → Gather photos from multiple drives, external HDDs, old backups  
- **Preserve truth** → Never alter originals; keep full EXIF, GPS, and file metadata  
- **Chronological-first** → Browse and navigate by actual capture date (not file modification time)  
- **Modular & extensible** → Swap scanner logic, add AI tagging, change storage backends easily  
- **Dual access** → Full-featured GUI + standalone CLI tools (scan, archive, query)  
- **No cloud** → 100% local — SQLite database, your photos never leave your machine  

---

## 🚀 Current Status (Rewrite Branch)

- **Version:** 0.1.x (initial modular skeleton)  
- **Focus:** Core module separation, placeholder files with versioned headers, CLI + GUI foundation  
- **Tech stack (planned):** Python 3.10+, PyQt5, Pillow, SQLite3  

---

## 📂 Project Structure (v0.1)
ChronoVault/
├── main.py                # Entry point: launches GUI or runs CLI commands
├── config.py              # Loads/saves app settings (JSON) – paths, threads, preferences
├── scanner.py             # Scans directories for images/videos, extracts EXIF → list/JSON
├── archiver.py            # Copies files to vault (YYYY/MM/DD), handles duplicates & deletes
├── database.py            # SQLite interface – insert, query by date/range/tags, metadata
├── ai.py                  # Placeholder for future image labeling / tagging (ML stub)
├── ui.py                  # PyQt5 GUI: folder tree, thumbnail grid, metadata sidebar
├── utils.py               # Shared helpers: EXIF parsing, thumbnail gen, logging, date utils
├── test_cases.py          # Generates fake photos with EXIF for development & testing
└── requirements.txt       # Dependencies: PyQt5, Pillow, ...
text### Module Descriptions

| File              | Role / Responsibility                                                                 | CLI Capable? | GUI Integration |
|-------------------|---------------------------------------------------------------------------------------|--------------|-----------------|
| `main.py`         | App launcher – CLI argument parser + GUI startup                                      | Yes          | Yes             |
| `config.py`       | Centralized configuration (scan/vault paths, threads, file types, etc.)               | Yes          | Yes             |
| `scanner.py`      | Directory traversal, media detection, EXIF extraction → structured output             | Yes          | Yes             |
| `archiver.py`     | Threaded archiving to date-based folders, duplicate handling, optional delete originals | Yes       | Yes             |
| `database.py`     | SQLite CRUD operations: photos table + indexes on date, path, tags                    | Indirect     | Yes             |
| `ai.py`           | Future: face detection, object recognition, auto-tagging                              | Yes (later)  | Yes (later)     |
| `ui.py`           | Full PyQt5 interface: tree view, chrono-aware grid, metadata panel, filters           | No           | Core            |
| `utils.py`        | Reusable helpers used by multiple modules (EXIF, thumbnails, safe file ops, etc.)     | Yes          | Yes             |
| `test_cases.py`   | Creates mock directory trees + images with controlled EXIF for reproducible testing   | Yes          | No              |

---

## 🔢 Versioning Convention (File Headers)

Each Python file begins with a header containing a simple changelog:

```python
# ChronoVault - [Module Name]
# Description: Short explanation of purpose and main interactions
#
# Version History:
#   0.1.1 – Initial placeholder file
#   0.1.2 – Added basic function signatures
#   0.2.1 – Introduced threading support (major feature)

Patch (0.1.x) → small fixes, refinements, docstrings, argument tweaks
Minor (0.x.1) → new functions, important behavior change, new dependency
Major (x.1.1) → big architectural shift, new core feature, major refactor

We only increment versions on meaningful changes — not every commit or typo fix.

🛠️ Getting Started (Development)

Clone & switch to the rewrite branchBashgit clone https://github.com/chronomicron/ChronoVault.git
cd ChronoVault
git checkout rewrite
Install dependenciesBashpip install -r requirements.txt
Run the GUIBashpython main.py
Run a standalone scan (example)Bashpython main.py --scan /path/to/photos --output scan.json


🗺️ Next Milestones (Planned)

 v0.2.x – Basic GUI layout (splitter panes, thumbnail grid, metadata panel)
 v0.3.x – Scanner + Archiver integration in GUI
 v0.4.x – Chronological timeline / calendar view in UI
 v0.5.x – Database population & query-powered browsing
 v1.0.0 – First usable release (full scan → archive → browse loop)


Made with ❤️ for anyone trying to tame 20+ years of scattered family photos.
Questions, ideas, or want to contribute?
→ Open an issue or pull request!
