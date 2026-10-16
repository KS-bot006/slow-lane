"""Load the feature table, split it by time, and run the leakage guards."""
from __future__ import annotations

import logging
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, FloatType

LOGGER = logging.getLogger(__name__)

FEATURES_NAME = "features.parquet"
TRAIN = "train"
TEST = "test"
LABEL = "label"

CATEGORICAL = [
    "agency", "complaint_type", "descriptor_g", "location_type_g", "borough",
    "channel", "hour", "dow",
]
NUMERIC_TIME = ["is_weekend"]
NUMERIC_HISTORY = [
    f"{key}_{name}"
    for key in ("h1", "h2", "h3")
    for name in ("slow_rate", "mean_log_days", "log_n")
]
NOT_FEATURES = [
    "unique_key", "window", "created_date", "label", "duration_days", "zip",
]
FEATURE_COLUMNS = CATEGORICAL + NUMERIC_TIME + NUMERIC_HISTORY
BANNED_NAME_PARTS = ("closed", "resolution", "status", "due")


class LeakageError(Exception):
    """A leakage guard failed."""


def check_windows(df: DataFrame) -> None:
    """Stop if the column window holds a value other than train or test."""
    found = {row["window"] for row in df.select("window").distinct().collect()}
    if not found <= {TRAIN, TEST}:
        raise LeakageError(f"The column window holds {sorted(found)}.")


def check_time_order(df: DataFrame) -> None:
    """Stop if the latest train date is not before the earliest test date."""
    rows = df.groupBy("window").agg(
        F.min("created_date").alias("first"), F.max("created_date").alias("last")
    ).collect()
    bounds = {row["window"]: (row["first"], row["last"]) for row in rows}
    if TRAIN not in bounds or TEST not in bounds:
        raise LeakageError(f"Both windows need rows. Found {sorted(bounds)}.")
    if bounds[TRAIN][1] >= bounds[TEST][0]:
        raise LeakageError(
            f"Latest train date {bounds[TRAIN][1]} is not before "
            f"earliest test date {bounds[TEST][0]}."
        )


def check_unique_keys(df: DataFrame) -> None:
    """Stop if a unique_key appears more than once."""
    row = df.agg(
        F.count("*").alias("rows"), F.countDistinct("unique_key").alias("keys")
    ).first()
    if row["rows"] != row["keys"]:
        raise LeakageError(f"{row['rows'] - row['keys']} unique_key values repeat.")


def check_feature_names(columns: list[str]) -> None:
    """Stop if a feature column is a non-feature or has a banned name part."""
    overlap = sorted(set(columns) & set(NOT_FEATURES))
    if overlap:
        raise LeakageError(f"Feature columns in NOT_FEATURES: {overlap}.")
    banned = [
        name for name in columns
        if any(part in name.lower() for part in BANNED_NAME_PARTS)
    ]
    if banned:
        raise LeakageError(f"Feature names with a banned part: {banned}.")


def check_no_nulls(df: DataFrame, columns: list[str]) -> None:
    """Stop if a feature column has a null or NaN value. One pass over the data."""
    checks = []
    for name in columns:
        missing = F.col(name).isNull()
        if isinstance(df.schema[name].dataType, (DoubleType, FloatType)):
            missing = missing | F.isnan(F.col(name))
        checks.append(F.sum(F.when(missing, 1).otherwise(0)).alias(name))
    row = df.agg(*checks).first()
    bad = {name: row[name] for name in columns if row[name]}
    if bad:
        raise LeakageError(f"Null or NaN values found: {bad}.")


def run_guards(df: DataFrame, columns: list[str] = FEATURE_COLUMNS) -> None:
    """Run every leakage guard on the feature table."""
    check_windows(df)
    check_time_order(df)
    check_unique_keys(df)
    check_feature_names(columns)
    check_no_nulls(df, columns)
    LOGGER.info("All leakage guards passed.")


def load_data(spark: SparkSession, processed: Path) -> tuple[DataFrame, DataFrame]:
    """Load the features, run the guards, and return the train and test frames."""
    path = processed / FEATURES_NAME
    if not path.is_dir():
        raise LeakageError(f"Feature table not found: {path}")
    df = spark.read.parquet(str(path.resolve()))
    run_guards(df)
    return df.filter(F.col("window") == TRAIN), df.filter(F.col("window") == TEST)
