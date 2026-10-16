"""Build the Spark ML pipeline and the class weights."""
from __future__ import annotations

from pyspark.ml import Pipeline
from pyspark.ml.feature import OneHotEncoder, StringIndexer, VectorAssembler
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from nyc311.data import CATEGORICAL, LABEL, NUMERIC_HISTORY, NUMERIC_TIME

WEIGHT = "weight"
FEATURES_VECTOR = "features"
CLASSES_COUNT = 2


def indexed_names() -> list[str]:
    """Return the names of the indexed categorical columns."""
    return [f"{name}_idx" for name in CATEGORICAL]


def encoded_names() -> list[str]:
    """Return the names of the one-hot columns."""
    return [f"{name}_ohe" for name in CATEGORICAL]


def assembler_inputs(use_history: bool) -> list[str]:
    """Return the input columns of the vector assembler."""
    inputs = encoded_names() + NUMERIC_TIME
    return inputs + NUMERIC_HISTORY if use_history else inputs


def class_weights(train: DataFrame) -> dict[float, float]:
    """Return the weight of each class: n divided by (2 times n_c)."""
    rows = train.groupBy(LABEL).count().collect()
    counts = {row[LABEL]: row["count"] for row in rows}
    if set(counts) != {0.0, 1.0}:
        raise ValueError(f"The train data needs both classes. Found {sorted(counts)}.")
    total = sum(counts.values())
    return {label: total / (CLASSES_COUNT * count) for label, count in counts.items()}


def add_weights(train: DataFrame) -> DataFrame:
    """Add the column weight so that both classes count the same."""
    weights = class_weights(train)
    column = F.when(F.col(LABEL) == 1.0, weights[1.0]).otherwise(weights[0.0])
    return train.withColumn(WEIGHT, column)


def build_pipeline(classifier, use_history: bool) -> Pipeline:
    """Build the pipeline: index, one-hot encode, assemble, and classify."""
    indexer = StringIndexer(
        inputCols=CATEGORICAL, outputCols=indexed_names(), handleInvalid="keep"
    )
    encoder = OneHotEncoder(
        inputCols=indexed_names(), outputCols=encoded_names(), handleInvalid="keep"
    )
    assembler = VectorAssembler(
        inputCols=assembler_inputs(use_history),
        outputCol=FEATURES_VECTOR,
        handleInvalid="error",
    )
    return Pipeline(stages=[indexer, encoder, assembler, classifier])
