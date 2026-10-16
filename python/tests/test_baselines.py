"""Tests for the baselines. The frames hold fixture rows."""
import pytest
from pyspark.sql import SparkSession

from nyc311 import baselines


def test_majority_label_follows_the_most_frequent_label(spark: SparkSession) -> None:
    """Check that the majority label is 0.0 for a train window with 25 percent slow."""
    train = spark.createDataFrame([(1.0,), (0.0,), (0.0,), (0.0,)], "label double")
    assert baselines.majority_label(train) == 0.0
    slow = spark.createDataFrame([(1.0,), (1.0,), (0.0,)], "label double")
    assert baselines.majority_label(slow) == 1.0


def test_majority_baseline_has_a_constant_prediction_and_score(
    spark: SparkSession,
) -> None:
    """Check that every row gets the same prediction and score."""
    df = spark.createDataFrame([(1.0,), (0.0,)], "label double")
    rows = baselines.with_majority(df, 0.0).collect()
    assert {(row["prediction"], row["score"]) for row in rows} == {(0.0, 0.0)}


def test_history_rule_predicts_slow_at_a_rate_of_half_or_more(
    spark: SparkSession,
) -> None:
    """Check the rule on rates below, at, and above 0.5."""
    df = spark.createDataFrame(
        [(1.0, 0.2), (1.0, 0.5), (0.0, 0.9)], "label double, h1_slow_rate double"
    )
    rows = baselines.with_history_rule(df).orderBy("h1_slow_rate").collect()
    assert [row["prediction"] for row in rows] == [0.0, 1.0, 1.0]
    assert [row["score"] for row in rows] == pytest.approx([0.2, 0.5, 0.9])
