"""Tests for the leakage guards. The frames hold fixture rows."""
import pytest
from pyspark.sql import DataFrame, SparkSession

from nyc311 import data


def frame(spark: SparkSession, rows: list[tuple]) -> DataFrame:
    """Build a fixture frame: unique_key, window, created_date, x, y."""
    schema = "unique_key string, window string, created_date string, x double, y string"
    return spark.createDataFrame(rows, schema)


GOOD = [
    ("1", "train", "2025-07-01T00:00:00", 0.1, "a"),
    ("2", "train", "2025-09-30T23:59:59", 0.2, "b"),
    ("3", "test", "2025-10-01T00:00:00", 0.3, "c"),
]


def test_good_frame_passes_every_guard(spark: SparkSession) -> None:
    """Check that a clean frame raises no error."""
    df = frame(spark, GOOD)
    data.check_windows(df)
    data.check_time_order(df)
    data.check_unique_keys(df)
    data.check_no_nulls(df, ["x", "y"])
    data.check_feature_names(["x", "y"])


def test_window_value_other_than_train_or_test_fails(spark: SparkSession) -> None:
    """Check that the value history in the column window stops the run."""
    df = frame(spark, GOOD + [("4", "history", "2025-01-01T00:00:00", 0.4, "d")])
    with pytest.raises(data.LeakageError, match="window"):
        data.check_windows(df)


def test_train_after_test_fails(spark: SparkSession) -> None:
    """Check that overlapping train and test dates stop the run."""
    df = frame(spark, GOOD + [("4", "train", "2025-10-01T00:00:00", 0.4, "d")])
    with pytest.raises(data.LeakageError, match="not before"):
        data.check_time_order(df)


def test_missing_window_fails(spark: SparkSession) -> None:
    """Check that a frame without test rows stops the run."""
    df = frame(spark, GOOD[:2])
    with pytest.raises(data.LeakageError, match="Both windows"):
        data.check_time_order(df)


def test_duplicate_key_fails(spark: SparkSession) -> None:
    """Check that a repeated unique_key stops the run."""
    df = frame(spark, GOOD + [("1", "test", "2025-11-01T00:00:00", 0.4, "d")])
    with pytest.raises(data.LeakageError, match="repeat"):
        data.check_unique_keys(df)


def test_feature_in_not_features_fails() -> None:
    """Check that a column of NOT_FEATURES cannot be a feature."""
    with pytest.raises(data.LeakageError, match="NOT_FEATURES"):
        data.check_feature_names(["agency", "duration_days"])


@pytest.mark.parametrize(
    "name", ["closed_flag", "resolution_code", "status_x", "due_soon"]
)
def test_banned_name_part_fails(name: str) -> None:
    """Check that a banned part in a feature name stops the run."""
    with pytest.raises(data.LeakageError, match="banned"):
        data.check_feature_names(["agency", name])


def test_real_feature_names_pass() -> None:
    """Check that the planned feature columns pass the name guard."""
    data.check_feature_names(data.FEATURE_COLUMNS)
    assert len(data.FEATURE_COLUMNS) == 18


def test_null_fails(spark: SparkSession) -> None:
    """Check that a null in a feature column stops the run."""
    df = frame(spark, GOOD + [("4", "test", "2025-11-01T00:00:00", 0.4, None)])
    with pytest.raises(data.LeakageError, match="Null"):
        data.check_no_nulls(df, ["x", "y"])


def test_nan_fails(spark: SparkSession) -> None:
    """Check that a NaN in a number column stops the run."""
    df = frame(spark, GOOD + [("4", "test", "2025-11-01T00:00:00", float("nan"), "d")])
    with pytest.raises(data.LeakageError, match="Null"):
        data.check_no_nulls(df, ["x", "y"])
