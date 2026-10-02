"""
app/plugins/processors/aggregate.py
--------------------------------------
Processor plugin that groups data by a column and applies an aggregation
function.

plugin_type: "aggregate"

Supported operations: sum, avg, count, min, max.
"avg" is mapped to pandas' "mean" internally.
"""

from __future__ import annotations

import pandas as pd

from app.plugins.base import PluginConfigError, ProcessorPlugin
from app.plugins.registry import registry

# Map Phase 2 config vocabulary → pandas aggregation function names
_OPERATION_MAP: dict[str, str] = {
    "sum": "sum",
    "avg": "mean",
    "count": "count",
    "min": "min",
    "max": "max",
}

_VALID_OPERATIONS = sorted(_OPERATION_MAP)


@registry.register_processor
class Aggregate(ProcessorPlugin):
    """
    Groups rows by ``group_by`` column and aggregates ``field`` with the
    specified ``operation``, returning one row per unique group value.

    The result DataFrame contains exactly two columns: the group-by column and
    the aggregated field column.  This is the correct shape for downstream
    storage or further processing.

    Required config keys
    --------------------
    group_by : str
        Column name to group rows by.
    operation : str
        Aggregation function — one of ``"sum"``, ``"avg"``, ``"count"``,
        ``"min"``, ``"max"``.
    field : str
        Column name to aggregate.
    """

    plugin_type = "aggregate"

    def process(self, df: pd.DataFrame, config: dict) -> pd.DataFrame:
        """
        Group *df* by ``group_by`` and aggregate ``field`` with ``operation``.

        Parameters
        ----------
        df : pandas.DataFrame
            Input DataFrame.
        config : dict
            Must contain ``"group_by"``, ``"operation"``, and ``"field"``.

        Returns
        -------
        pandas.DataFrame
            One row per unique ``group_by`` value, columns = [group_by, field].
            Index is reset.

        Raises
        ------
        PluginConfigError
            A required config key is missing, an invalid operation is given,
            or the referenced columns do not exist in *df*.
        """
        self._require(config, "group_by", "operation", "field")
        group_by: str = config["group_by"]
        operation: str = config["operation"]
        field: str = config["field"]

        if operation not in _OPERATION_MAP:
            raise PluginConfigError(
                f"Aggregate: unknown operation '{operation}'.  "
                f"Supported operations: {_VALID_OPERATIONS}."
            )

        for col_name, role in [(group_by, "group_by"), (field, "field")]:
            if col_name not in df.columns:
                raise PluginConfigError(
                    f"Aggregate: {role} column '{col_name}' not found in DataFrame.  "
                    f"Available columns: {list(df.columns)}."
                )

        pandas_op = _OPERATION_MAP[operation]
        result: pd.DataFrame = (
            df.groupby(group_by)[field]
            .agg(pandas_op)
            .reset_index()
        )
        return result
