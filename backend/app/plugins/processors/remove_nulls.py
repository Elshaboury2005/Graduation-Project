"""
app/plugins/processors/remove_nulls.py
----------------------------------------
Processor plugin that drops rows containing any null/NaN value.

plugin_type: "remove_nulls"
"""

from __future__ import annotations

import pandas as pd

from app.plugins.base import ProcessorPlugin
from app.plugins.registry import registry


@registry.register_processor
class RemoveNulls(ProcessorPlugin):
    """
    Drops every row that contains at least one null or NaN value in any column.

    This is typically the first processor in a pipeline because null values can
    cause downstream operations (filters, type conversions, aggregates) to
    produce incorrect or unexpected results.

    Config keys
    -----------
    None required.  This processor uses no additional configuration.
    """

    plugin_type = "remove_nulls"

    def process(self, df: pd.DataFrame, config: dict) -> pd.DataFrame:
        """
        Remove rows with any null value from *df*.

        Parameters
        ----------
        df : pandas.DataFrame
            Input DataFrame.
        config : dict
            Ignored — no configuration needed.

        Returns
        -------
        pandas.DataFrame
            DataFrame with null-containing rows removed.  May have fewer rows
            than the input.
        """
        return df.dropna()
