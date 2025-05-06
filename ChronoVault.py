"""
ChronoVault main application.

Orchestrates the initialization and execution of ChronoVault modules,
including UI, scanner, database, AI, and archiver.

Author: chronomicron@gmail.com
Created: 2025-05-03
Version: 1.0.0
"""

import sys
import logging
from PyQt5.QtWidgets import QApplication
import chronovault.ui as ui_module
import chronovault.scanner as scanner_module
import chronovault.database as database_module
import chronovault.ai as ai_module
import chronovault.config as config_module
import chronovault.archiver as archiver_module

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def test_module(module, module_name):
    """Test initialization of a module."""
    try:
        result = module.init_module()
        logging.info(f"Testing {module_name}: {result}")
        return result
    except Exception as e:
        logging.error(f"Failed to initialize {module_name}: {e}")
        raise

def main():
    """Main function to set up and run the application."""
    # Initialize modules
    modules = [
        (ui_module, "ui"),
        (scanner_module, "scanner"),
        (database_module, "database"),
        (ai_module, "ai"),
        (config_module, "config"),
        (archiver_module, "archiver")
    ]

    for module, name in modules:
        test_module(module, name)

    logging.info("All modules initialized successfully")

    # Set up PyQt application
    app = QApplication(sys.argv)
    window = ui_module.create_main_window()

    try:
        scan_input, vault_input, test_db_button, start_scan_button, status_output, status_emitter = ui_module.setup_ui(window)
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        logging.error(f"Failed to initialize UI: {e}")
        raise

if __name__ == "__main__":
    main()