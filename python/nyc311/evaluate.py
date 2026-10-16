"""Metrics of the slow class: counts, accuracy, precision, recall, F1, and AUC."""
from __future__ import annotations

from pyspark.ml.evaluation import BinaryClassificationEvaluator
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

COUNT_NAMES = ("tp", "fp", "tn", "fn")


def confusion_counts(df: DataFrame, label_col: str, pred_col: str) -> dict[str, int]:
    """Count true and false positives and negatives. The slow class is 1.0."""
    actual = F.col(label_col) == 1.0
    predicted = F.col(pred_col) == 1.0
    cases = {
        "tp": actual & predicted,
        "fp": ~actual & predicted,
        "tn": ~actual & ~predicted,
        "fn": actual & ~predicted,
    }
    sums = [
        F.sum(F.when(cases[name], 1).otherwise(0)).alias(name) for name in COUNT_NAMES
    ]
    row = df.agg(*sums).first()
    return {name: int(row[name] or 0) for name in COUNT_NAMES}


def _ratio(numerator: float, denominator: float) -> float:
    """Divide two numbers. A zero denominator gives 0.0."""
    return numerator / denominator if denominator else 0.0


def metrics_from_counts(counts: dict[str, int]) -> dict[str, float]:
    """Return accuracy, precision, recall, and F1 of the slow class."""
    tp, fp, tn, fn = (counts[name] for name in COUNT_NAMES)
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    return {
        "accuracy": _ratio(tp + tn, tp + fp + tn + fn),
        "precision": precision,
        "recall": recall,
        "f1": _ratio(2 * precision * recall, precision + recall),
    }


def auc_scores(df: DataFrame, label_col: str, score_col: str) -> dict[str, float]:
    """Return the area under the ROC curve and under the precision-recall curve."""
    scores = {}
    for key, metric in (("auc_roc", "areaUnderROC"), ("auc_pr", "areaUnderPR")):
        evaluator = BinaryClassificationEvaluator(
            labelCol=label_col, rawPredictionCol=score_col, metricName=metric
        )
        scores[key] = float(evaluator.evaluate(df))
    return scores


def evaluate_scored(
    df: DataFrame, label_col: str, pred_col: str, score_col: str
) -> dict[str, float | int]:
    """Return every metric, the four counts, and the number of rows."""
    counts = confusion_counts(df, label_col, pred_col)
    result: dict[str, float | int] = {}
    result.update(metrics_from_counts(counts))
    result.update(auc_scores(df, label_col, score_col))
    result.update(counts)
    result["test_rows"] = sum(counts.values())
    return result
