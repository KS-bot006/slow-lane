"""Build the classifiers with the settings from the config."""
from __future__ import annotations

from pyspark.ml.classification import LogisticRegression, RandomForestClassifier

from nyc311.config import get_float, get_int
from nyc311.data import LABEL
from nyc311.features import FEATURES_VECTOR, WEIGHT


def make_logistic_regression(config: dict[str, str]) -> LogisticRegression:
    """Build the Logistic Regression with class weights and standardization."""
    return LogisticRegression(
        featuresCol=FEATURES_VECTOR,
        labelCol=LABEL,
        weightCol=WEIGHT,
        maxIter=get_int(config, "lr_max_iter"),
        standardization=True,
    )


def make_random_forest(
    config: dict[str, str], fast: bool = False
) -> RandomForestClassifier:
    """Build the Random Forest. Fast mode uses fewer and shallower trees."""
    prefix = "fast_rf" if fast else "rf"
    return RandomForestClassifier(
        featuresCol=FEATURES_VECTOR,
        labelCol=LABEL,
        weightCol=WEIGHT,
        featureSubsetStrategy="sqrt",
        numTrees=get_int(config, f"{prefix}_num_trees"),
        maxDepth=get_int(config, f"{prefix}_max_depth"),
        subsamplingRate=get_float(config, "rf_subsampling_rate"),
        minInstancesPerNode=get_int(config, "rf_min_instances_per_node"),
        seed=get_int(config, "seed"),
    )
