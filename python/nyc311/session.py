"""Build the local SparkSession."""
from __future__ import annotations

from pyspark.sql import SparkSession

SHUFFLE_PARTITIONS = 16


def get_spark(app_name: str, config: dict[str, str]) -> SparkSession:
    """Build a local SparkSession with the master and memory from the config."""
    spark = (
        SparkSession.builder.appName(app_name)
        .master(config["spark_master"])
        .config("spark.driver.memory", config["spark_driver_memory"])
        .config("spark.sql.shuffle.partitions", str(SHUFFLE_PARTITIONS))
        .config("spark.sql.ansi.enabled", "false")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    return spark
