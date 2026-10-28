#!/usr/bin/env python3
"""Initialize a ChronoVault workspace after the native bootstrap launcher.

Checks the Python environment, collects the current source and archive paths,
verifies access, and saves the paths for the GUI. It does not install packages
or create pipeline databases; Indexer and Importer own those databases.
"""

import argparse
import configparser
import importlib.util
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
GUI_SETTINGS_PATH = PROJECT_ROOT / "gui" / "gui_settings.ini"
REQUIREMENTS_PATH = PROJECT_ROOT / "requirements.txt"


def _dependency_result(label, available, detail="", required=False):
    mark = "OK" if available else ("REQUIRED MISSING" if required else "OPTIONAL MISSING")
    suffix = f" — {detail}" if detail else ""
    print(f"[{mark}] {label}{suffix}")
    return available or not required


def check_environment():
    """Report installed requirements; never install or modify packages."""
    print("\nChronoVault environment checks")
    print("------------------------------")
    version_ok = sys.version_info >= (3, 8)
    okay = _dependency_result(
        "Python",
        version_ok,
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} (requires 3.8+)",
        required=True,
    )
    okay &= _dependency_result("SQLite", True, sqlite3.sqlite_version, required=True)

    # Pillow is the only required third-party package for the currently
    # implemented pipeline. Other dependencies unlock optional features.
    required_modules = (("Pillow", "PIL", "Pillow"),)
    optional_modules = (
        ("NumPy", "numpy", "numpy"),
        ("OpenCV", "cv2", "opencv-python-headless"),
        ("pytesseract", "pytesseract", "pytesseract"),
        ("pycdlib", "pycdlib", "pycdlib"),
    )
    for label, module, package in required_modules:
        found = importlib.util.find_spec(module) is not None
        okay &= _dependency_result(
            label,
            found,
            "install with: python3 -m pip install " + package if not found else "",
            required=True,
        )
    for label, module, package in optional_modules:
        found = importlib.util.find_spec(module) is not None
        detail = "" if found else f"install with: python3 -m pip install {package} (optional feature)"
        _dependency_result(label, found, detail)

    tesseract = shutil.which("tesseract")
    detail = "" if tesseract else "install the Tesseract OCR application for OCR features"
    _dependency_result("Tesseract executable", bool(tesseract), detail)

    check_gui_runtime()

    if REQUIREMENTS_PATH.is_file():
        missing = missing_manifest_packages(REQUIREMENTS_PATH)
        if missing:
            okay &= _dependency_result(
                "requirements.txt",
                False,
                "missing packages: " + ", ".join(missing)
                + "; install manually with: python3 -m pip install -r requirements.txt",
                required=True,
            )
        else:
            _dependency_result("requirements.txt", True, "all listed packages appear installed")
    else:
        print("[INFO] No requirements.txt is present; checked the dependencies currently used by ChronoVault.")

    print("Packages are not installed automatically.")
    return okay


