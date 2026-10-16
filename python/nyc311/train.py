"""Train the models on the train window and evaluate them on the test window."""
from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import time
from pathlib import Path

from pyspark.ml import PipelineModel
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from nyc311.baselines import baseline_metrics
from nyc311.config import ConfigError, get_float, get_int, load_config
from nyc311.data import (
    CATEGORICAL, LABEL, LeakageError, NUMERIC_HISTORY, NUMERIC_TIME, load_data,
)
from nyc311.evaluate import (
    DECISION_THRESHOLD, decile_rows, evaluate_scored, group_importances,
    metrics_by_group, precision_recall_rows, slow_probability,
)
from nyc311.features import add_weights, build_pipeline, class_weights, encoded_names
from nyc311.models import make_logistic_regression, make_random_forest
from nyc311.session import get_spark

LOGGER = logging.getLogger(__name__)

DEFAULT_PROCESSED = "data/processed"
DEFAULT_RESULTS = "results"
PREDICTIONS_NAME = "predictions_test.parquet"
TOP_AGENCIES = 10
IMPORTANCE_TOLERANCE = 1e-6
MODELS = {
    "logistic_regression": "p_lr",
    "random_forest": "p_rf",
    "random_forest_no_history": "p_rf_nohist",
}
METRIC_COLUMNS = ["accuracy", "precision", "recall", "f1", "auc_roc", "auc_pr",
                  "tp", "fp", "tn", "fn", "test_rows"]
DECILE_COLUMNS = ["decile", "rows", "slow_rows", "share_of_all_slow",
                  "cumulative_share", "lift"]
AGENCY_COLUMNS = ["agency", "rows", "slow_share", "accuracy", "precision", "recall",
                  "f1", "tp", "fp", "tn", "fn"]
CONFIG_KEYS = ["seed", "lr_max_iter", "rf_num_trees", "rf_max_depth",
               "rf_subsampling_rate", "rf_min_instances_per_node",
               "fast_train_fraction", "fast_rf_num_trees", "fast_rf_max_depth"]

Fitted = dict[str, tuple[PipelineModel, float]]


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Read the command line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed", default=DEFAULT_PROCESSED)
    parser.add_argument("--results", default=DEFAULT_RESULTS)
    parser.add_argument("--fast", action="store_true", help="Use less data and trees.")
    return parser.parse_args(argv)


