"""
spark-jobs/operations/aggregate_ops.py
-----------------------------------------
PySpark DataFrame aggregation operations.

Implements grouped aggregation using ``DataFrame.groupBy().agg()``, mapping
config-level operation names (``sum``, ``avg``, ``count``, ``min``, ``max``)
to the correct Spark SQL aggregate functions.
"""

from __future__ import annotations

import logging
from typing import Literal

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

logger = logging.getLogger(__name__)

AggOperation = Literal["sum", "avg", "count", "min", "max"]

# Map config operation names to Spark built-in aggregate functions.
# "count" is handled separately because it ignores the field argument.
_AGG_FUNC_MAP: dict[str, str] = {
    "sum": "sum",
    "avg": "avg",
    "min": "min",
    "max": "max",
}


def aggregate(
    df: DataFrame,
    group_by: str,
    operation: AggOperation,
    field: str,
) -> DataFrame:
    """
    Group *df* by *group_by* and apply *operation* to *field*.

    For ``operation="count"`` the *field* argument is ignored and
    ``F.count("*")`` is used to count total rows per group.

    Parameters
    ----------
    df : DataFrame
        Input Spark DataFrame.
    group_by : str
        Column name to group by.
    operation : AggOperation
        Aggregation function: ``"sum"``, ``"avg"``, ``"count"``, ``"min"``,
        or ``"max"``.
    field : str
        Column to aggregate (ignored when ``operation="count"``).

    Returns
    -------
    DataFrame
        Aggregated DataFrame with two columns: *group_by* and the result
        column named ``{operation}({field})`` (Spark default naming).

    Raises
    ------
    ValueError
        If *group_by* or *field* (for non-count operations) is missing from
        *df*, or if *operation* is unsupported.
    """
    if group_by not in df.columns:
        raise ValueError(
            f"aggregate: group_by column '{group_by}' not found. "
            f"Available: {df.columns}"
        )
    if operation not in ("sum", "avg", "count", "min", "max"):
        raise ValueError(
            f"aggregate: unsupported operation '{operation}'. "
            "Supported: sum, avg, count, min, max"
        )

    grouped = df.groupBy(group_by)

    if operation == "count":
        # count(*) — counts all rows per group, field is irrelevant
        result = grouped.agg(F.count("*").alias("count"))
        logger.info(
            "aggregate: groupBy('%s').count() → %d groups",
            group_by,
            result.count(),
        )
        return result

    # For all other operations, the field must exist
    if field not in df.columns:
        raise ValueError(
            f"aggregate: field column '{field}' not found. "
            f"Available: {df.columns}"
        )

    spark_fn_name = _AGG_FUNC_MAP[operation]
    agg_col = getattr(F, spark_fn_name)(F.col(field)).alias(f"{operation}_{field}")
    result = grouped.agg(agg_col)
    logger.info(
        "aggregate: groupBy('%s').%s('%s') → %d groups",
        group_by,
        operation,
        field,
        result.count(),
    )
    return result
