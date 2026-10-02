"""
app/plugins/processors/select_columns.py
------------------------------------------
Processor plugin that selects a subset of columns.

plugin_type: "select_columns"
"""

from __future__ import annotations

import pandas as pd

from app.plugins.base import PluginConfigError, ProcessorPlugin
from app.plugins.registry import registry


@registry.register_processor
class SelectColumns(ProcessorPlugin):
    """
    Retains only the columns listed in ``config["columns"]``, dropping all
    others.  Column order in the output matches the order in the config list.

    This is useful for reducing the DataFrame to only the fields that are
    relevant for downstream processing and storage.

    Required config keys
    --------------------
    columns : list[str]
        Ordered list of column names to keep.  All names must exist in the
        DataFrame — missing names raise :class:`PluginConfigError` with the
        full list of what was missing and what is available.
    """

    plugin_type = "select_columns"

    def process(self, df: pd.DataFrame, config: dict) -> pd.DataFrame:
        """
        Select only the columns listed in ``config["columns"]``.

        Parameters
        ----------
        df : pandas.DataFrame
            Input DataFrame.
        config : dict
            Must contain ``"columns"`` (a non-empty list of strings).

        Returns
        -------
        pandas.DataFrame
            DataFrame containing only the requested columns in the requested
            order.

        Raises
        ------
        PluginConfigError
            ``"columns"`` is missing, empty, or contains column names that
            do not exist in *df*.
        """
        self._require(config, "columns")
        columns: list[str] = config["columns"]

        if not columns:
            raise PluginConfigError(
                "SelectColumns: 'columns' list must not be empty."
            )

        missing = [c for c in columns if c not in df.columns]
        if missing:
            raise PluginConfigError(
                f"SelectColumns: the following requested columns do not exist "
                f"in the DataFrame: {missing}.  "
                f"Available columns: {list(df.columns)}."
            )

        return df[columns]
