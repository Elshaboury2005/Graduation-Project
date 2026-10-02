"""
spark-jobs/operations/cleaning_ops.py
---------------------------------------
PySpark DataFrame cleaning operations.

Mirrors Phase 3's pandas-based ``remove_nulls`` and ``remove_duplicates``
processors, but operates on ``pyspark.sql.DataFrame`` objects so jobs run
natively inside the Spark cluster.
"""

from __future__ import annotations

import logging

from pyspark.sql import DataFrame

logger = logging.getLogger(__name__)


def remove_nulls(df: DataFrame) -> DataFrame:
    """
    Drop any row that contains at least one null value.

    Uses Spark's built-in ``DataFrame.na.drop()`` which is equivalent to
    ``df.dropna(how='any')`` in pandas.

    Parameters
    ----------
    df : DataFrame
        Input Spark DataFrame.

    Returns
    -------
    DataFrame
        New DataFrame with null-containing rows removed.
    """
    before = df.count()
    result = df.na.drop()
    after = result.count()
    logger.info("remove_nulls: %d → %d rows (dropped %d)", before, after, before - after)
    return result


def remove_duplicates(df: DataFrame) -> DataFrame:
    """
    Remove exact duplicate rows from the DataFrame.

    Uses ``DataFrame.dropDuplicates()`` which considers all columns when
    determining row equality.

    Parameters
    ----------
    df : DataFrame
        Input Spark DataFrame.

    Returns
    -------
    DataFrame
        New DataFrame with duplicate rows removed.
    """
    before = df.count()
    result = df.dropDuplicates()
    after = result.count()
    logger.info(
        "remove_duplicates: %d → %d rows (dropped %d)", before, after, before - after
    )
    return result
