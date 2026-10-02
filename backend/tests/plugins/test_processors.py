"""
tests/plugins/test_processors.py
----------------------------------
Unit tests for all built-in processor plugins.

One test class per processor.  Each class constructs a small in-memory
DataFrame (no file I/O) and asserts the exact transformation result.
Tests run entirely in-process — no Docker, no database, no network.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import app.plugins  # noqa: F401 — ensures all plugins are registered

from app.plugins.base import PluginConfigError
from app.plugins.processors.aggregate import Aggregate
from app.plugins.processors.filter_processor import FilterProcessor
from app.plugins.processors.remove_duplicates import RemoveDuplicates
from app.plugins.processors.remove_nulls import RemoveNulls
from app.plugins.processors.rename_columns import RenameColumns
from app.plugins.processors.select_columns import SelectColumns
from app.plugins.processors.type_conversion import TypeConversion


# ── Shared helper ──────────────────────────────────────────────────────────────


def sales_df() -> pd.DataFrame:
    """Small sales DataFrame used across multiple test classes."""
    return pd.DataFrame(
        {
            "transaction_id": ["T1", "T2", "T3", "T1"],
            "amount": [100.0, np.nan, 200.0, 100.0],
            "customer_id": ["C1", "C2", "C1", "C1"],
            "category": ["A", "B", "A", "A"],
        }
    )


# ── RemoveNulls ────────────────────────────────────────────────────────────────


class TestRemoveNulls:
    """RemoveNulls must drop every row that has at least one NaN."""

    def test_reduces_row_count_by_null_rows(self) -> None:
        df = sales_df()
        # Row 1 (T2) has null amount — should be removed
        result = RemoveNulls().process(df, {})
        assert len(result) == 3  # 4 rows − 1 null row

    def test_no_nulls_remain(self) -> None:
        df = sales_df()
        result = RemoveNulls().process(df, {})
        assert result.isnull().sum().sum() == 0

    def test_returns_dataframe(self) -> None:
        result = RemoveNulls().process(sales_df(), {})
        assert isinstance(result, pd.DataFrame)

    def test_all_clean_df_unchanged(self) -> None:
        clean = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        result = RemoveNulls().process(clean, {})
        assert len(result) == 3

    def test_all_null_df_returns_empty(self) -> None:
        all_null = pd.DataFrame({"a": [np.nan, np.nan], "b": [np.nan, np.nan]})
        result = RemoveNulls().process(all_null, {})
        assert len(result) == 0

    def test_plugin_type_is_remove_nulls(self) -> None:
        assert RemoveNulls.plugin_type == "remove_nulls"


# ── RemoveDuplicates ───────────────────────────────────────────────────────────


class TestRemoveDuplicates:
    """RemoveDuplicates must keep the first occurrence of each duplicate set."""

    def test_reduces_row_count_by_duplicates(self) -> None:
        # Drop the null row first so duplicates are truly identical
        df = sales_df().dropna()
        # Rows T1+100.0+C1+A appear at index 0 and 3
        result = RemoveDuplicates().process(df, {})
        assert len(result) == 2  # T1 and T3 (T1 duplicate removed)

    def test_no_duplicates_remain(self) -> None:
        df = sales_df().dropna()
        result = RemoveDuplicates().process(df, {})
        assert result.duplicated().sum() == 0

    def test_index_is_reset(self) -> None:
        df = sales_df().dropna()
        result = RemoveDuplicates().process(df, {})
        assert list(result.index) == list(range(len(result)))

    def test_unique_df_unchanged(self) -> None:
        unique = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        result = RemoveDuplicates().process(unique, {})
        assert len(result) == 3

    def test_plugin_type_is_remove_duplicates(self) -> None:
        assert RemoveDuplicates.plugin_type == "remove_duplicates"


# ── FilterProcessor ────────────────────────────────────────────────────────────


class TestFilterProcessor:
    """FilterProcessor must filter rows by a boolean condition."""

    def test_filters_rows_correctly(self) -> None:
        df = pd.DataFrame({"amount": [10, 20, 30, 40], "status": ["a", "b", "a", "b"]})
        result = FilterProcessor().process(df, {"condition": "amount > 15"})
        assert len(result) == 3
        assert result["amount"].min() == 20

    def test_string_equality_condition(self) -> None:
        df = pd.DataFrame({"status": ["active", "inactive", "active"]})
        result = FilterProcessor().process(df, {"condition": "status == 'active'"})
        assert len(result) == 2

    def test_compound_and_condition(self) -> None:
        df = pd.DataFrame({"x": [1, 5, 10], "y": [100, 50, 10]})
        result = FilterProcessor().process(df, {"condition": "x > 2 and y > 20"})
        assert len(result) == 1
        assert result["x"].iloc[0] == 5

    def test_all_rows_filtered_returns_empty(self) -> None:
        df = pd.DataFrame({"amount": [1.0, 2.0, 3.0]})
        result = FilterProcessor().process(df, {"condition": "amount > 1000"})
        assert len(result) == 0

    def test_missing_condition_raises_plugin_config_error(self) -> None:
        df = pd.DataFrame({"a": [1, 2]})
        with pytest.raises(PluginConfigError):
            FilterProcessor().process(df, {})

    def test_dunder_in_condition_raises_plugin_config_error(self) -> None:
        """Conditions containing '__' must be rejected as unsafe."""
        df = pd.DataFrame({"a": [1, 2]})
        with pytest.raises(PluginConfigError) as exc_info:
            FilterProcessor().process(df, {"condition": "a.__class__ == int"})
        assert "disallowed" in str(exc_info.value).lower() or "__" in str(exc_info.value)

    def test_import_keyword_rejected(self) -> None:
        df = pd.DataFrame({"a": [1]})
        with pytest.raises(PluginConfigError):
            FilterProcessor().process(df, {"condition": "import os"})

    def test_eval_keyword_rejected(self) -> None:
        df = pd.DataFrame({"a": [1]})
        with pytest.raises(PluginConfigError):
            FilterProcessor().process(df, {"condition": "eval('1+1')"})

    def test_exec_keyword_rejected(self) -> None:
        df = pd.DataFrame({"a": [1]})
        with pytest.raises(PluginConfigError):
            FilterProcessor().process(df, {"condition": "exec('pass')"})

    def test_invalid_column_in_condition_raises_plugin_config_error(self) -> None:
        df = pd.DataFrame({"amount": [1, 2, 3]})
        with pytest.raises(PluginConfigError):
            FilterProcessor().process(df, {"condition": "nonexistent_col > 0"})

    def test_plugin_type_is_filter(self) -> None:
        assert FilterProcessor.plugin_type == "filter"


# ── SelectColumns ──────────────────────────────────────────────────────────────


class TestSelectColumns:
    """SelectColumns must return only the requested columns in the requested order."""

    def test_selects_subset_of_columns(self) -> None:
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4], "c": [5, 6]})
        result = SelectColumns().process(df, {"columns": ["a", "c"]})
        assert list(result.columns) == ["a", "c"]
        assert "b" not in result.columns

    def test_preserves_column_order(self) -> None:
        df = pd.DataFrame({"x": [1], "y": [2], "z": [3]})
        result = SelectColumns().process(df, {"columns": ["z", "x"]})
        assert list(result.columns) == ["z", "x"]

    def test_missing_column_raises_with_informative_error(self) -> None:
        df = pd.DataFrame({"a": [1], "b": [2]})
        with pytest.raises(PluginConfigError) as exc_info:
            SelectColumns().process(df, {"columns": ["a", "nonexistent"]})
        assert "nonexistent" in str(exc_info.value)
        assert "a" in str(exc_info.value) or "b" in str(exc_info.value)

    def test_missing_columns_key_raises(self) -> None:
        df = pd.DataFrame({"a": [1]})
        with pytest.raises(PluginConfigError):
            SelectColumns().process(df, {})

    def test_empty_columns_list_raises(self) -> None:
        df = pd.DataFrame({"a": [1]})
        with pytest.raises(PluginConfigError):
            SelectColumns().process(df, {"columns": []})

    def test_row_count_unchanged(self) -> None:
        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        result = SelectColumns().process(df, {"columns": ["a"]})
        assert len(result) == 3

    def test_plugin_type_is_select_columns(self) -> None:
        assert SelectColumns.plugin_type == "select_columns"


# ── RenameColumns ──────────────────────────────────────────────────────────────


class TestRenameColumns:
    """RenameColumns must rename mapped columns and leave others intact."""

    def test_renames_mapped_columns(self) -> None:
        df = pd.DataFrame({"transaction_id": [1, 2], "amount": [10.0, 20.0]})
        result = RenameColumns().process(
            df, {"mapping": {"transaction_id": "txn_id"}}
        )
        assert "txn_id" in result.columns
        assert "transaction_id" not in result.columns

    def test_unmapped_columns_unchanged(self) -> None:
        df = pd.DataFrame({"a": [1], "b": [2], "c": [3]})
        result = RenameColumns().process(df, {"mapping": {"a": "alpha"}})
        assert "b" in result.columns
        assert "c" in result.columns

    def test_missing_mapping_key_raises(self) -> None:
        df = pd.DataFrame({"a": [1]})
        with pytest.raises(PluginConfigError):
            RenameColumns().process(df, {})

    def test_non_dict_mapping_raises(self) -> None:
        df = pd.DataFrame({"a": [1]})
        with pytest.raises(PluginConfigError):
            RenameColumns().process(df, {"mapping": ["a", "b"]})

    def test_renaming_nonexistent_column_is_silently_ignored(self) -> None:
        """pandas.rename silently ignores missing source columns — we preserve this."""
        df = pd.DataFrame({"a": [1], "b": [2]})
        result = RenameColumns().process(df, {"mapping": {"ghost": "phantom"}})
        assert list(result.columns) == ["a", "b"]

    def test_row_count_unchanged(self) -> None:
        df = pd.DataFrame({"col": [1, 2, 3, 4, 5]})
        result = RenameColumns().process(df, {"mapping": {"col": "new_col"}})
        assert len(result) == 5

    def test_plugin_type_is_rename_columns(self) -> None:
        assert RenameColumns.plugin_type == "rename_columns"


# ── TypeConversion ─────────────────────────────────────────────────────────────


class TestTypeConversion:
    """TypeConversion must cast the named column to the requested dtype."""

    def test_converts_to_double(self) -> None:
        df = pd.DataFrame({"amount": ["10.5", "20.0", "30.1"]})
        result = TypeConversion().process(df, {"column": "amount", "to_type": "double"})
        assert pd.api.types.is_float_dtype(result["amount"])

    def test_converts_to_string(self) -> None:
        df = pd.DataFrame({"value": [1, 2, 3]})
        result = TypeConversion().process(df, {"column": "value", "to_type": "string"})
        assert result["value"].dtype == object

    def test_converts_to_integer(self) -> None:
        df = pd.DataFrame({"count": [1.0, 2.0, 3.0]})
        result = TypeConversion().process(df, {"column": "count", "to_type": "integer"})
        # Int64 is the nullable pandas integer dtype
        assert str(result["count"].dtype) == "Int64"

    def test_converts_to_timestamp(self) -> None:
        df = pd.DataFrame({"ts": ["2024-01-01", "2024-01-02"]})
        result = TypeConversion().process(df, {"column": "ts", "to_type": "timestamp"})
        assert pd.api.types.is_datetime64_any_dtype(result["ts"])

    def test_converts_to_boolean(self) -> None:
        df = pd.DataFrame({"flag": [1, 0, 1]})
        result = TypeConversion().process(df, {"column": "flag", "to_type": "boolean"})
        assert pd.api.types.is_bool_dtype(result["flag"])

    def test_other_columns_unchanged(self) -> None:
        df = pd.DataFrame({"amount": ["10.0"], "name": ["Alice"]})
        result = TypeConversion().process(df, {"column": "amount", "to_type": "double"})
        assert result["name"].iloc[0] == "Alice"

    def test_missing_column_key_raises(self) -> None:
        df = pd.DataFrame({"a": [1]})
        with pytest.raises(PluginConfigError):
            TypeConversion().process(df, {"to_type": "double"})

    def test_missing_to_type_key_raises(self) -> None:
        df = pd.DataFrame({"a": [1]})
        with pytest.raises(PluginConfigError):
            TypeConversion().process(df, {"column": "a"})

    def test_nonexistent_column_raises(self) -> None:
        df = pd.DataFrame({"a": [1]})
        with pytest.raises(PluginConfigError) as exc_info:
            TypeConversion().process(df, {"column": "ghost", "to_type": "double"})
        assert "ghost" in str(exc_info.value)

    def test_unknown_type_raises(self) -> None:
        df = pd.DataFrame({"a": [1]})
        with pytest.raises(PluginConfigError) as exc_info:
            TypeConversion().process(df, {"column": "a", "to_type": "matrix"})
        assert "matrix" in str(exc_info.value)

    def test_plugin_type_is_type_conversion(self) -> None:
        assert TypeConversion.plugin_type == "type_conversion"


# ── Aggregate ──────────────────────────────────────────────────────────────────


class TestAggregate:
    """Aggregate must group and reduce the DataFrame to one row per group."""

    @pytest.fixture()
    def multi_customer_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "customer_id": ["C1", "C2", "C1", "C3", "C2"],
                "amount": [100.0, 200.0, 150.0, 300.0, 250.0],
                "count_col": [1, 1, 1, 1, 1],
            }
        )

    def test_sum_produces_correct_values(
        self, multi_customer_df: pd.DataFrame
    ) -> None:
        result = Aggregate().process(
            multi_customer_df,
            {"group_by": "customer_id", "operation": "sum", "field": "amount"},
        )
        by_customer = dict(zip(result["customer_id"], result["amount"]))
        assert by_customer["C1"] == pytest.approx(250.0)
        assert by_customer["C2"] == pytest.approx(450.0)
        assert by_customer["C3"] == pytest.approx(300.0)

    def test_sum_reduces_row_count(self, multi_customer_df: pd.DataFrame) -> None:
        result = Aggregate().process(
            multi_customer_df,
            {"group_by": "customer_id", "operation": "sum", "field": "amount"},
        )
        assert len(result) == 3  # 3 unique customers

    def test_avg_computes_mean(self, multi_customer_df: pd.DataFrame) -> None:
        result = Aggregate().process(
            multi_customer_df,
            {"group_by": "customer_id", "operation": "avg", "field": "amount"},
        )
        by_customer = dict(zip(result["customer_id"], result["amount"]))
        assert by_customer["C1"] == pytest.approx(125.0)
        assert by_customer["C2"] == pytest.approx(225.0)

    def test_count_operation(self, multi_customer_df: pd.DataFrame) -> None:
        result = Aggregate().process(
            multi_customer_df,
            {"group_by": "customer_id", "operation": "count", "field": "amount"},
        )
        by_customer = dict(zip(result["customer_id"], result["amount"]))
        assert by_customer["C1"] == 2
        assert by_customer["C2"] == 2
        assert by_customer["C3"] == 1

    def test_min_operation(self, multi_customer_df: pd.DataFrame) -> None:
        result = Aggregate().process(
            multi_customer_df,
            {"group_by": "customer_id", "operation": "min", "field": "amount"},
        )
        by_customer = dict(zip(result["customer_id"], result["amount"]))
        assert by_customer["C1"] == pytest.approx(100.0)

    def test_max_operation(self, multi_customer_df: pd.DataFrame) -> None:
        result = Aggregate().process(
            multi_customer_df,
            {"group_by": "customer_id", "operation": "max", "field": "amount"},
        )
        by_customer = dict(zip(result["customer_id"], result["amount"]))
        assert by_customer["C2"] == pytest.approx(250.0)

    def test_result_has_two_columns(self, multi_customer_df: pd.DataFrame) -> None:
        result = Aggregate().process(
            multi_customer_df,
            {"group_by": "customer_id", "operation": "sum", "field": "amount"},
        )
        assert list(result.columns) == ["customer_id", "amount"]

    def test_result_index_is_reset(self, multi_customer_df: pd.DataFrame) -> None:
        result = Aggregate().process(
            multi_customer_df,
            {"group_by": "customer_id", "operation": "sum", "field": "amount"},
        )
        assert list(result.index) == list(range(len(result)))

    def test_missing_group_by_raises(self, multi_customer_df: pd.DataFrame) -> None:
        with pytest.raises(PluginConfigError):
            Aggregate().process(
                multi_customer_df, {"operation": "sum", "field": "amount"}
            )

    def test_unknown_operation_raises(self, multi_customer_df: pd.DataFrame) -> None:
        with pytest.raises(PluginConfigError) as exc_info:
            Aggregate().process(
                multi_customer_df,
                {"group_by": "customer_id", "operation": "median", "field": "amount"},
            )
        assert "median" in str(exc_info.value)

    def test_nonexistent_group_by_column_raises(
        self, multi_customer_df: pd.DataFrame
    ) -> None:
        with pytest.raises(PluginConfigError) as exc_info:
            Aggregate().process(
                multi_customer_df,
                {"group_by": "ghost_col", "operation": "sum", "field": "amount"},
            )
        assert "ghost_col" in str(exc_info.value)

    def test_nonexistent_field_column_raises(
        self, multi_customer_df: pd.DataFrame
    ) -> None:
        with pytest.raises(PluginConfigError) as exc_info:
            Aggregate().process(
                multi_customer_df,
                {"group_by": "customer_id", "operation": "sum", "field": "ghost_field"},
            )
        assert "ghost_field" in str(exc_info.value)

    def test_plugin_type_is_aggregate(self) -> None:
        assert Aggregate.plugin_type == "aggregate"
