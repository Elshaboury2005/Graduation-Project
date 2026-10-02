"""
app/plugins/processors/filter_processor.py
--------------------------------------------
Processor plugin that filters rows using a boolean expression.

plugin_type: "filter"

Uses ``pandas.DataFrame.query()`` to evaluate the condition.  A basic
injection guard rejects conditions containing dangerous patterns before
they reach the pandas expression evaluator.
"""

from __future__ import annotations

import re

import pandas as pd

from app.plugins.base import PluginConfigError, ProcessorPlugin
from app.plugins.registry import registry

# Patterns that are never valid in a DataFrame filter condition and could
# indicate an attempt to execute arbitrary Python via pandas' query engine.
_UNSAFE_PATTERNS: list[str] = [
    "__",        # dunder access (__class__, __import__, etc.)
    "import",    # module imports
    "exec(",     # code execution
    "eval(",     # expression evaluation
    "open(",     # file access
    "os.",       # OS module access
    "sys.",      # sys module access
]


def _validate_condition(condition: str) -> None:
    """
    Raise :class:`PluginConfigError` if *condition* matches any unsafe pattern.

    This is a basic, defence-in-depth guard — it does not make ``df.query()``
    fully sandboxed, but it rejects the most obvious injection vectors.

    Parameters
    ----------
    condition : str
        The filter expression to validate.

    Raises
    ------
    PluginConfigError
        The condition contains a pattern that could be used for injection.
    """
    condition_lower = condition.lower()
    for pattern in _UNSAFE_PATTERNS:
        if pattern in condition_lower:
            raise PluginConfigError(
                f"FilterProcessor: condition {condition!r} contains the "
                f"disallowed pattern '{pattern}'.  "
                "Only simple boolean expressions referencing column names are "
                "permitted (e.g. 'amount > 0 and status == \"active\"')."
            )


@registry.register_processor
class FilterProcessor(ProcessorPlugin):
    """
    Retains only rows where the boolean *condition* expression evaluates to True.

    Uses ``pandas.DataFrame.query()`` which supports a SQL-like expression
    language: column name comparisons, ``and``/``or``/``not`` operators, and
    string literals in single or double quotes.

    Required config keys
    --------------------
    condition : str
        Boolean expression, e.g. ``"amount > 0"`` or
        ``"status == 'active' and amount > 100"``.
    """

    plugin_type = "filter"

    def process(self, df: pd.DataFrame, config: dict) -> pd.DataFrame:
        """
        Filter *df* rows using ``config["condition"]``.

        Parameters
        ----------
        df : pandas.DataFrame
            Input DataFrame.
        config : dict
            Must contain ``"condition"``.

        Returns
        -------
        pandas.DataFrame
            Subset of rows where the condition is True.  Index is NOT reset —
            original row indices are preserved.

        Raises
        ------
        PluginConfigError
            ``"condition"`` is missing or contains an unsafe pattern.
        """
        self._require(config, "condition")
        condition: str = config["condition"]

        _validate_condition(condition)

        try:
            return df.query(condition)
        except Exception as exc:
            raise PluginConfigError(
                f"FilterProcessor: failed to evaluate condition {condition!r}: {exc}.  "
                "Check that the column names in the condition match the DataFrame schema."
            ) from exc
