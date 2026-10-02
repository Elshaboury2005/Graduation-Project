"""
app/storage/hdfs_config.py
---------------------------
HDFS-related configuration constants.

Actual field definitions live in ``app/core/config.py`` (``Settings`` class).
This module centralises the default values and documents each setting so they
are easy to find without grepping through the main config file.

Environment variables
---------------------
HDFS_NAMENODE_URL
    Full WebHDFS base URL of the NameNode, e.g. ``http://namenode:9870``.
    The ``hdfs`` library appends ``/webhdfs/v1`` automatically.

HDFS_USER
    Hadoop username sent with every WebHDFS request (SIMPLE authentication).
    Defaults to ``"root"`` which matches the ``bde2020/hadoop-*`` images.

HDFS_DEFAULT_REPLICATION
    Replication factor for files written to HDFS.  Set to ``1`` for a
    single-datanode local development cluster; production clusters typically
    use ``3``.
"""

# ── Default values ─────────────────────────────────────────────────────────────

HDFS_DEFAULT_NAMENODE_URL: str = "http://namenode:9870"
HDFS_DEFAULT_USER: str = "root"
HDFS_DEFAULT_REPLICATION: int = 1
