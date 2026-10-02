"""
spark-jobs/tests/test_aggregate_ops.py
-----------------------------------------
Unit tests for spark-jobs/operations/aggregate_ops.py.

Verifies all five aggregation operations (sum, avg, count, min, max)
against small in-memory Spark DataFrames.
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from pyspark.sql import SparkSession, Row

from operations.aggregate_ops import aggregate


class TestAggregate:
    """Tests for ``aggregate``."""

    def _make_sales_df(self, spark: SparkSession):
        """Helper: create a simple sales DataFrame for testing."""
        return spark.createDataFrame(
            [
                Row(customer="alice", amount=100.0),
                Row(customer="alice", amount=50.0),
                Row(customer="bob", amount=200.0),
                Row(customer="bob", amount=80.0),
                Row(customer="charlie", amount=30.0),
            ]
        )

    def test_sum_aggregation(self, spark: SparkSession) -> None:
        """Sum per group must equal the expected totals."""
        df = self._make_sales_df(spark)
        result = aggregate(df, group_by="customer", operation="sum", field="amount")
        rows = {r.customer: r.sum_amount for r in result.collect()}
        assert rows["alice"] == pytest.approx(150.0)
        assert rows["bob"] == pytest.approx(280.0)
        assert rows["charlie"] == pytest.approx(30.0)

    def test_avg_aggregation(self, spark: SparkSession) -> None:
        """Average per group must be computed correctly."""
        df = self._make_sales_df(spark)
        result = aggregate(df, group_by="customer", operation="avg", field="amount")
        rows = {r.customer: r.avg_amount for r in result.collect()}
        assert rows["alice"] == pytest.approx(75.0)
        assert rows["bob"] == pytest.approx(140.0)

    def test_min_aggregation(self, spark: SparkSession) -> None:
        """Minimum per group must be correct."""
        df = self._make_sales_df(spark)
        result = aggregate(df, group_by="customer", operation="min", field="amount")
        rows = {r.customer: r.min_amount for r in result.collect()}
        assert rows["alice"] == pytest.approx(50.0)
        assert rows["bob"] == pytest.approx(80.0)

    def test_max_aggregation(self, spark: SparkSession) -> None:
        """Maximum per group must be correct."""
        df = self._make_sales_df(spark)
        result = aggregate(df, group_by="customer", operation="max", field="amount")
        rows = {r.customer: r.max_amount for r in result.collect()}
        assert rows["alice"] == pytest.approx(100.0)
        assert rows["bob"] == pytest.approx(200.0)

    def test_count_aggregation_ignores_field(self, spark: SparkSession) -> None:
        """Count must return per-group row counts; field argument is ignored."""
        df = self._make_sales_df(spark)
        result = aggregate(df, group_by="customer", operation="count", field="amount")
        rows = {r.customer: r["count"] for r in result.collect()}
        assert rows["alice"] == 2
        assert rows["bob"] == 2
        assert rows["charlie"] == 1

    def test_result_has_expected_columns(self, spark: SparkSession) -> None:
        """Sum result must have group_by column + aggregate alias column."""
        df = self._make_sales_df(spark)
        result = aggregate(df, group_by="customer", operation="sum", field="amount")
        assert "customer" in result.columns
        assert "sum_amount" in result.columns

    def test_missing_group_by_column_raises(self, spark: SparkSession) -> None:
        """Referencing a non-existent group_by column must raise ValueError."""
        df = self._make_sales_df(spark)
        with pytest.raises(ValueError, match="not found"):
            aggregate(df, group_by="nonexistent", operation="sum", field="amount")

    def test_missing_field_column_raises(self, spark: SparkSession) -> None:
        """Referencing a non-existent field column must raise ValueError."""
        df = self._make_sales_df(spark)
        with pytest.raises(ValueError, match="not found"):
            aggregate(df, group_by="customer", operation="sum", field="nonexistent")

    def test_unsupported_operation_raises(self, spark: SparkSession) -> None:
        """Requesting an unsupported aggregation function must raise ValueError."""
        df = self._make_sales_df(spark)
        with pytest.raises(ValueError, match="unsupported operation"):
            aggregate(df, group_by="customer", operation="median", field="amount")  # type: ignore[arg-type]

    def test_count_missing_group_by_raises(self, spark: SparkSession) -> None:
        """Count with a missing group_by must still raise ValueError."""
        df = self._make_sales_df(spark)
        with pytest.raises(ValueError, match="not found"):
            aggregate(df, group_by="nope", operation="count", field="amount")
