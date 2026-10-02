"""
app/plugins/base.py
--------------------
Abstract base classes and shared exceptions for the plugin system.

Every concrete plugin must inherit from one of the three ABCs defined here
and set the ``plugin_type`` class attribute to a unique string that matches
the value used in pipeline YAML configs (e.g. ``"csv"``, ``"filter"``,
``"local"``).

Defensive validation
--------------------
Each plugin method is responsible for validating its own ``config`` dict even
though configs originate from Pydantic-validated models — plugins must be
usable in isolation (e.g. in unit tests) without any Pydantic involvement.
Missing required keys raise :class:`PluginConfigError` with a clear message.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

import pandas as pd


# ── Plugin exceptions ──────────────────────────────────────────────────────────


class PluginConfigError(Exception):
    """
    Raised when a plugin receives a config dict that is missing a required key
    or contains an invalid value.

    This is distinct from Pydantic ``ValidationError`` — it fires at plugin
    *runtime*, not at config parse time, and can be triggered by passing a
    partial config dict directly in a test.

    Example
    -------
    ::

        raise PluginConfigError("CsvSource requires 'path' in config")
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


# ── Abstract base classes ──────────────────────────────────────────────────────


class SourcePlugin(ABC):
    """
    Abstract base class for all data-source plugins.

    A source plugin reads data from an external system (filesystem, API, …)
    and returns it as a pandas DataFrame.  The DataFrame is then passed to the
    first :class:`ProcessorPlugin` in the pipeline.

    Subclasses must
    ---------------
    * Set ``plugin_type: ClassVar[str]`` to the string used in YAML configs.
    * Implement :meth:`read`.
    * Register themselves with the global registry via
      ``@registry.register_source``.
    """

    plugin_type: ClassVar[str]

    @abstractmethod
    def read(self, config: dict) -> pd.DataFrame:
        """
        Read data from the source described by *config* and return a DataFrame.

        Parameters
        ----------
        config:
            Dict derived from the ``source`` section of a validated
            ``PipelineConfig``.  Must contain at least ``"type"`` and whatever
            fields the concrete source requires (e.g. ``"path"`` for
            file-based sources, ``"url"`` for API sources).

        Returns
        -------
        pandas.DataFrame
            Raw data ready for processing.  May not be clean — that is the job
            of downstream :class:`ProcessorPlugin` instances.

        Raises
        ------
        PluginConfigError
            A required config key is missing or invalid.
        """

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _require(self, config: dict, *keys: str) -> None:
        """Raise :class:`PluginConfigError` if any of *keys* is absent from *config*."""
        missing = [k for k in keys if k not in config or config[k] is None]
        if missing:
            cls_name = type(self).__name__
            raise PluginConfigError(
                f"{cls_name} requires the following config key(s) "
                f"that are missing or None: {missing}"
            )


class ProcessorPlugin(ABC):
    """
    Abstract base class for all data-transformation plugins.

    A processor takes an input DataFrame, applies a transformation defined by
    *config*, and returns a (possibly modified) DataFrame.  The output is
    passed to the next processor or the storage plugin.

    Processors must be stateless — all parameters come from *config*.
    """

    plugin_type: ClassVar[str]

    @abstractmethod
    def process(self, df: pd.DataFrame, config: dict) -> pd.DataFrame:
        """
        Transform *df* according to *config* and return the result.

        Parameters
        ----------
        df:
            Input DataFrame from the previous pipeline stage.
        config:
            Dict derived from a ``processing.operations`` entry in the YAML.

        Returns
        -------
        pandas.DataFrame
            Transformed data.  Must have the same or fewer columns / rows than
            the input — processors never generate new data, only refine it.

        Raises
        ------
        PluginConfigError
            A required config key is missing or invalid.
        """

    def _require(self, config: dict, *keys: str) -> None:
        """Raise :class:`PluginConfigError` if any of *keys* is absent from *config*."""
        missing = [k for k in keys if k not in config or config[k] is None]
        if missing:
            cls_name = type(self).__name__
            raise PluginConfigError(
                f"{cls_name} requires the following config key(s) "
                f"that are missing or None: {missing}"
            )


class StoragePlugin(ABC):
    """
    Abstract base class for all storage-backend plugins.

    A storage plugin persists a DataFrame produced by the pipeline and
    returns metadata about what was written.  It also exposes an
    :meth:`exists` check so the executor can detect incremental / idempotent
    runs.

    Concrete implementations currently registered:

    * ``"local"`` — writes Parquet files to the local filesystem.
    * ``"hdfs"``  — stub only in Phase 3 (raises :class:`NotImplementedError`).
    """

    plugin_type: ClassVar[str]

    @abstractmethod
    def write(self, df: pd.DataFrame, config: dict) -> dict:
        """
        Persist *df* to the storage backend described by *config*.

        Parameters
        ----------
        df:
            The fully-processed DataFrame ready to be stored.
        config:
            Dict derived from the ``storage`` section of a validated
            ``PipelineConfig``.

        Returns
        -------
        dict
            Metadata about the write operation.  At minimum must include
            ``"path"``, ``"rows_written"``, and ``"format"``.

        Raises
        ------
        PluginConfigError
            A required config key is missing or invalid.
        """

    @abstractmethod
    def exists(self, config: dict) -> bool:
        """
        Check whether output for this config already exists in the backend.

        Used by the executor to support idempotent / incremental runs.

        Parameters
        ----------
        config:
            Same dict passed to :meth:`write`.

        Returns
        -------
        bool
            True if the expected output artifact already exists.
        """

    def _require(self, config: dict, *keys: str) -> None:
        """Raise :class:`PluginConfigError` if any of *keys* is absent from *config*."""
        missing = [k for k in keys if k not in config or config[k] is None]
        if missing:
            cls_name = type(self).__name__
            raise PluginConfigError(
                f"{cls_name} requires the following config key(s) "
                f"that are missing or None: {missing}"
            )
