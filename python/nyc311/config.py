"""Read the project settings and the run parameters."""
from __future__ import annotations

import logging
from pathlib import Path

LOGGER = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "project.properties"
RUN_PARAMS_NAME = "run_params.properties"
REQUIRED_KEYS = (
    "spark_master",
    "spark_driver_memory",
    "seed",
    "slow_threshold_days",
    "history_rows",
    "history_slow_share",
)


class ConfigError(Exception):
    """A setting is missing or a file cannot be read."""


def read_properties(path: Path) -> dict[str, str]:
    """Read a key=value file. Skip empty lines and comment lines."""
    if not path.is_file():
        raise ConfigError(f"File not found: {path}")
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if text and not text.startswith("#") and "=" in text:
            key, _, value = text.partition("=")
            values[key.strip()] = value.strip()
    return values


def load_config(processed: Path, config_path: Path = CONFIG_PATH) -> dict[str, str]:
    """Merge the project settings and the run parameters. Stop if a key is missing."""
    values = read_properties(config_path)
    values.update(read_properties(processed / RUN_PARAMS_NAME))
    missing = [key for key in REQUIRED_KEYS if key not in values]
    if missing:
        raise ConfigError(f"Missing keys {missing} in {config_path} and {processed}.")
    LOGGER.info("Loaded %d settings.", len(values))
    return values


def get_int(config: dict[str, str], key: str) -> int:
    """Return a setting as an integer."""
    try:
        return int(config[key])
    except (KeyError, ValueError) as error:
        raise ConfigError(f"Key '{key}' is missing or not an integer.") from error


def get_float(config: dict[str, str], key: str) -> float:
    """Return a setting as a number."""
    try:
        return float(config[key])
    except (KeyError, ValueError) as error:
        raise ConfigError(f"Key '{key}' is missing or not a number.") from error
