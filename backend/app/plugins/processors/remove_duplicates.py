"""
app/plugins/processors/remove_duplicates.py
---------------------------------------------
Processor plugin that drops exact duplicate rows.

plugin_type: "remove_duplicates"
"""

from __future__ import annotations

import pandas as pd

from app.plugins.base import ProcessorPlugin
from app.plugins.registry import registry


@registry.register_processor
class RemoveDuplicates(ProcessorPlugin):
    """
    Drops rows that are exact duplicates of a previously seen row (all columns
    must match for a row to be considered a duplicate).

    The first occurrence of each row is kept; subsequent duplicates are removed.
    Row index is reset on the result to maintain a clean 0-based index.

    Config keys
    -----------
    None required.  This processor uses no additional configuration.

    Note
    ----
    For column-subset deduplication (e.g. "deduplicate on transaction_id only")
    add a ``subset`` config key in a future version.
    """

    plugin_type = "remove_duplicates"

    def process(self, df: pd.DataFrame, config: dict) -> pd.DataFrame:
        """
        Remove duplicate rows from *df*, keeping the first occurrence.

        Parameters
        ----------
        df : pandas.DataFrame
            Input DataFrame.
        config : dict
            Ignored — no configuration needed.

        Returns
        -------
        pandas.DataFrame
            DataFrame with duplicate rows removed and index reset.
        """
        return df.drop_duplicates().reset_index(drop=True)
