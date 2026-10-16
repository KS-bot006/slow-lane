"""Metrics of the slow class: counts, accuracy, precision, recall, F1, and AUC."""
from __future__ import annotations

from collections.abc import Sequence

from pyspark.ml.evaluation import BinaryClassificationEvaluator
from pyspark.ml.feature import Bucketizer
from pyspark.ml.functions import vector_to_array
from pyspark.sql import Column, DataFrame
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


PR_STEPS = 100
DECILES = 10
QUANTILE_ERROR = 0.001
DECISION_THRESHOLD = 0.5


def slow_probability(probability_col: str = "probability") -> Column:
    """Return the slow probability: the second value of the probability vector."""
    return vector_to_array(F.col(probability_col))[1]


def precision_recall_rows(
    df: DataFrame, label_col: str, score_col: str
) -> list[dict[str, float]]:
    """Return precision and recall for the thresholds 0.00, 0.01, up to 1.00."""
    actual = F.col(label_col) == 1.0
    sums = [F.sum(F.when(actual, 1).otherwise(0)).alias("positives")]
    for step in range(PR_STEPS + 1):
        predicted = F.col(score_col) >= step / PR_STEPS
        sums.append(F.sum(F.when(predicted, 1).otherwise(0)).alias(f"p{step}"))
        hit = predicted & actual
        sums.append(F.sum(F.when(hit, 1).otherwise(0)).alias(f"t{step}"))
    row = df.agg(*sums).first()
    return [
        {
            "threshold": step / PR_STEPS,
            "precision": _ratio(row[f"t{step}"] or 0, row[f"p{step}"] or 0),
            "recall": _ratio(row[f"t{step}"] or 0, row["positives"] or 0),
        }
        for step in range(PR_STEPS + 1)
    ]


def decile_rows(
    df: DataFrame, label_col: str, score_col: str
) -> list[dict[str, float]]:
    """Sort the rows by score into deciles. Decile 1 holds the riskiest 10 percent."""
    probabilities = [index / DECILES for index in range(1, DECILES)]
    cuts = sorted(set(df.approxQuantile(score_col, probabilities, QUANTILE_ERROR)))
    splits = [float("-inf")] + cuts + [float("inf")]
    bucketizer = Bucketizer(splits=splits, inputCol=score_col, outputCol="bucket")
    bucketed = bucketizer.transform(df)
    groups = bucketed.groupBy("bucket").agg(
        F.count("*").alias("rows"), F.sum(label_col).alias("slow")
    ).collect()
    bucket_count = len(splits) - 1
    by_decile = {bucket_count - int(row["bucket"]): row for row in groups}
    total_rows = sum(row["rows"] for row in groups)
    total_slow = sum(row["slow"] for row in groups)
    overall_share = _ratio(total_slow, total_rows)
    result, cumulative = [], 0.0
    for decile in sorted(by_decile):
        rows, slow = by_decile[decile]["rows"], int(by_decile[decile]["slow"])
        cumulative += _ratio(slow, total_slow)
        result.append({
            "decile": decile,
            "rows": rows,
            "slow_rows": slow,
            "share_of_all_slow": _ratio(slow, total_slow),
            "cumulative_share": cumulative,
            "lift": _ratio(_ratio(slow, rows), overall_share),
        })
    return result


def metrics_by_group(
    df: DataFrame, label_col: str, pred_col: str, group_col: str, top: int
) -> list[dict[str, float | int | str]]:
    """Return the metrics of the groups with the most rows."""
    actual = F.col(label_col) == 1.0
    predicted = F.col(pred_col) == 1.0
    cases = {
        "tp": actual & predicted, "fp": ~actual & predicted,
        "tn": ~actual & ~predicted, "fn": actual & ~predicted,
    }
    sums = [F.sum(F.when(cases[n], 1).otherwise(0)).alias(n) for n in COUNT_NAMES]
    rows = df.groupBy(group_col).agg(F.count("*").alias("rows"), *sums).collect()
    rows = sorted(rows, key=lambda row: (-row["rows"], row[group_col]))[:top]
    result = []
    for row in rows:
        counts = {name: int(row[name]) for name in COUNT_NAMES}
        entry = {group_col: row[group_col], "rows": int(row["rows"])}
        entry["slow_share"] = _ratio(counts["tp"] + counts["fn"], row["rows"])
        entry.update(metrics_from_counts(counts))
        entry.update(counts)
        result.append(entry)
    return result


def group_importances(
    values: Sequence[float],
    lengths: dict[str, int],
    numeric_time: Sequence[str],
    history: Sequence[str],
) -> dict[str, float]:
    """Sum an importance vector by group.

    The vector holds the one-hot slices in the order of the lengths, then the time
    columns, then the history columns. The history columns form the groups h1, h2, h3.
    """
    expected = sum(lengths.values()) + len(numeric_time) + len(history)
    if len(values) != expected:
        raise ValueError(f"The vector has {len(values)} values, expected {expected}.")
    groups: dict[str, float] = {}
    position = 0
    for name, length in lengths.items():
        groups[name] = float(sum(values[position:position + length]))
        position += length
    for name in numeric_time:
        groups[name] = float(values[position])
        position += 1
    for name in history:
        key = name.split("_")[0]
        groups[key] = groups.get(key, 0.0) + float(values[position])
        position += 1
    return groups
