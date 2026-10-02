"""
spark-jobs/operations/filter_ops.py
--------------------------------------
PySpark DataFrame filter operations.

Uses Spark SQL expression strings for maximum flexibility while applying
an injection guard identical in spirit to Phase 3's pandas filter processor
(reject patterns that indicate code injection attempts).
"""

from __future__ import annotations

import logging

from pyspark.sql import DataFrame

logger = logging.getLogger(__name__)

# ── Injection guard ────────────────────────────────────────────────────────────
# Patterns that should never appear in a legitimate Spark SQL filter expression.
_BANNED_SUBSTRINGS: tuple[str, ...] = ("__", "import", "exec", "eval")


def _check_condition(condition: str) -> None:
    """
    Reject filter conditions that contain dangerous substrings.

    This is a defence-in-depth safeguard; Spark's own parser provides the
    primary protection against malformed SQL, but we additionally block
    Python-specific injection patterns that could be dangerous if the
    expression were ever evaluated in a non-Spark context.

    Parameters
    ----------
    condition : str
        The filter expression to validate.

    Raises
    ------
    ValueError
        If the condition contains any banned substring.
    """
    lowered = condition.lower()
    for pattern in _BANNED_SUBSTRINGS:
        if pattern in lowered:
            raise ValueError(
                f"Filter condition contains forbidden pattern '{pattern}': {condition!r}. "
                "Only pure Spark SQL expressions are allowed."
            )


def apply_filter(df: DataFrame, condition: str) -> DataFrame:
    """
    Retain only rows where *condition* evaluates to ``True``.

    *condition* is passed directly to ``DataFrame.filter()`` as a Spark SQL
    expression string (e.g. ``"amount > 0"`` or ``"status = 'active'"``).

    Parameters
    ----------
    df : DataFrame
        Input Spark DataFrame.
    condition : str
        Spark SQL boolean expression.

    Returns
    -------
    DataFrame
        Filtered DataFrame.

    Raises
    ------
    ValueError
        If *condition* contains a forbidden pattern (injection guard).
    """
    _check_condition(condition)
    before = df.count()
    result = df.filter(condition)
    after = result.count()
    logger.info(
        "apply_filter(%r): %d → %d rows (kept %d)", condition, before, after, after
    )
    return result
