# ChronoVault - Configuration Module
# Description: Central place to load, store and save user/app settings.
# Settings include paths (vault, database), preferences (threads, delete originals),
# supported file types, etc.
#
# Loaded early by the main entry point and passed/used by other modules.
#
# Version History:
#   0.1.1 – Initial placeholder with simple JSON config class

import json
from pathlib import Path
from typing import Any


DEFAULT_CONFIG = {
    "vault_path": "vault",
    "db_path": "chronovault.db",
    "scan_paths": [],
    "supported_extensions": [".jpg", ".jpeg", ".png", ".gif", ".mp4", ".mov"],
    "max_threads": 4,
    "delete_originals_after_archive": False,
    "last_scan_date": None
}


class Config:
    """Simple persistent configuration handler."""

    def __init__(self, config_file: str | Path = "config.json"):
        self.filepath = Path(config_file)
        self.data = DEFAULT_CONFIG.copy()
        self.load()

    def load(self) -> None:
        if not self.filepath.is_file():
            return
        try:
            with self.filepath.open("r", encoding="utf-8") as f:
                loaded = json.load(f)
                self.data.update(loaded)
        except Exception as e:
            print(f"Warning: Could not load config {self.filepath}: {e}")

    def save(self) -> None:
        try:
            with self.filepath.open("w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, sort_keys=True)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value


if __name__ == "__main__":
    # Smoke test
    cfg = Config("test_config.json")
    print("Initial config:", cfg.data)
    cfg.set("vault_path", "/Users/me/Pictures/ChronoVault")
    cfg.set("scan_paths", ["/DCIM", "/Photos/2024"])
    cfg.save()
    print("Updated & saved.")