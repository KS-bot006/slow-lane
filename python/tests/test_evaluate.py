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


def test_group_importances_sum_by_group() -> None:
    """Check the slices of the importance vector and the three history groups."""
    values = [0.1, 0.1, 0.2, 0.05, 0.05, 0.1, 0.1, 0.1, 0.05, 0.05, 0.1]
    lengths = {"agency": 2, "borough": 3}
    history = ["h1_slow_rate", "h1_log_n", "h2_slow_rate", "h2_log_n", "h3_log_n"]
    groups = evaluate.group_importances(values, lengths, ["is_weekend"], history)
    assert groups["agency"] == pytest.approx(0.2)
    assert groups["borough"] == pytest.approx(0.3)
    assert groups["is_weekend"] == pytest.approx(0.1)
    assert groups["h1"] == pytest.approx(0.2)
    assert groups["h2"] == pytest.approx(0.1)
    assert groups["h3"] == pytest.approx(0.1)
    assert sum(groups.values()) == pytest.approx(1.0)


def test_group_importances_rejects_a_wrong_length() -> None:
    """Check that a vector of the wrong length stops with an error."""
    with pytest.raises(ValueError, match="expected"):
        evaluate.group_importances([0.5, 0.5], {"agency": 3}, [], [])


def test_decile_rows_rank_the_riskiest_first(spark: SparkSession) -> None:
    """Check the decile table on 100 rows where the score orders the labels."""
    rows = [(1.0 if i >= 80 else 0.0, i / 100.0) for i in range(100)]
    df = spark.createDataFrame(rows, "label double, score double")
    table = evaluate.decile_rows(df, "label", "score")
    assert [row["decile"] for row in table] == list(range(1, 11))
    assert table[0]["slow_rows"] == table[0]["rows"]
    assert table[1]["cumulative_share"] > 0.9
    assert table[-1]["cumulative_share"] == pytest.approx(1.0)
    assert table[0]["lift"] == pytest.approx(5.0)
    assert sum(row["rows"] for row in table) == 100


def test_precision_recall_rows_have_101_thresholds(spark: SparkSession) -> None:
    """Check the thresholds, a precision of 1.0, and the end values."""
    rows = [(1.0, 0.9), (1.0, 0.8), (0.0, 0.3), (0.0, 0.1)]
    df = spark.createDataFrame(rows, "label double, score double")
    table = evaluate.precision_recall_rows(df, "label", "score")
    assert len(table) == 101
    assert table[0]["threshold"] == 0.0 and table[100]["threshold"] == 1.0
    assert table[0]["recall"] == 1.0 and table[0]["precision"] == pytest.approx(0.5)
    assert table[50]["precision"] == 1.0 and table[50]["recall"] == 1.0
    assert table[100]["precision"] == 0.0 and table[100]["recall"] == 0.0


def test_metrics_by_group_keeps_the_largest_groups(spark: SparkSession) -> None:
    """Check that the top groups come first, with their counts."""
    rows = [("A", 1.0, 1.0), ("A", 0.0, 0.0), ("A", 1.0, 0.0), ("B", 1.0, 1.0)]
    df = spark.createDataFrame(rows, "agency string, label double, pred double")
    table = evaluate.metrics_by_group(df, "label", "pred", "agency", top=1)
    assert [row["agency"] for row in table] == ["A"]
    assert (table[0]["tp"], table[0]["fn"], table[0]["tn"]) == (1, 1, 1)
    assert table[0]["slow_share"] == pytest.approx(2 / 3)
