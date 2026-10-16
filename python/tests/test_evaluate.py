"""Tests for the metric functions. The frames hold fixture rows."""
import pytest
from pyspark.sql import SparkSession

from nyc311 import evaluate


def test_metrics_from_known_counts() -> None:
    """Check the metrics for tp 6, fp 2, tn 10, and fn 2."""
    metrics = evaluate.metrics_from_counts({"tp": 6, "fp": 2, "tn": 10, "fn": 2})
    assert metrics["accuracy"] == pytest.approx(0.8)
    assert metrics["precision"] == pytest.approx(0.75)
    assert metrics["recall"] == pytest.approx(0.75)
    assert metrics["f1"] == pytest.approx(0.75)


def test_zero_denominators_give_zero() -> None:
    """Check that a zero denominator gives 0.0 and not an error."""
    metrics = evaluate.metrics_from_counts({"tp": 0, "fp": 0, "tn": 5, "fn": 0})
    assert metrics == {"accuracy": 1.0, "precision": 0.0, "recall": 0.0, "f1": 0.0}
    empty = evaluate.metrics_from_counts({"tp": 0, "fp": 0, "tn": 0, "fn": 0})
    assert empty["accuracy"] == 0.0


def test_confusion_counts(spark: SparkSession) -> None:
    """Check the four counts on a small frame."""
    rows = [(1.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 1.0), (0.0, 0.0), (0.0, 0.0)]
    df = spark.createDataFrame(rows, "label double, prediction double")
    counts = evaluate.confusion_counts(df, "label", "prediction")
    assert counts == {"tp": 2, "fp": 1, "tn": 2, "fn": 1}


def test_auc_of_a_perfect_and_a_constant_score(spark: SparkSession) -> None:
    """Check that a perfect score gives 1.0 and a constant score gives 0.5."""
    rows = [(1.0, 0.9, 0.0), (1.0, 0.8, 0.0), (0.0, 0.2, 0.0), (0.0, 0.1, 0.0)]
    df = spark.createDataFrame(rows, "label double, good double, flat double")
    assert evaluate.auc_scores(df, "label", "good")["auc_roc"] == pytest.approx(1.0)
    assert evaluate.auc_scores(df, "label", "flat")["auc_roc"] == pytest.approx(0.5)


def test_evaluate_scored_has_every_entry(spark: SparkSession) -> None:
    """Check the keys of the result and the number of rows."""
    rows = [(1.0, 1.0, 0.9), (0.0, 0.0, 0.1), (1.0, 0.0, 0.4), (0.0, 1.0, 0.6)]
    df = spark.createDataFrame(rows, "label double, prediction double, score double")
    result = evaluate.evaluate_scored(df, "label", "prediction", "score")
    expected = {"accuracy", "precision", "recall", "f1", "auc_roc", "auc_pr",
                "tp", "fp", "tn", "fn", "test_rows"}
    assert set(result) == expected
    assert result["test_rows"] == 4
