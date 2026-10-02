"""
tests/storage/test_hdfs_client.py
-----------------------------------
Integration tests for :class:`~app.storage.HdfsStorageClient`.

All tests are marked ``@pytest.mark.integration`` and skipped automatically
when the HDFS NameNode is not reachable — the same pattern used by the Kafka
and Spark integration test suites in Phases 4 and 5.

Test coverage
-------------
* ``write_dataframe`` → ``path_exists`` round-trip.
* ``read_dataframe`` — data integrity check (values match what was written).
* ``list_directory`` — file appears in parent directory listing.
* ``delete_path`` — teardown actually removes the path.
* ``health_check`` — returns ``connected: True`` with live capacity stats.
* ``HdfsStorage`` plugin (Phase 3 stub → Phase 6 real implementation)
  performs a real write via the registry without raising ``NotImplementedError``.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pandas as pd
import pytest

HDFS_BASE_PATH = "/data/test"


# ── Skip fixture ───────────────────────────────────────────────────────────────


def _hdfs_reachable() -> bool:
    """Return True if the HDFS NameNode WebHDFS root endpoint responds."""
    try:
        import requests

        from app.core.config import get_settings

        settings = get_settings()
        url = f"{settings.HDFS_NAMENODE_URL}/webhdfs/v1/?op=GETFILESTATUS"
        resp = requests.get(url, timeout=5)
        return resp.status_code in (200, 403)  # 403 = auth needed but reachable
    except Exception:
        return False


skip_if_no_hdfs = pytest.mark.skipif(
    not _hdfs_reachable(),
    reason="HDFS NameNode is not reachable — start the cluster with docker-compose up",
)


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def client():
    """Return a live HdfsStorageClient (skips if HDFS not reachable)."""
    from app.storage.hdfs_client import HdfsStorageClient

    return HdfsStorageClient()


@pytest.fixture()
def sample_df() -> pd.DataFrame:
    """A small DataFrame used as write payload for every test."""
    return pd.DataFrame(
        {
            "id": [1, 2, 3],
            "name": ["alice", "bob", "carol"],
            "score": [99.5, 87.3, 92.1],
        }
    )


@pytest.fixture()
def unique_path() -> str:
    """Generate a unique HDFS path so parallel test runs don't collide."""
    return f"{HDFS_BASE_PATH}/{uuid.uuid4().hex}.parquet"


# ── Tests ──────────────────────────────────────────────────────────────────────


@pytest.mark.integration
@skip_if_no_hdfs
class TestHdfsClientRoundTrip:
    """Write → read round-trip and path management tests."""

    def test_write_returns_metadata(self, client, sample_df, unique_path) -> None:
        """write_dataframe must return hdfs_path, rows_written, size_bytes."""
        result = client.write_dataframe(sample_df, unique_path)
        assert result["hdfs_path"] == unique_path
        assert result["rows_written"] == len(sample_df)
        assert result["size_bytes"] > 0
        # Teardown
        client.delete_path(unique_path)

    def test_path_exists_true_after_write(self, client, sample_df, unique_path) -> None:
        """path_exists must return True for a successfully written path."""
        client.write_dataframe(sample_df, unique_path)
        try:
            assert client.path_exists(unique_path) is True
        finally:
            client.delete_path(unique_path)

    def test_path_exists_false_before_write(self, client) -> None:
        """path_exists must return False for a path that has never been written."""
        fake_path = f"{HDFS_BASE_PATH}/nonexistent_{uuid.uuid4().hex}.parquet"
        assert client.path_exists(fake_path) is False

    def test_read_matches_written_data(self, client, sample_df, unique_path) -> None:
        """read_dataframe must return identical data to what was written."""
        client.write_dataframe(sample_df, unique_path)
        try:
            df_back = client.read_dataframe(unique_path)
            pd.testing.assert_frame_equal(
                df_back.reset_index(drop=True),
                sample_df.reset_index(drop=True),
            )
        finally:
            client.delete_path(unique_path)

    def test_list_directory_shows_written_file(
        self, client, sample_df, unique_path
    ) -> None:
        """list_directory must include the written file's basename."""
        client.write_dataframe(sample_df, unique_path)
        try:
            parent = unique_path.rsplit("/", 1)[0]
            entries = client.list_directory(parent)
            filename = unique_path.rsplit("/", 1)[-1]
            assert filename in entries
        finally:
            client.delete_path(unique_path)

    def test_delete_removes_path(self, client, sample_df, unique_path) -> None:
        """delete_path must return True and path_exists must be False afterwards."""
        client.write_dataframe(sample_df, unique_path)
        deleted = client.delete_path(unique_path)
        assert deleted is True
        assert client.path_exists(unique_path) is False

    def test_overwrite_succeeds(self, client, sample_df, unique_path) -> None:
        """Writing the same path twice (overwrite=True) must succeed."""
        client.write_dataframe(sample_df, unique_path)
        df2 = sample_df.copy()
        df2["score"] = df2["score"] * 2
        result = client.write_dataframe(df2, unique_path)
        assert result["rows_written"] == len(df2)
        client.delete_path(unique_path)


