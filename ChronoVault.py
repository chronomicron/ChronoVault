"""
ChronoVault main application.

Entry point for the ChronoVault application. Loads and verifies all package
modules (ui, scanner, database, ai, config) and initializes the app.

Author: [chronomicron@gmail.com]
Created: 2025-05-03
"""

import sys
import importlib
from PyQt5.QtWidgets import QApplication

def verify_module(module_name, function_name):
    """Verify if a module and its function exist."""
    try:
        module = importlib.import_module(f"chronovault.{module_name}")
        if hasattr(module, function_name):
            func = getattr(module, function_name)
            return func
        else:
            assert False, f"Function {function_name} not found in {module_name}"
    except ImportError as e:
        assert False, f"Failed to load module {module_name}: {str(e)}"
    except Exception as e:
        assert False, f"Error in module {module_name}: {str(e)}"
    return None

def main():
    """Initialize and run ChronoVault."""
    # List of modules and their init functions
    modules = [
        ("ui", "init_ui"),
        ("scanner", "init_scanner"),
        ("database", "init_database"),
        ("ai", "init_ai"),
        ("config", "get_config")
    ]

    # Verify and test each module
    test_functions = {}
    for module_name, function_name in modules:
        func = verify_module(module_name, function_name)
        if func:
            try:
                print(f"Testing {module_name}: {func()}")
                test_functions[module_name] = func
            except Exception as e:
                assert False, f"Error executing {function_name} in {module_name}: {str(e)}"
        else:
            # Assertion already printed by verify_module
            continue

    # Initialize PyQt application
    app = QApplication(sys.argv)

    # Set up UI if available
    if "ui" in test_functions:
        try:
            ui_module = importlib.import_module("chronovault.ui")
            window = ui_module.create_main_window()
            scan_input, db_input = ui_module.setup_ui(window)
            window.show()
        except Exception as e:
            assert False, f"Failed to initialize UI: {str(e)}"
    else:
        print("UI module not available, running in console mode")

    # Run application
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()