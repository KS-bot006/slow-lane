"""Tests for the config module."""
from pathlib import Path

import pytest

from nyc311 import config


def write(path: Path, text: str) -> Path:
    """Write a fixture file and return its path."""
    path.write_text(text, encoding="utf-8")
    return path


def test_read_properties_skips_comments_and_blank_lines(tmp_path: Path) -> None:
    """Check that comments and blank lines are skipped."""
    path = write(tmp_path / "a.properties", "# note\n\nseed=42\nname = x = y\n")
    assert config.read_properties(path) == {"seed": "42", "name": "x = y"}


def test_missing_file_gives_a_clear_error(tmp_path: Path) -> None:
    """Check that a missing file stops with ConfigError."""
    with pytest.raises(config.ConfigError, match="not found"):
        config.read_properties(tmp_path / "none.properties")


def test_load_config_merges_both_files(tmp_path: Path) -> None:
    """Check that the project settings and the run parameters are merged."""
    project = write(
        tmp_path / "project.properties",
        "spark_master=local[2]\nspark_driver_memory=1g\nseed=42\n",
    )
    write(
        tmp_path / config.RUN_PARAMS_NAME,
        "slow_threshold_days=3\nhistory_rows=10\nhistory_slow_share=0.25\n",
    )
    values = config.load_config(tmp_path, project)
    assert config.get_int(values, "slow_threshold_days") == 3
    assert config.get_float(values, "history_slow_share") == 0.25


def test_load_config_names_the_missing_key(tmp_path: Path) -> None:
    """Check that a missing key is named in the error."""
    project = write(tmp_path / "project.properties", "spark_master=local[2]\n")
    write(tmp_path / config.RUN_PARAMS_NAME, "slow_threshold_days=3\n")
    with pytest.raises(config.ConfigError, match="seed"):
        config.load_config(tmp_path, project)


def test_get_int_rejects_text() -> None:
    """Check that a value that is not a number stops with ConfigError."""
    with pytest.raises(config.ConfigError):
        config.get_int({"seed": "abc"}, "seed")
