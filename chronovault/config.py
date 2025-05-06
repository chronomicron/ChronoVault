"""
ChronoVault config module.

Manages configuration settings stored in a JSON file.

Author: chronomicron@gmail.com
Created: 2025-05-03
Version: 1.0.0
"""

import json
from pathlib import Path

def init_config():
    """Initialize the config module."""
    return "Config module initialized"

def load_config():
    """Load configuration from config.json."""
    config_file = Path("config.json")
    default_config = {"scan_dir": "", "vault_dir": ""}
    try:
        if config_file.exists():
            with config_file.open() as f:
                config_data = json.load(f)
                # Ensure all required keys are present
                for key in default_config:
                    if key not in config_data:
                        config_data[key] = default_config[key]
                return config_data
        return default_config
    except Exception as e:
        print(f"Error loading config: {e}")
        return default_config

def save_config(config_data):
    """Save configuration to config.json."""
    config_file = Path("config.json")
    try:
        with config_file.open("w") as f:
            json.dump(config_data, f, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")

def init_module():
    """Initialize the config module (for compatibility)."""
    return init_config()