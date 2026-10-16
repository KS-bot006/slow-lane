"""Score the majority-class baseline and the history-rule baseline."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from nyc311.config import ConfigError, get_float, get_int, load_config
from nyc311.data import LABEL, LeakageError, load_data
from nyc311.evaluate import evaluate_scored
from nyc311.session import get_spark

LOGGER = logging.getLogger(__name__)

DEFAULT_PROCESSED = "data/processed"
DEFAULT_OUTPUT = "results/metrics_baselines.json"
MAJORITY_SHARE = 0.5
RULE_COLUMN = "h1_slow_rate"
RULE_THRESHOLD = 0.5
PREDICTION = "prediction"
SCORE = "score"


def majority_label(train: DataFrame) -> float:
    """Return the most frequent label of the train window: 1.0 or 0.0."""
    share = train.agg(F.avg(LABEL).alias("share")).first()["share"]
    return 1.0 if share > MAJORITY_SHARE else 0.0


def with_majority(df: DataFrame, label: float) -> DataFrame:
    """Add the majority prediction. The score is a constant."""
    return df.withColumn(PREDICTION, F.lit(label)).withColumn(SCORE, F.lit(label))


def with_history_rule(df: DataFrame) -> DataFrame:
    """Predict slow when h1_slow_rate is at least 0.5. The score is h1_slow_rate."""
    rule = F.when(F.col(RULE_COLUMN) >= RULE_THRESHOLD, 1.0).otherwise(0.0)
    return df.withColumn(PREDICTION, rule).withColumn(SCORE, F.col(RULE_COLUMN))


def baseline_metrics(train: DataFrame, test: DataFrame) -> dict[str, dict]:
    """Return the test metrics of the majority baseline and the history rule."""
    label = majority_label(train)
    return {
        "majority": {
            "label": label,
            **evaluate_scored(with_majority(test, label), LABEL, PREDICTION, SCORE),
        },
        "history_rule": evaluate_scored(
            with_history_rule(test), LABEL, PREDICTION, SCORE
        ),
    }


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Read the command line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed", default=DEFAULT_PROCESSED)
    parser.add_argument("--out", default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Score both baselines on the test window and write the metrics file."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    args = parse_args(argv)
    processed = Path(args.processed)
    try:
        config = load_config(processed)
        spark = get_spark("baselines", config)
        train, test = load_data(spark, processed)
    except (ConfigError, LeakageError) as error:
        print(f"ERROR {error}", file=sys.stderr)
        return 1
    try:
        test = test.cache()
        results = {
            "slow_threshold_days": get_int(config, "slow_threshold_days"),
            "history_slow_share": get_float(config, "history_slow_share"),
            "test_slow_share": test.agg(F.avg(LABEL)).first()[0],
            **baseline_metrics(train, test),
        }
        majority = results["majority"]
        print(f"majority label: {majority['label']}, rows: {majority['test_rows']}")
        output = Path(args.out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {output}")
    finally:
        spark.stop()
    print("BASELINES OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
