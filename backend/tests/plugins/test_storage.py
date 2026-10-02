"""
tests/plugins/test_storage.py
------------------------------
Unit tests for all built-in storage plugins.

Covers:
* LocalStorage.write() creates a real Parquet file in tmp_path.
* LocalStorage.exists() correctly detects the file before and after write.
* LocalStorage write metadata contains expected keys.
* HdfsStorage (Phase 6 real implementation) delegates to HdfsStorageClient
  (mocked — no live HDFS cluster needed for unit tests).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import app.plugins  # noqa: F401 — ensures all plugins are registered

from app.plugins.base import PluginConfigError
from app.plugins.storage.hdfs_storage import HdfsStorage
from app.plugins.storage.local_storage import LocalStorage


# ── Shared sample DataFrame ────────────────────────────────────────────────────


@pytest.fixture()
def sample_df() -> pd.DataFrame:
    """Small DataFrame used as write input across all storage tests."""
    return pd.DataFrame(
        {
            "customer_id": ["C1", "C2", "C3"],
            "amount": [100.0, 250.0, 175.5],
        }
    )


# ── LocalStorage ───────────────────────────────────────────────────────────────


class TestLocalStorage:
    """LocalStorage writes Parquet to disk and detects it with exists()."""

    def test_write_creates_parquet_file(
        self, tmp_path: Path, sample_df: pd.DataFrame
    ) -> None:
        storage = LocalStorage()
        storage.write(sample_df, {"path": str(tmp_path)})
        assert (tmp_path / "data.parquet").exists()

    def test_write_returns_correct_metadata(
        self, tmp_path: Path, sample_df: pd.DataFrame
    ) -> None:
        storage = LocalStorage()
        meta = storage.write(sample_df, {"path": str(tmp_path)})

        assert meta["rows_written"] == len(sample_df)
        assert meta["format"] == "parquet"
        assert "data.parquet" in meta["path"]

    def test_written_file_is_readable_as_parquet(
        self, tmp_path: Path, sample_df: pd.DataFrame
    ) -> None:
        """Roundtrip: write then read back via pandas.read_parquet."""
        storage = LocalStorage()
        meta = storage.write(sample_df, {"path": str(tmp_path)})
        df_back = pd.read_parquet(meta["path"], engine="pyarrow")

        assert len(df_back) == len(sample_df)
        assert set(df_back.columns) == set(sample_df.columns)

    def test_written_values_match_input(
        self, tmp_path: Path, sample_df: pd.DataFrame
    ) -> None:
        storage = LocalStorage()
        meta = storage.write(sample_df, {"path": str(tmp_path)})
        df_back = pd.read_parquet(meta["path"])

        pd.testing.assert_frame_equal(
            df_back.reset_index(drop=True),
            sample_df.reset_index(drop=True),
            check_dtype=False,
        )

    def test_creates_parent_directories(
        self, tmp_path: Path, sample_df: pd.DataFrame
    ) -> None:
        deep_path = tmp_path / "a" / "b" / "c"
        storage = LocalStorage()
        storage.write(sample_df, {"path": str(deep_path)})
        assert (deep_path / "data.parquet").exists()

    def test_exists_returns_false_before_write(self, tmp_path: Path) -> None:
        storage = LocalStorage()
        assert storage.exists({"path": str(tmp_path)}) is False

    def test_exists_returns_true_after_write(
        self, tmp_path: Path, sample_df: pd.DataFrame
    ) -> None:
        storage = LocalStorage()
        storage.write(sample_df, {"path": str(tmp_path)})
        assert storage.exists({"path": str(tmp_path)}) is True

    def test_missing_path_raises_plugin_config_error_on_write(
        self, sample_df: pd.DataFrame
    ) -> None:
        storage = LocalStorage()
        with pytest.raises(PluginConfigError):
            storage.write(sample_df, {})

    def test_missing_path_raises_plugin_config_error_on_exists(self) -> None:
        storage = LocalStorage()
        with pytest.raises(PluginConfigError):
            storage.exists({})

    def test_empty_dataframe_writes_zero_rows(self, tmp_path: Path) -> None:
        empty_df = pd.DataFrame({"a": [], "b": []})
        storage = LocalStorage()
        meta = storage.write(empty_df, {"path": str(tmp_path)})
        assert meta["rows_written"] == 0

    def test_plugin_type_is_local(self) -> None:
        assert LocalStorage.plugin_type == "local"

    def test_overwrite_succeeds(
        self, tmp_path: Path, sample_df: pd.DataFrame
    ) -> None:
        """Writing twice to the same path must silently overwrite."""
        storage = LocalStorage()
        storage.write(sample_df, {"path": str(tmp_path)})
        bigger_df = pd.concat([sample_df, sample_df], ignore_index=True)
        meta = storage.write(bigger_df, {"path": str(tmp_path)})
        assert meta["rows_written"] == len(bigger_df)


# ── HdfsStorage ────────────────────────────────────────────────────────────────


class TestHdfsStorage:
    """
    HdfsStorage Phase-6 plugin — unit tests using a mocked HdfsStorageClient.

    No live HDFS cluster is required.  All tests patch HdfsStorageClient so
    the plugin routing and config validation are exercised without I/O.
    """

    def test_plugin_type_is_hdfs(self) -> None:
        """plugin_type class attribute must be 'hdfs'."""
        assert HdfsStorage.plugin_type == "hdfs"

    def test_hdfs_is_in_registry(self) -> None:
        """HdfsStorage must be registered so pipeline configs can reference 'hdfs'."""
        from app.plugins.registry import registry
        assert "hdfs" in registry.list_storage()

    def test_write_calls_client_write_dataframe(
        self, sample_df: pd.DataFrame
    ) -> None:
        """write() must delegate to HdfsStorageClient.write_dataframe() with the correct path."""
        from unittest.mock import MagicMock, patch

        mock_result = {"hdfs_path": "/hdfs/test.parquet", "rows_written": 3, "size_bytes": 512}
        with patch("app.plugins.storage.hdfs_storage.HdfsStorageClient") as MockClient:
            MockClient.return_value.write_dataframe.return_value = mock_result
            storage = HdfsStorage()
            result = storage.write(sample_df, {"path": "/hdfs/test.parquet"})

        MockClient.return_value.write_dataframe.assert_called_once_with(
            sample_df, "/hdfs/test.parquet"
        )
        assert result == mock_result

    def test_exists_calls_client_path_exists(self) -> None:
        """exists() must delegate to HdfsStorageClient.path_exists()."""
        from unittest.mock import patch

        with patch("app.plugins.storage.hdfs_storage.HdfsStorageClient") as MockClient:
            MockClient.return_value.path_exists.return_value = True
            storage = HdfsStorage()
            result = storage.exists({"path": "/hdfs/test.parquet"})

        MockClient.return_value.path_exists.assert_called_once_with("/hdfs/test.parquet")
        assert result is True

    def test_write_missing_path_raises_plugin_config_error(
        self, sample_df: pd.DataFrame
    ) -> None:
        """write() must raise PluginConfigError if 'path' is absent from config."""
        storage = HdfsStorage()
        with pytest.raises(PluginConfigError):
            storage.write(sample_df, {})

    def test_exists_missing_path_raises_plugin_config_error(self) -> None:
        """exists() must raise PluginConfigError if 'path' is absent from config."""
        storage = HdfsStorage()
        with pytest.raises(PluginConfigError):
            storage.exists({})

    def test_write_does_not_raise_not_implemented(
        self, sample_df: pd.DataFrame
    ) -> None:
        """Phase 6: write() must NOT raise NotImplementedError (stub is gone)."""
        from unittest.mock import patch

        with patch("app.plugins.storage.hdfs_storage.HdfsStorageClient") as MockClient:
            MockClient.return_value.write_dataframe.return_value = {
                "hdfs_path": "/ok", "rows_written": 3, "size_bytes": 100
            }
            storage = HdfsStorage()
            # Must not raise NotImplementedError
            result = storage.write(sample_df, {"path": "/ok"})
        assert result["rows_written"] == 3
