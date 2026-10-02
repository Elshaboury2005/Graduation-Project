"""
app/storage/exceptions.py
--------------------------
Custom exception hierarchy for HDFS storage operations.

All exceptions carry the HDFS path that caused the failure so log
aggregation tools can correlate errors without parsing free-form messages.
"""

from __future__ import annotations


class HdfsConnectionError(Exception):
    """
    Raised when the HDFS NameNode is not reachable or authentication fails.

    Attributes
    ----------
    namenode_url : str
        The WebHDFS URL that was attempted.
    """

    def __init__(self, message: str, namenode_url: str = "") -> None:
        super().__init__(message)
        self.namenode_url = namenode_url


class HdfsWriteError(Exception):
    """
    Raised when writing data to HDFS fails after a successful connection.

    Attributes
    ----------
    hdfs_path : str
        The target HDFS path that could not be written.
    """

    def __init__(self, message: str, hdfs_path: str = "") -> None:
        super().__init__(message)
        self.hdfs_path = hdfs_path


class HdfsReadError(Exception):
    """
    Raised when reading data from HDFS fails.

    Attributes
    ----------
    hdfs_path : str
        The source HDFS path that could not be read.
    """

    def __init__(self, message: str, hdfs_path: str = "") -> None:
        super().__init__(message)
        self.hdfs_path = hdfs_path


class HdfsPathNotFoundError(HdfsReadError):
    """
    Raised when an expected HDFS path does not exist.

    Subclasses :class:`HdfsReadError` so callers that catch read errors
    automatically handle missing-path errors too.
    """
