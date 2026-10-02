"""
app/spark/exceptions.py
------------------------
Custom exceptions for Spark job submission.

All exceptions carry captured stdout/stderr so operators can debug
failures without tailing container logs manually.
"""

from __future__ import annotations


class SparkSubmitError(Exception):
    """
    Base class for all Spark submission errors.

    Attributes
    ----------
    stdout : str
        Captured standard output from the ``spark-submit`` process.
    stderr : str
        Captured standard error from the ``spark-submit`` process.
    """

    def __init__(self, message: str, stdout: str = "", stderr: str = "") -> None:
        super().__init__(message)
        self.stdout = stdout
        self.stderr = stderr

    def __str__(self) -> str:
        base = super().__str__()
        if self.stderr:
            return f"{base}\n--- Spark diagnostics ---\n{self.stderr}"
        if self.stdout:
            tail = "\n".join(self.stdout.splitlines()[-80:])
            return f"{base}\n--- stdout (last 80 lines) ---\n{tail}"
        return base


class SparkJobTimeoutError(SparkSubmitError):
    """
    Raised when a ``spark-submit`` process exceeds the configured timeout.

    The subprocess is killed before this exception is raised so no orphaned
    Spark processes are left running.
    """


class SparkJobFailedError(SparkSubmitError):
    """
    Raised when ``spark-submit`` exits with a non-zero return code.

    The last N lines of stderr are embedded in the exception message to
    surface Spark's error output directly in API responses and backend logs.
    """
