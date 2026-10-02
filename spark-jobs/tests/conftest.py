"""
spark-jobs/tests/conftest.py
-----------------------------
Shared pytest fixtures for spark-jobs unit tests.

Creates a single local-mode SparkSession for the entire test session and
tears it down when done.  Tests run without a Docker Spark cluster.
"""

from __future__ import annotations

import pytest
from pyspark.sql import SparkSession


@pytest.fixture(scope="session")
def spark() -> SparkSession:
    """
    Create a local-mode SparkSession for the test session.

    Using ``local[2]`` gives 2 executor threads so tests finish quickly
    while still exercising parallel execution paths.
    """
    session = (
        SparkSession.builder.master("local[2]")
        .appName("spark-jobs-unit-tests")
        # Suppress verbose INFO logs from Spark itself
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "2")
        .getOrCreate()
    )
    session.sparkContext.setLogLevel("WARN")
    yield session
    session.stop()
