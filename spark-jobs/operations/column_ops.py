"""
spark-jobs/operations/column_ops.py
--------------------------------------
PySpark DataFrame column manipulation operations.

Provides select, rename, and type-conversion helpers that mirror Phase 3's
pandas column processors but use the Spark DataFrame API.
"""

from __future__ import annotations

import logging
from typing import Literal

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import (
    BooleanType,
    DoubleType,
    IntegerType,
    StringType,
    TimestampType,
)

logger = logging.getLogger(__name__)

# ── Type mapping ───────────────────────────────────────────────────────────────

ColumnTypeName = Literal["string", "integer", "double", "boolean", "timestamp"]

_SPARK_TYPE_MAP: dict[str, object] = {
    "string": StringType(),
    "integer": IntegerType(),
    "double": DoubleType(),
    "boolean": BooleanType(),
    "timestamp": TimestampType(),
}


def select_columns(df: DataFrame, columns: list[str]) -> DataFrame:
    """
    Retain only the specified columns, in the given order.

    Parameters
    ----------
    df : DataFrame
        Input Spark DataFrame.
    columns : list[str]
        Names of columns to keep.

    Returns
    -------
    DataFrame
        Projected DataFrame containing only *columns*.

    Raises
    ------
    ValueError
        If any requested column does not exist in *df*.
    """
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(
            f"select_columns: columns {missing} not found in DataFrame. "
            f"Available: {df.columns}"
        )
    result = df.select(columns)
    logger.info("select_columns: kept %d of %d columns", len(columns), len(df.columns))
    return result


def rename_columns(df: DataFrame, mapping: dict[str, str]) -> DataFrame:
    """
    Rename columns using a ``{old_name: new_name}`` mapping.

    Columns absent from *mapping* are left unchanged.

    Parameters
    ----------
    df : DataFrame
        Input Spark DataFrame.
    mapping : dict[str, str]
        Rename mapping.

    Returns
    -------
    DataFrame
        DataFrame with columns renamed according to *mapping*.

    Raises
    ------
    ValueError
        If any source column in *mapping* does not exist in *df*.
    """
    missing = [old for old in mapping if old not in df.columns]
    if missing:
        raise ValueError(
            f"rename_columns: source columns {missing} not found in DataFrame. "
            f"Available: {df.columns}"
        )
    result = df
    for old, new in mapping.items():
        result = result.withColumnRenamed(old, new)
    logger.info("rename_columns: renamed %d column(s)", len(mapping))
    return result


def convert_type(df: DataFrame, column: str, to_type: ColumnTypeName) -> DataFrame:
    """
    Cast *column* to *to_type* using Spark's ``cast`` function.

    The supported type names match the ``ColumnType`` values defined in
    Phase 2's ``config_models.py``.

    Parameters
    ----------
    df : DataFrame
        Input Spark DataFrame.
    column : str
        Column to cast.
    to_type : ColumnTypeName
        Target type: ``"string"``, ``"integer"``, ``"double"``,
        ``"boolean"``, or ``"timestamp"``.

    Returns
    -------
    DataFrame
        DataFrame with *column* cast to *to_type*.

    Raises
    ------
    ValueError
        If *column* is not in *df* or *to_type* is unsupported.
    """
    if column not in df.columns:
        raise ValueError(
            f"convert_type: column '{column}' not found. Available: {df.columns}"
        )
    spark_type = _SPARK_TYPE_MAP.get(to_type)
    if spark_type is None:
        raise ValueError(
            f"convert_type: unsupported type '{to_type}'. "
            f"Supported: {list(_SPARK_TYPE_MAP.keys())}"
        )
    result = df.withColumn(column, F.col(column).cast(spark_type))
    logger.info("convert_type: cast column '%s' to %s", column, to_type)
    return result
