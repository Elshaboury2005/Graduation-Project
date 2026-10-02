"""
app/plugins/storage/hdfs_storage.py
-------------------------------------
Storage plugin for HDFS (Hadoop Distributed File System).

plugin_type: "hdfs"

Phase 6 — real implementation replacing the Phase 3 stub.

The plugin delegates all HDFS operations to :class:`~app.storage.HdfsStorageClient`
which talks to the NameNode's WebHDFS REST API via the ``hdfs`` Python library.
No ``NotImplementedError`` remains — pipelines configured with
``storage.type: hdfs`` now genuinely write data to the HDFS cluster.

Config dict keys:
    path (required): target HDFS path, e.g. ``/data/processed/sales.parquet``

Design principles:
    * Plugin layer stays thin — it validates the config and delegates.
    * Top-level import of HdfsStorageClient enables ``unittest.mock.patch``
      to replace it in unit tests without requiring a live cluster.
    * ``PluginConfigError`` is raised for missing/invalid config; all HDFS-
      level errors propagate as-is from HdfsStorageClient.
"""

from __future__ import annotations

import pandas as pd

from app.plugins.base import PluginConfigError, StoragePlugin
from app.plugins.registry import registry

# Top-level import so ``patch("app.plugins.storage.hdfs_storage.HdfsStorageClient")``
# works in unit tests — lazy imports inside methods are not patchable by path.
from app.storage.hdfs_client import HdfsStorageClient


@registry.register_storage
class HdfsStorage(StoragePlugin):
    """
    HDFS storage plugin — writes pandas DataFrames to HDFS via WebHDFS.

    Registered under ``plugin_type = "hdfs"`` and discovered automatically
    by the plugin registry when ``app.plugins`` is imported.

    The plugin serialises the DataFrame through a local Parquet temp file
    then uploads it to HDFS (see :class:`~app.storage.HdfsStorageClient` for
    full details of the write protocol).
    """

    plugin_type = "hdfs"

    def write(self, df: pd.DataFrame, config: dict) -> dict:
        """
        Write *df* to the HDFS path specified in *config*.

        Parameters
        ----------
        df : pandas.DataFrame
            Data to persist.
        config : dict
            Must contain ``"path"``: target HDFS path string.

        Returns
        -------
        dict
            ``{"hdfs_path": str, "rows_written": int, "size_bytes": int}``

        Raises
        ------
        PluginConfigError
            If ``"path"`` is missing from *config*.
        HdfsWriteError
            If the HDFS upload fails.
        """
        if "path" not in config:
            raise PluginConfigError(
                "HdfsStorage.write requires 'path' in config."
            )

        client = HdfsStorageClient()
        return client.write_dataframe(df, config["path"])

    def exists(self, config: dict) -> bool:
        """
        Return ``True`` if the HDFS path in *config* already exists.

        Parameters
        ----------
        config : dict
            Must contain ``"path"``: HDFS path to test.

        Returns
        -------
        bool

        Raises
        ------
        PluginConfigError
            If ``"path"`` is missing from *config*.
        """
        if "path" not in config:
            raise PluginConfigError(
                "HdfsStorage.exists requires 'path' in config."
            )

        client = HdfsStorageClient()
        return client.path_exists(config["path"])
