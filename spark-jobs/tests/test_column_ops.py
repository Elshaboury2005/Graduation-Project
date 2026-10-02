"""
spark-jobs/tests/test_column_ops.py
--------------------------------------
Unit tests for spark-jobs/operations/column_ops.py.

Verifies select_columns, rename_columns, and convert_type against small
in-memory Spark DataFrames.
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from pyspark.sql import SparkSession, Row

from operations.column_ops import select_columns, rename_columns, convert_type


class TestSelectColumns:
    """Tests for ``select_columns``."""

    def test_keeps_requested_columns_only(self, spark: SparkSession) -> None:
        """Only the requested columns must appear in the result."""
        df = spark.createDataFrame([Row(a=1, b=2, c=3)])
        result = select_columns(df, ["a", "c"])
        assert result.columns == ["a", "c"]
        assert result.count() == 1

    def test_single_column_select(self, spark: SparkSession) -> None:
        """Selecting a single column must work."""
        df = spark.createDataFrame([Row(x=10, y=20)])
        result = select_columns(df, ["x"])
        assert result.columns == ["x"]

    def test_preserves_row_count(self, spark: SparkSession) -> None:
        """Row count must not change after selection."""
        df = spark.createDataFrame([Row(a=1, b=2), Row(a=3, b=4), Row(a=5, b=6)])
        result = select_columns(df, ["a"])
        assert result.count() == 3

    def test_missing_column_raises_value_error(self, spark: SparkSession) -> None:
        """Requesting a non-existent column must raise ValueError."""
        df = spark.createDataFrame([Row(a=1)])
        with pytest.raises(ValueError, match="not found"):
            select_columns(df, ["a", "nonexistent"])

    def test_preserves_column_order(self, spark: SparkSession) -> None:
        """The output column order must follow the requested list order."""
        df = spark.createDataFrame([Row(a=1, b=2, c=3)])
        result = select_columns(df, ["c", "a"])
        assert result.columns == ["c", "a"]


class TestRenameColumns:
    """Tests for ``rename_columns``."""

    def test_renames_specified_columns(self, spark: SparkSession) -> None:
        """Columns in the mapping must be renamed."""
        df = spark.createDataFrame([Row(old_name=1, other=2)])
        result = rename_columns(df, {"old_name": "new_name"})
        assert "new_name" in result.columns
        assert "old_name" not in result.columns

    def test_untouched_columns_unchanged(self, spark: SparkSession) -> None:
        """Columns not in the mapping must retain their names."""
        df = spark.createDataFrame([Row(a=1, b=2)])
        result = rename_columns(df, {"a": "alpha"})
        assert "b" in result.columns
        assert "alpha" in result.columns

    def test_multi_column_rename(self, spark: SparkSession) -> None:
        """Renaming multiple columns at once must work."""
        df = spark.createDataFrame([Row(x=1, y=2)])
        result = rename_columns(df, {"x": "new_x", "y": "new_y"})
        assert set(result.columns) == {"new_x", "new_y"}

    def test_missing_source_column_raises(self, spark: SparkSession) -> None:
        """Mapping a non-existent source column must raise ValueError."""
        df = spark.createDataFrame([Row(a=1)])
        with pytest.raises(ValueError, match="not found"):
            rename_columns(df, {"nonexistent": "new"})

    def test_empty_mapping_returns_unchanged(self, spark: SparkSession) -> None:
        """An empty mapping must leave the DataFrame unchanged."""
        df = spark.createDataFrame([Row(a=1, b=2)])
        result = rename_columns(df, {})
        assert result.columns == ["a", "b"]


class TestConvertType:
    """Tests for ``convert_type``."""

    def test_string_to_integer(self, spark: SparkSession) -> None:
        """String values that represent integers must be cast correctly."""
        df = spark.createDataFrame([Row(val="42"), Row(val="7")])
        result = convert_type(df, "val", "integer")
        rows = sorted(r.val for r in result.collect())
        assert rows == [7, 42]

    def test_integer_to_double(self, spark: SparkSession) -> None:
        """Integer column cast to double must produce float values."""
        df = spark.createDataFrame([Row(n=3)])
        result = convert_type(df, "n", "double")
        val = result.first().n
        assert isinstance(val, float)

    def test_integer_to_string(self, spark: SparkSession) -> None:
        """Integer cast to string must produce string values."""
        df = spark.createDataFrame([Row(n=5)])
        result = convert_type(df, "n", "string")
        assert result.first().n == "5"

    def test_missing_column_raises(self, spark: SparkSession) -> None:
        """Casting a non-existent column must raise ValueError."""
        df = spark.createDataFrame([Row(a=1)])
        with pytest.raises(ValueError, match="not found"):
            convert_type(df, "nonexistent", "string")

    def test_unsupported_type_raises(self, spark: SparkSession) -> None:
        """Requesting an unsupported target type must raise ValueError."""
        df = spark.createDataFrame([Row(a=1)])
        with pytest.raises(ValueError, match="unsupported type"):
            convert_type(df, "a", "bigint")  # type: ignore[arg-type]
