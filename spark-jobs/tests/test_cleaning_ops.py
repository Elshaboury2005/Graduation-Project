"""
spark-jobs/tests/test_cleaning_ops.py
---------------------------------------
Unit tests for spark-jobs/operations/cleaning_ops.py.

Verifies that ``remove_nulls`` and ``remove_duplicates`` produce exact
expected row counts and values using a local-mode SparkSession.
"""

from __future__ import annotations

import sys
import os

# Allow importing from the spark-jobs root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from pyspark.sql import SparkSession, Row

from operations.cleaning_ops import remove_nulls, remove_duplicates


class TestRemoveNulls:
    """Tests for ``remove_nulls``."""

    def test_removes_rows_with_any_null(self, spark: SparkSession) -> None:
        """Row containing at least one null must be dropped."""
        df = spark.createDataFrame(
            [
                Row(a=1, b="x"),
                Row(a=None, b="y"),
                Row(a=3, b=None),
                Row(a=4, b="z"),
            ]
        )
        result = remove_nulls(df)
        assert result.count() == 2
        rows = {(r.a, r.b) for r in result.collect()}
        assert rows == {(1, "x"), (4, "z")}

    def test_all_nulls_returns_empty(self, spark: SparkSession) -> None:
        """DataFrame where every row has a null → empty result."""
        df = spark.createDataFrame([Row(a=None, b=None), Row(a=None, b="x")])
        # second row has b="x" so only first is fully null, but a=None → dropped
        result = remove_nulls(df)
        # Row(a=None, b="x") still has null in column a, so it should be dropped
        assert result.count() == 0

    def test_no_nulls_returns_all_rows(self, spark: SparkSession) -> None:
        """DataFrame with no nulls must be returned unchanged."""
        df = spark.createDataFrame([Row(a=1, b="x"), Row(a=2, b="y")])
        result = remove_nulls(df)
        assert result.count() == 2

    def test_preserves_column_names(self, spark: SparkSession) -> None:
        """Column names must not be altered by the operation."""
        df = spark.createDataFrame([Row(col1=1, col2="ok")])
        result = remove_nulls(df)
        assert result.columns == ["col1", "col2"]

    def test_empty_dataframe_returns_empty(self, spark: SparkSession) -> None:
        """Empty input must produce empty output."""
        df = spark.createDataFrame([], schema="a INT, b STRING")
        result = remove_nulls(df)
        assert result.count() == 0


class TestRemoveDuplicates:
    """Tests for ``remove_duplicates``."""

    def test_removes_exact_duplicates(self, spark: SparkSession) -> None:
        """Identical rows must be collapsed to one."""
        df = spark.createDataFrame(
            [Row(a=1, b="x"), Row(a=1, b="x"), Row(a=2, b="y")]
        )
        result = remove_duplicates(df)
        assert result.count() == 2

    def test_all_unique_rows_unchanged(self, spark: SparkSession) -> None:
        """No duplicates → all rows retained."""
        df = spark.createDataFrame([Row(a=1), Row(a=2), Row(a=3)])
        result = remove_duplicates(df)
        assert result.count() == 3

    def test_all_duplicates_returns_one(self, spark: SparkSession) -> None:
        """All identical rows → exactly one row returned."""
        df = spark.createDataFrame([Row(a=99), Row(a=99), Row(a=99)])
        result = remove_duplicates(df)
        assert result.count() == 1

    def test_empty_dataframe_returns_empty(self, spark: SparkSession) -> None:
        """Empty input must produce empty output."""
        df = spark.createDataFrame([], schema="a INT")
        result = remove_duplicates(df)
        assert result.count() == 0

    def test_preserves_column_order(self, spark: SparkSession) -> None:
        """Column order must be preserved after deduplication."""
        df = spark.createDataFrame([Row(x=1, y=2, z=3)])
        result = remove_duplicates(df)
        assert result.columns == ["x", "y", "z"]