@pytest.mark.integration
@skip_if_no_hdfs
class TestHdfsHealthCheck:
    """health_check() tests against a live cluster."""

    def test_health_check_connected_is_true(self, client) -> None:
        """health_check must report connected: True when the cluster is up."""
        result = client.health_check()
        assert result["connected"] is True
        assert result["error"] is None

    def test_health_check_has_namenode_url(self, client) -> None:
        """health_check must include the namenode_url field."""
        result = client.health_check()
        assert "namenode_url" in result
        assert result["namenode_url"].startswith("http")

    def test_health_check_includes_live_datanodes(self, client) -> None:
        """health_check must report at least 1 live DataNode via JMX stats."""
        result = client.health_check()
        # JMX may be unavailable — only assert if the field is populated
        if result.get("num_live_datanodes") is not None:
            assert result["num_live_datanodes"] >= 1

    def test_health_check_capacity_fields_present(self, client) -> None:
        """Capacity stats fields must be present (may be None if JMX down)."""
        result = client.health_check()
        assert "capacity_total_gb" in result
        assert "capacity_used_gb" in result


@pytest.mark.integration
@skip_if_no_hdfs
class TestHdfsStoragePlugin:
    """Tests the Phase 6 HdfsStorage plugin (real, not stub) via the registry."""

    def test_hdfs_plugin_write_via_registry(self, sample_df) -> None:
        """HdfsStorage plugin registered under 'hdfs' must write to a real HDFS path."""
        from app.plugins.registry import registry

        import app.plugins  # noqa: F401 — ensure auto-registration

        plugin = registry.get_storage("hdfs")
        hdfs_path = f"{HDFS_BASE_PATH}/plugin_test_{uuid.uuid4().hex}.parquet"
        config = {"path": hdfs_path}
        result = plugin.write(sample_df, config)
        assert result["rows_written"] == len(sample_df)
        assert result["hdfs_path"] == hdfs_path
        # Cleanup
        from app.storage.hdfs_client import HdfsStorageClient
        HdfsStorageClient().delete_path(hdfs_path)

    def test_hdfs_plugin_exists_returns_true_after_write(self, sample_df) -> None:
        """HdfsStorage.exists must return True for a path that was just written."""
        from app.plugins.registry import registry

        import app.plugins  # noqa: F401

        plugin = registry.get_storage("hdfs")
        hdfs_path = f"{HDFS_BASE_PATH}/exists_test_{uuid.uuid4().hex}.parquet"
        plugin.write(sample_df, {"path": hdfs_path})
        assert plugin.exists({"path": hdfs_path}) is True
        from app.storage.hdfs_client import HdfsStorageClient
        HdfsStorageClient().delete_path(hdfs_path)

    def test_hdfs_plugin_no_longer_raises_not_implemented(self, sample_df) -> None:
        """Phase 6: HdfsStorage must NOT raise NotImplementedError."""
        from app.plugins.registry import registry

        import app.plugins  # noqa: F401

        plugin = registry.get_storage("hdfs")
        hdfs_path = f"{HDFS_BASE_PATH}/not_impl_test_{uuid.uuid4().hex}.parquet"
        # Must succeed — no NotImplementedError
        result = plugin.write(sample_df, {"path": hdfs_path})
        assert "rows_written" in result
        from app.storage.hdfs_client import HdfsStorageClient
        HdfsStorageClient().delete_path(hdfs_path)
