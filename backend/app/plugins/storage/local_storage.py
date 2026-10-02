"""
app/plugins/storage/local_storage.py
--------------------------------------
Storage plugin that writes DataFrames to the local filesystem as Parquet.

plugin_type: "local"

Parquet is chosen over CSV because it is typed (column types survive a
round-trip), compressed by default, and directly readable by Spark, pandas,
DuckDB, and most modern analytics tools.  The ``pyarrow`` engine is used
explicitly so the dependency is declared rather than inferred.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from app.plugins.base import PluginConfigError, StoragePlugin
from app.plugins.registry import registry

_OUTPUT_FILENAME = "data.parquet"
"""Fixed output file name written inside the configured ``path`` directory."""


@registry.register_storage
class LocalStorage(StoragePlugin):
    """
    Writes a DataFrame to ``{config["path"]}/data.parquet`` on the local
    filesystem.

    Parent directories are created automatically if they do not exist.  An
    existing file at the same path is silently overwritten — implement
    idempotency at the caller level using :meth:`exists` if overwriting is not
    desired.

    Required config keys
    --------------------
    path : str
        Absolute path to the output *directory*.  The Parquet file will be
        written as ``{path}/data.parquet``.
    """

    plugin_type = "local"

    def write(self, df: pd.DataFrame, config: dict) -> dict:
        """
        Persist *df* to ``{config["path"]}/data.parquet``.

        Parameters
        ----------
        df : pandas.DataFrame
            Fully-processed DataFrame to persist.
        config : dict
            Must contain ``"path"``.

        Returns
        -------
        dict
            ``{"path": str, "rows_written": int, "format": "parquet"}``

        Raises
        ------
        PluginConfigError
            ``"path"`` is missing or writing fails.
        """
        self._require(config, "path")
        output_dir = Path(config["path"])
        output_path = output_dir / _OUTPUT_FILENAME

        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            df.to_parquet(str(output_path), index=False, engine="pyarrow")
        except Exception as exc:
            raise PluginConfigError(
                f"LocalStorage: failed to write Parquet to '{output_path}': {exc}"
            ) from exc

        return {
            "path": str(output_path),
            "rows_written": len(df),
            "format": "parquet",
        }

    def exists(self, config: dict) -> bool:
        """
        Return True if ``{config["path"]}/data.parquet`` exists on disk.

        Parameters
        ----------
        config : dict
            Must contain ``"path"``.

        Returns
        -------
        bool
        """
        self._require(config, "path")
        output_path = Path(config["path"]) / _OUTPUT_FILENAME
        return output_path.exists()
