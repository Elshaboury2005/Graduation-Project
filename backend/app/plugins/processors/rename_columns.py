"""
app/plugins/processors/rename_columns.py
------------------------------------------
Processor plugin that renames columns using a mapping dict.

plugin_type: "rename_columns"
"""

from __future__ import annotations

import pandas as pd

from app.plugins.base import PluginConfigError, ProcessorPlugin
from app.plugins.registry import registry


@registry.register_processor
class RenameColumns(ProcessorPlugin):
    """
    Renames columns using a ``{old_name: new_name}`` mapping.

    Only the columns present in the mapping are renamed; all other columns
    pass through unchanged.  If a mapped-from column does not exist in the
    DataFrame, pandas silently ignores it — this is intentional and allows
    flexible use of the same mapping across multiple pipeline variants.

    Required config keys
    --------------------
    mapping : dict[str, str]
        Dict mapping existing column names to their desired new names.
        Example: ``{"transaction_id": "txn_id", "sale_date": "date"}``.
    """

    plugin_type = "rename_columns"

    def process(self, df: pd.DataFrame, config: dict) -> pd.DataFrame:
        """
        Rename columns in *df* according to ``config["mapping"]``.

        Parameters
        ----------
        df : pandas.DataFrame
            Input DataFrame.
        config : dict
            Must contain ``"mapping"`` (a non-empty dict of str → str).

        Returns
        -------
        pandas.DataFrame
            DataFrame with renamed columns; column count and row count
            are unchanged.

        Raises
        ------
        PluginConfigError
            ``"mapping"`` is missing or is not a dict.
        """
        self._require(config, "mapping")
        mapping = config["mapping"]

        if not isinstance(mapping, dict):
            raise PluginConfigError(
                f"RenameColumns: 'mapping' must be a dict, got {type(mapping).__name__!r}."
            )

        return df.rename(columns=mapping)
