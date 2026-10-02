"""
app/plugins/processors/type_conversion.py
-------------------------------------------
Processor plugin that casts a single column to a different data type.

plugin_type: "type_conversion"

Supported target types: string, integer, double, boolean, timestamp.
The type names match the vocabulary used in ``schema[].type`` fields so
pipeline configs can be self-consistent.
"""

from __future__ import annotations

import pandas as pd

from app.plugins.base import PluginConfigError, ProcessorPlugin
from app.plugins.registry import registry

# Maps Phase 2 schema type names → callable that converts a pandas Series.
_TYPE_CONVERTERS = {
    "string": lambda s: s.astype(str),
    "integer": lambda s: pd.to_numeric(s, errors="raise").astype("Int64"),
    "double": lambda s: s.astype(float),
    "boolean": lambda s: s.astype(bool),
    "timestamp": lambda s: pd.to_datetime(s),
}

_VALID_TYPES = sorted(_TYPE_CONVERTERS)


@registry.register_processor
class TypeConversion(ProcessorPlugin):
    """
    Casts a single named column to the specified data type.

    Uses ``Int64`` (pandas nullable integer dtype) for ``"integer"`` so that
    columns with NaN values that survived previous steps are handled correctly
    without immediately failing.

    Required config keys
    --------------------
    column : str
        Name of the column to cast.
    to_type : str
        Target type — one of ``"string"``, ``"integer"``, ``"double"``,
        ``"boolean"``, ``"timestamp"``.
    """

    plugin_type = "type_conversion"

    def process(self, df: pd.DataFrame, config: dict) -> pd.DataFrame:
        """
        Cast ``config["column"]`` to ``config["to_type"]`` in *df*.

        Parameters
        ----------
        df : pandas.DataFrame
            Input DataFrame.
        config : dict
            Must contain ``"column"`` and ``"to_type"``.

        Returns
        -------
        pandas.DataFrame
            DataFrame with the named column replaced by its cast version.
            All other columns and row count are unchanged.

        Raises
        ------
        PluginConfigError
            ``"column"`` or ``"to_type"`` is missing, the column does not
            exist in *df*, or the cast operation fails.
        """
        self._require(config, "column", "to_type")
        column: str = config["column"]
        to_type: str = config["to_type"]

        if column not in df.columns:
            raise PluginConfigError(
                f"TypeConversion: column '{column}' not found in DataFrame.  "
                f"Available columns: {list(df.columns)}."
            )

        if to_type not in _TYPE_CONVERTERS:
            raise PluginConfigError(
                f"TypeConversion: unknown target type '{to_type}'.  "
                f"Supported types: {_VALID_TYPES}."
            )

        converter = _TYPE_CONVERTERS[to_type]
        result = df.copy()
        try:
            result[column] = converter(result[column])
        except (ValueError, TypeError) as exc:
            raise PluginConfigError(
                f"TypeConversion: failed to cast column '{column}' to '{to_type}': {exc}."
            ) from exc

        return result
