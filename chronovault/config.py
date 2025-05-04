"""
ChronoVault configuration module.

Manages loading and saving configuration settings from a JSON file.

Author: chronomicron@gmail.com
Created: 2025-05-03
"""

import json
from pathlib import Path

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.bmp', '.raw'}

def init_config():
    """Initialize the config module."""
    return "Config module initialized"

def load_config():
    """Load configuration from config.json."""
    config_file = Path("config.json")
    default_config = {
        "scan_dir": "",
        "vault_dir": "",
        "archive_dir": "~/ChronoVault/Archive",
        "copy_not_move": True,
        "scan_locations": [],
        "max_threads": 4
    }
    try:
        if config_file.exists():
            with config_file.open('r') as f:
                config_data = json.load(f)
            # Ensure all default keys are present
            for key, value in default_config.items():
                if key not in config_data:
                    config_data[key] = value
            return config_data
        else:
            return default_config
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in config.json: {e}")
        return default_config
    except Exception as e:
        print(f"Error: Failed to load config: {e}")
        return default_config

def save_config(config_data):
    """Save configuration to config.json."""
    config_file = Path("config.json")
    try:
        with config_file.open('w') as f:
            json.dump(config_data, f, indent=4)
    except PermissionError as e:
        print(f"Error: Permission denied writing to config.json: {e}")
    except Exception as e:
        print(f"Error: Failed to save config: {e}")