def write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    """Write a CSV file with a header."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def write_dicts(path: Path, header: list[str], rows: list[dict]) -> None:
    """Write a list of dicts as a CSV file with the given columns."""
    write_csv(path, header, [[row[name] for name in header] for row in rows])


def fit_models(train: DataFrame, config: dict[str, str], fast: bool) -> Fitted:
    """Fit the three pipelines. Return each model with its training seconds."""
    plans = {
        "logistic_regression": (make_logistic_regression(config), True),
        "random_forest": (make_random_forest(config, fast), True),
        "random_forest_no_history": (make_random_forest(config, fast), False),
    }
    fitted: Fitted = {}
    for name, (classifier, use_history) in plans.items():
        start = time.perf_counter()
        model = build_pipeline(classifier, use_history).fit(train)
        seconds = time.perf_counter() - start
        print(f"fit {name}: {seconds:.1f} seconds", flush=True)
        fitted[name] = (model, seconds)
    return fitted


def score_test(test: DataFrame, fitted: Fitted) -> DataFrame:
    """Add the slow probability and the prediction of each model to the test rows."""
    scored = test.select("unique_key", LABEL, "agency", "complaint_type", "borough")
    for name, (model, _) in fitted.items():
        column = MODELS[name]
        probabilities = model.transform(test).select(
            "unique_key", slow_probability().alias(column)
        )
        scored = scored.join(probabilities, "unique_key")
        slow = F.col(column) >= DECISION_THRESHOLD
        scored = scored.withColumn(f"pred_{column}", F.when(slow, 1.0).otherwise(0.0))
    return scored


def model_metrics(scored: DataFrame, fitted: Fitted) -> dict[str, dict]:
    """Return the test metrics of each model, with the training seconds."""
    results = {}
    for name, (_, seconds) in fitted.items():
        column = MODELS[name]
        metrics = evaluate_scored(scored, LABEL, f"pred_{column}", column)
        results[name] = {**metrics, "train_seconds": seconds}
    return results


def one_hot_lengths(model: PipelineModel, sample: DataFrame) -> dict[str, int]:
    """Read the length of each one-hot vector from the metadata of its column."""
    frame = sample.limit(1)
    for stage in model.stages[:-1]:
        frame = stage.transform(frame)
    return {
        name: int(frame.schema[column].metadata["ml_attr"]["num_attrs"])
        for name, column in zip(CATEGORICAL, encoded_names())
    }


def importance_rows(model: PipelineModel, test: DataFrame) -> list[list]:
    """Return the feature importance of the Random Forest by group."""
    values = model.stages[-1].featureImportances.toArray()
    groups = group_importances(
        values, one_hot_lengths(model, test), NUMERIC_TIME, NUMERIC_HISTORY
    )
    total = sum(groups.values())
    if abs(total - 1.0) > IMPORTANCE_TOLERANCE:
        raise ValueError(f"The importances sum to {total}, not 1.")
    ordered = sorted(groups.items(), key=lambda item: -item[1])
    return [[name, value] for name, value in ordered]


def write_model_tables(tables: Path, metrics: dict[str, dict]) -> None:
    """Write the metrics of each model and the confusion matrix of the forest."""
    columns = METRIC_COLUMNS + ["train_seconds"]
    write_csv(
        tables / "metrics_by_model.csv", ["model"] + columns,
        [[name] + [entry.get(column, "") for column in columns]
         for name, entry in metrics.items()],
    )
    forest = metrics["random_forest"]
    write_csv(
        tables / "confusion_matrix_rf.csv",
        ["actual", "predicted_not_slow", "predicted_slow"],
        [
            ["not_slow", forest["tn"], forest["fp"]],
            ["slow", forest["fn"], forest["tp"]],
        ],
    )


def write_curve_tables(tables: Path, scored: DataFrame) -> None:
    """Write the precision-recall table and the decile table."""
    curve = []
    for name, column in (("random_forest", "p_rf"), ("logistic_regression", "p_lr")):
        for row in precision_recall_rows(scored, LABEL, column):
            curve.append([name, row["threshold"], row["precision"], row["recall"]])
    header = ["model", "threshold", "precision", "recall"]
    write_csv(tables / "pr_curve.csv", header, curve)
    write_dicts(
        tables / "decile_capture_rf.csv", DECILE_COLUMNS,
        decile_rows(scored, LABEL, "p_rf"),
    )


def write_forest_tables(
    tables: Path, scored: DataFrame, test: DataFrame, forest: PipelineModel
) -> None:
    """Write the agency metrics and the feature importance of the forest."""
    write_dicts(
        tables / "metrics_by_agency_rf.csv", AGENCY_COLUMNS,
        metrics_by_group(scored, LABEL, "pred_p_rf", "agency", TOP_AGENCIES),
    )
    write_csv(
        tables / "feature_importance_groups_rf.csv", ["group", "importance"],
        importance_rows(forest, test),
    )


def write_train_config(
    tables: Path, config: dict[str, str], summary: dict, weights: dict[float, float]
) -> None:
    """Write the settings of this run."""
    rows = [[key, value] for key, value in summary.items()]
    rows += [["decision_threshold", DECISION_THRESHOLD],
             ["weight_not_slow", weights[0.0]], ["weight_slow", weights[1.0]]]
    rows += [[key, config[key]] for key in CONFIG_KEYS]
    write_csv(tables / "train_config.csv", ["key", "value"], rows)


def run(args: argparse.Namespace, config: dict[str, str], spark) -> None:
    """Fit the models, score the test window, and write every result file."""
    processed, results = Path(args.processed), Path(args.results)
    train_full, test = load_data(spark, processed)
    train = train_full
    if args.fast:
        fraction = get_float(config, "fast_train_fraction")
        train = train.sample(fraction, get_int(config, "seed"))
    weights = class_weights(train)
    train, test = add_weights(train).cache(), test.cache()
    print(f"load: train rows {train.count()}, test rows {test.count()}", flush=True)

    fitted = fit_models(train, config, args.fast)
    scored = score_test(test, fitted).cache()
    output = ["unique_key", LABEL, "p_lr", "p_rf", "p_rf_nohist", "agency",
              "complaint_type", "borough"]
    predictions = str((processed / PREDICTIONS_NAME).resolve())
    scored.select(*output).write.mode("overwrite").parquet(predictions)

    metrics = {**baseline_metrics(train_full, test), **model_metrics(scored, fitted)}
    tables = results / "tables"
    write_model_tables(tables, metrics)
    write_curve_tables(tables, scored)
    write_forest_tables(tables, scored, test, fitted["random_forest"][0])
    summary = {
        "train_rows": train.count(), "test_rows": test.count(),
        "slow_threshold_days": get_int(config, "slow_threshold_days"),
        "test_slow_share": test.agg(F.avg(LABEL)).first()[0],
        "fast_mode": args.fast,
    }
    write_train_config(tables, config, summary, weights)
    (results / "metrics.json").write_text(
        json.dumps({**summary, **metrics}, indent=2) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    """Train, evaluate, and write the result files."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    args = parse_args(argv)
    try:
        config = load_config(Path(args.processed))
        spark = get_spark("train", config)
    except ConfigError as error:
        print(f"ERROR {error}", file=sys.stderr)
        return 1
    try:
        run(args, config, spark)
    except LeakageError as error:
        print(f"ERROR {error}", file=sys.stderr)
        return 1
    finally:
        spark.stop()
    print("TRAIN OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