def check_gui_runtime():
    """Try to construct and show ChronoVault's window using Qt offscreen."""
    if importlib.util.find_spec("PySide6") is None:
        _dependency_result(
            "GUI startup",
            False,
            "PySide6 is missing; install with: python3 -m pip install PySide6",
        )
        return False

    probe = textwrap.dedent(
        """
        import sys
        from pathlib import Path
        root = Path(sys.argv[1])
        sys.path.insert(0, str(root / "gui"))
        from PySide6.QtWidgets import QApplication
        import chronovault_gui as gui
        # Keep the startup check read-only: window construction normally records
        # activity in gui_settings.ini, which this diagnostic must not change.
        gui.check_and_log_startup = lambda settings: False
        gui.save_settings = lambda settings: None
        app = QApplication([])
        window = gui.ChronoVaultWindow()
        window.show()
        app.processEvents()
        from PySide6.QtCore import QLibraryInfo
        print("CHRONOVAULT_GUI_OK")
        print("QT_PLUGINS=" + QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath))
        """
    )
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    try:
        result = subprocess.run(
            [sys.executable, "-c", probe, str(PROJECT_ROOT)],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except subprocess.TimeoutExpired:
        _dependency_result("GUI startup", False, "Qt window startup check timed out after 20 seconds")
        return False
    except OSError as exc:
        _dependency_result("GUI startup", False, f"could not start the Python check: {exc}")
        return False

    if result.returncode != 0 or "CHRONOVAULT_GUI_OK" not in result.stdout:
        explanation = (result.stderr or result.stdout).strip()
        if not explanation:
            explanation = f"startup check exited with status {result.returncode}"
        _dependency_result("GUI startup", False, explanation)
        if "xcb" in explanation.lower() or "platform plugin" in explanation.lower():
            print("  On Linux, see gui/README.md for Qt platform-library guidance (including libxcb-cursor0).")
        return False

    _dependency_result("GUI startup", True, "Qt initialized and ChronoVault's window opened offscreen")
    plugin_line = next((line for line in result.stdout.splitlines() if line.startswith("QT_PLUGINS=")), None)
    if sys.platform.startswith("linux") and plugin_line:
        report_xcb_dependencies(Path(plugin_line.partition("=")[2]))
    print("  This checks Qt and window construction; it cannot verify the current desktop display session.")
    return True


def report_xcb_dependencies(plugin_root):
    """On Linux, report missing shared libraries for Qt's XCB platform plugin."""
    xcb_plugin = plugin_root / "platforms" / "libqxcb.so"
    ldd = shutil.which("ldd")
    if not xcb_plugin.is_file() or not ldd:
        return
    try:
        result = subprocess.run(
            [ldd, str(xcb_plugin)], capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return
    missing = [line.strip() for line in result.stdout.splitlines() if "not found" in line]
    if missing:
        print("  XCB display support has missing system libraries:")
        for dependency in missing:
            print(f"    {dependency}")
        if any("libxcb-cursor.so" in item for item in missing):
            print("  Debian/Ubuntu package: libxcb-cursor0 (other distributions may use another package name).")
        print("  Qt offscreen startup passed, but a graphical session using XCB may fail until these are installed.")


def missing_manifest_packages(path):
    """Check ordinary pinned/unpinned requirements without installing them.

    This supports the common PEP 508 package-name form. Options, editable
    installs, and direct URLs are left to the explicit dependency checks above
    and pip's eventual manual install guidance.
    """
    missing = []
    pattern = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or line.startswith(("-", "git+", "https://", "http://")):
            continue
        match = pattern.match(line)
        if not match:
            continue
        package = match.group(1)
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", package],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if result.returncode != 0:
            missing.append(package)
    return missing


def ask_path(label, value):
    """Return a normalized path, prompting only when no value was supplied."""
    while not value:
        try:
            value = input(f"{label}: ").strip()
        except EOFError:
            raise ValueError(f"{label} is required; pass it as a command-line option.")
    if not value:
        raise ValueError(f"{label} cannot be empty.")
    return Path(value).expanduser().resolve()


def check_source_folder(path):
    if not path.exists():
        raise ValueError(f"Source folder does not exist: {path}")
    if not path.is_dir():
        raise ValueError(f"Source path is not a folder: {path}")
    try:
        with os.scandir(path) as entries:
            next(entries, None)
    except OSError as exc:
        raise ValueError(f"Cannot read source folder '{path}': {exc}") from exc


def prepare_archive_folder(path):
    try:
        path.mkdir(parents=True, exist_ok=True)
        if not path.is_dir():
            raise NotADirectoryError(f"Path exists and is not a folder: {path}")
        with tempfile.NamedTemporaryFile(prefix=".chronovault_write_check_", dir=path, delete=True):
            pass
    except OSError as exc:
        raise ValueError(f"Cannot create or write to archive destination '{path}': {exc}") from exc


def save_gui_paths(source_path, archive_path):
    """Remember the chosen paths in the GUI's existing personal settings."""
    settings = configparser.ConfigParser()
    if GUI_SETTINGS_PATH.is_file():
        settings.read(GUI_SETTINGS_PATH, encoding="utf-8")
    if not settings.has_section("paths"):
        settings.add_section("paths")
    settings["paths"]["source_folder"] = str(source_path)
    settings["paths"]["archive_folder"] = str(archive_path)
    try:
        GUI_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with GUI_SETTINGS_PATH.open("w", encoding="utf-8") as settings_file:
            settings.write(settings_file)
    except OSError as exc:
        raise ValueError(f"Could not save selected paths to '{GUI_SETTINGS_PATH}': {exc}") from exc


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Check ChronoVault requirements and validate source/archive folders."
    )
    parser.add_argument("--source-root", help="readable folder to scan")
    parser.add_argument("--archive-root", help="folder where imported files will be stored")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    print("ChronoVault initialization")
    print("This program checks dependencies and paths; it does not install software or create databases.")

    if not check_environment():
        print("\nResolve the required dependency gaps above, then run initialization again.", file=sys.stderr)
        return 1

    try:
        source_path = ask_path("Source folder to scan", args.source_root)
        archive_path = ask_path("Archive destination folder", args.archive_root)
        check_source_folder(source_path)
        prepare_archive_folder(archive_path)
        save_gui_paths(source_path, archive_path)
    except (OSError, ValueError) as exc:
        print(f"\nSetup could not be completed: {exc}", file=sys.stderr)
        return 1

    print("\nPath checks passed:")
    print(f"  Source:  {source_path} (readable)")
    print(f"  Archive: {archive_path} (created if needed; writable)")
    print(f"Saved these paths for the GUI in {GUI_SETTINGS_PATH}.")
    print("Run Indexer to create the source inventory database. Importer creates the archive database when needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
