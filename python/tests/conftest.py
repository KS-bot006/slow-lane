"""Shared fixtures. The Spark session lives for one test module."""
from collections.abc import Iterator

import pytest
from pyspark.sql import SparkSession


@pytest.fixture(scope="module")
def spark() -> Iterator[SparkSession]:
    """Start a small local SparkSession for a test module."""
    session = (
        SparkSession.builder.master("local[2]")
        .appName("nyc311-tests")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.sql.ansi.enabled", "false")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()
