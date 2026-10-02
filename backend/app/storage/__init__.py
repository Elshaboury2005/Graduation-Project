"""
app/storage/__init__.py
------------------------
HDFS storage integration package (Phase 6).

Exposes the high-level client and exception classes so callers import
from a single, stable location::

    from app.storage import HdfsStorageClient
    from app.storage.exceptions import HdfsConnectionError
"""

from app.storage.exceptions import (
    HdfsConnectionError,
    HdfsPathNotFoundError,
    HdfsReadError,
    HdfsWriteError,
)
from app.storage.hdfs_client import HdfsStorageClient

__all__ = [
    "HdfsStorageClient",
    "HdfsConnectionError",
    "HdfsWriteError",
    "HdfsReadError",
    "HdfsPathNotFoundError",
]
