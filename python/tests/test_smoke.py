"""Smoke test: a local SparkSession runs a small job."""
from pyspark.sql import SparkSession

ROW_COUNT = 100


def test_spark_range_count() -> None:
    """Check that a local SparkSession counts 100 rows."""
    spark = SparkSession.builder.master("local[2]").appName("smoke-test").getOrCreate()
    try:
        assert spark.range(ROW_COUNT).count() == ROW_COUNT
    finally:
        spark.stop()
