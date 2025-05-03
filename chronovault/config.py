"""
ChronoVault config module.

Defines constants and configuration settings (e.g., image extensions, archive
directory) for ChronoVault.

Author: chronomicron@gmail.com
Created: 2025-05-03
"""

import json
from pathlib import Path

def get_config():
    """Initialize the config module."""
    return "Config module initialized"

def load_config(config_file="config.json"):
    """Load configuration from JSON file."""
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Default config
        config_data = {
            "scan_dir": "",
            "vault_dir": "",
            "archive_dir": str(Path.home() / "ChronoVault" / "Archive"),
            "copy_not_move": True,
            "scan_locations": []
        }
        save_config(config_data, config_file)
        return config_data

def save_config(config_data, config_file="config.json"):
    """Save configuration to JSON file."""
    with open(config_file, 'w') as f:
        json.dump(config_data, f, indent=4)

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.bmp', '.raw'}
DEFAULT_ARCHIVE_DIR = str(Path.home() / "ChronoVault" / "Archive")