"""Load a tool's settings from standalone or GUI runtime JSON."""

import json
from pathlib import Path


CENTRAL_CONFIG_KEYS = {"schema_version", "gui", "tools"}
CENTRAL_CONFIG_VERSION = 1


def load_tool_config(config_path, tool_name):
    """Return one tool config section, accepting central and standalone files.

    Standalone configs remain ordinary top-level tool objects. The central
    GUI runtime file keeps the same tool object under ``tools[tool_name]``.
    """
    with Path(config_path).open("r", encoding="utf-8") as config_file:
        config = json.load(config_file)

    if not isinstance(config, dict):
        raise ValueError("Configuration must be a JSON object.")

    if CENTRAL_CONFIG_KEYS.issubset(config):
        if config["schema_version"] != CENTRAL_CONFIG_VERSION:
            raise ValueError(
                f"Unsupported central configuration schema version: {config['schema_version']}"
            )
        if not isinstance(config["gui"], dict) or not isinstance(config["tools"], dict):
            raise ValueError("Central configuration must contain object-valued 'gui' and 'tools' blocks.")
        tool_config = config["tools"].get(tool_name)
        if not isinstance(tool_config, dict):
            raise ValueError(f"Central configuration has no object-valued '{tool_name}' tool section.")
        return tool_config

    return config
