"""
spark-jobs/tests/test_filter_ops.py
--------------------------------------
Unit tests for spark-jobs/operations/filter_ops.py.

Verifies that ``apply_filter`` correctly retains/excludes rows and that the
injection guard raises ``ValueError`` on dangerous patterns.
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from pyspark.sql import SparkSession, Row

from operations.filter_ops import apply_filter, _check_condition


class TestApplyFilter:
    """Tests for ``apply_filter``."""

    def test_numeric_gt_filter(self, spark: SparkSession) -> None:
        """Rows below threshold must be excluded."""
        df = spark.createDataFrame(
            [Row(amount=5.0), Row(amount=-1.0), Row(amount=0.0), Row(amount=100.0)]
        )
        result = apply_filter(df, "amount > 0")
        values = sorted(r.amount for r in result.collect())
        assert values == [5.0, 100.0]

    def test_string_equality_filter(self, spark: SparkSession) -> None:
        """String equality filter must keep only matching rows."""
        df = spark.createDataFrame(
            [Row(status="active"), Row(status="inactive"), Row(status="active")]
        )
        result = apply_filter(df, "status = 'active'")
        assert result.count() == 2

    def test_filter_that_keeps_all(self, spark: SparkSession) -> None:
        """Filter that matches every row must return all rows."""
        df = spark.createDataFrame([Row(a=1), Row(a=2), Row(a=3)])
        result = apply_filter(df, "a > 0")
        assert result.count() == 3

    def test_filter_that_keeps_none(self, spark: SparkSession) -> None:
        """Filter that matches nothing must return an empty DataFrame."""
        df = spark.createDataFrame([Row(a=1), Row(a=2)])
        result = apply_filter(df, "a > 100")
        assert result.count() == 0

    def test_complex_and_condition(self, spark: SparkSession) -> None:
        """Compound AND condition must be applied correctly."""
        df = spark.createDataFrame(
            [Row(a=5, b=10), Row(a=3, b=10), Row(a=5, b=2)]
        )
        result = apply_filter(df, "a > 4 AND b > 5")
        assert result.count() == 1
        assert result.first().a == 5

    def test_empty_dataframe_returns_empty(self, spark: SparkSession) -> None:
        """Filtering an empty DataFrame must return an empty DataFrame."""
        df = spark.createDataFrame([], schema="a INT")
        result = apply_filter(df, "a > 0")
        assert result.count() == 0


class TestInjectionGuard:
    """Tests for the ``_check_condition`` injection guard."""

    @pytest.mark.parametrize(
        "bad_condition",
        [
            "a.__class__",
            "import os",
            "exec('rm -rf /')",
            "eval('1+1')",
            "__import__('os')",
        ],
    )
    def test_banned_patterns_raise_value_error(self, bad_condition: str) -> None:
        """Any banned substring in the condition must raise ValueError."""
        with pytest.raises(ValueError, match="forbidden pattern"):
            _check_condition(bad_condition)

    def test_safe_condition_passes(self) -> None:
        """Legitimate Spark SQL expressions must not be rejected."""
        _check_condition("amount > 0")  # must not raise
        _check_condition("status = 'active'")
        _check_condition("a > 4 AND b > 5")
