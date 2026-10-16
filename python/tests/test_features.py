"""Tests for the pipeline stages, the class weights, and the model builders."""
import pytest
from pyspark.ml.feature import OneHotEncoder, StringIndexer, VectorAssembler
from pyspark.sql import SparkSession

from nyc311 import data, features, models


def test_add_weights_uses_n_over_two_times_class_count(spark: SparkSession) -> None:
    """Check the weights for 1 slow row and 3 not slow rows."""
    train = spark.createDataFrame([(1.0,), (0.0,), (0.0,), (0.0,)], "label double")
    rows = features.add_weights(train).collect()
    weight_of = {row["label"]: row["weight"] for row in rows}
    assert weight_of[1.0] == pytest.approx(4 / (2 * 1))
    assert weight_of[0.0] == pytest.approx(4 / (2 * 3))
    assert sum(row["weight"] for row in rows) == pytest.approx(4.0)


def test_add_weights_needs_both_classes(spark: SparkSession) -> None:
    """Check that a train frame with one class stops with an error."""
    train = spark.createDataFrame([(0.0,), (0.0,)], "label double")
    with pytest.raises(ValueError, match="both classes"):
        features.add_weights(train)


def test_pipeline_stages_and_settings() -> None:
    """Check the stage types and the handleInvalid settings."""
    classifier = models.make_random_forest(CONFIG)
    stages = features.build_pipeline(classifier, True).getStages()
    kinds = [type(stage) for stage in stages[:3]]
    assert kinds == [StringIndexer, OneHotEncoder, VectorAssembler]
    assert stages[0].getHandleInvalid() == "keep"
    assert stages[1].getHandleInvalid() == "keep"
    assert stages[2].getHandleInvalid() == "error"
    assert stages[3] is classifier


def test_pipeline_without_history_has_no_history_column() -> None:
    """Check the inputs of the assembler with and without the history columns."""
    classifier = models.make_logistic_regression(CONFIG)
    plain = features.build_pipeline(classifier, False).getStages()
    full = features.build_pipeline(classifier, True).getStages()
    without, with_history = plain[2].getInputCols(), full[2].getInputCols()
    assert not [name for name in without if name.startswith(("h1_", "h2_", "h3_"))]
    assert set(data.NUMERIC_HISTORY) <= set(with_history)
    assert len(with_history) - len(without) == 9
    assert "is_weekend" in without


CONFIG = {
    "seed": "42", "lr_max_iter": "50", "rf_num_trees": "60", "rf_max_depth": "10",
    "rf_subsampling_rate": "0.5", "rf_min_instances_per_node": "20",
    "fast_rf_num_trees": "20", "fast_rf_max_depth": "6",
}


def test_logistic_regression_settings() -> None:
    """Check the weight column, the iterations, and the standardization."""
    model = models.make_logistic_regression(CONFIG)
    assert model.getWeightCol() == "weight"
    assert model.getMaxIter() == 50
    assert model.getStandardization() is True


def test_random_forest_settings_and_fast_mode() -> None:
    """Check the forest settings from the config and the fast values."""
    forest = models.make_random_forest(CONFIG)
    assert (forest.getNumTrees(), forest.getMaxDepth()) == (60, 10)
    assert forest.getFeatureSubsetStrategy() == "sqrt"
    assert forest.getSubsamplingRate() == 0.5
    assert forest.getMinInstancesPerNode() == 20
    assert forest.getSeed() == 42
    fast = models.make_random_forest(CONFIG, fast=True)
    assert (fast.getNumTrees(), fast.getMaxDepth()) == (20, 6)
