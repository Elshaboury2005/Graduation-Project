"""
app/plugins/sources/csv_source.py
-----------------------------------
Source plugin for reading CSV files.

plugin_type: "csv"

Reads a local CSV file using ``pandas.read_csv`` and returns a DataFrame.
No schema enforcement is applied here — that is the responsibility of the
downstream :class:`~app.plugins.processors` chain.
"""

from __future__ import annotations

import pandas as pd

from app.plugins.base import PluginConfigError, SourcePlugin
from app.plugins.registry import registry


@registry.register_source
class CsvSource(SourcePlugin):
    """
    Reads data from a CSV file on the local filesystem.

    Required config keys
    --------------------
    path : str
        Absolute or relative path to the CSV file.

    Optional config keys
    --------------------
    encoding : str, default ``"utf-8"``
        File encoding.
    delimiter : str, default ``","``
        Field delimiter character.
    """

    plugin_type = "csv"

    def read(self, config: dict) -> pd.DataFrame:
        """
        Load the CSV file at ``config["path"]`` into a DataFrame.

        Parameters
        ----------
        config : dict
            Must contain ``"path"``.

        Returns
        -------
        pandas.DataFrame
            All rows and columns from the CSV file, with inferred dtypes.

        Raises
        ------
        PluginConfigError
            ``"path"`` is missing or None.
        FileNotFoundError
            The file at ``path`` does not exist.
        """
        self._require(config, "path")
        path: str = config["path"]
        encoding: str = config.get("encoding", "utf-8")
        delimiter: str = config.get("delimiter", ",")

        try:
            df = pd.read_csv(path, encoding=encoding, delimiter=delimiter)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"CsvSource: file not found at path '{path}'.  "
                "Check that the path is correct and the file exists."
            ) from None
        except Exception as exc:
            raise PluginConfigError(
                f"CsvSource: failed to read CSV from '{path}': {exc}"
            ) from exc

        return df
