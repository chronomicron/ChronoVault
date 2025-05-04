"""
ChronoVault main application.

Initializes and runs the PyQt-based GUI for scanning, archiving, and managing
images.

Author: chronomicron@gmail.com
Created: 2025-05-03
"""

import sys
import os
from importlib import import_module
from PyQt5.QtWidgets import QApplication
import logging

# Set Qt platform to X11 to avoid Wayland issues
os.environ["QT_QPA_PLATFORM"] = "xcb"

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

MODULES = {
    "ui": "chronovault.ui",
    "scanner": "chronovault.scanner",
    "database": "chronovault.database",
    "ai": "chronovault.ai",
    "config": "chronovault.config",
    "archiver": "chronovault.archiver"
}

def test_module(module_name, function_name="init"):
    """Test a module by calling its init function."""
    try:
        module = import_module(MODULES[module_name])
        func = getattr(module, f"{function_name}_{module_name}")
        logging.info(f"Testing {module_name}: {func()}")
    except Exception as e:
        logging.error(f"Error executing {function_name} in {module_name}: {str(e)}")
        raise

def main():
    """Main function to initialize and run ChronoVault."""
    # Test all modules
    for module_name in MODULES:
        test_module(module_name)
    logging.info("All modules initialized successfully")

    # Initialize PyQt application
    app = QApplication(sys.argv)

    # Set up UI
    try:
        ui_module = import_module(MODULES["ui"])
        window = ui_module.create_main_window()
        scan_input, vault_input, test_db_button, start_scan_button, status_output, status_emitter = ui_module.setup_ui(window)
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        logging.error(f"Failed to initialize UI: {str(e)}")
        raise

if __name__ == "__main__":
    main()