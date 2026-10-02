"""
app/plugins/sources/json_source.py
------------------------------------
Source plugin for reading JSON files.

plugin_type: "json"

Supports two JSON layouts automatically:
* **JSON array of records** — ``[{"col": val, ...}, ...]``
* **JSON Lines (NDJSON)** — one JSON object per line

Detection logic: try ``orient="records"`` first; if pandas raises (because
the file is JSON Lines), fall back to ``lines=True``.
"""

from __future__ import annotations

import pandas as pd

from app.plugins.base import PluginConfigError, SourcePlugin
from app.plugins.registry import registry


@registry.register_source
class JsonSource(SourcePlugin):
    """
    Reads data from a JSON file on the local filesystem.

    Supports both a JSON array of records and JSON Lines (NDJSON) format.
    The format is auto-detected: array format is tried first; JSON Lines is
    the fallback.

    Required config keys
    --------------------
    path : str
        Absolute or relative path to the JSON file.
    """

    plugin_type = "json"

    def read(self, config: dict) -> pd.DataFrame:
        """
        Load the JSON file at ``config["path"]`` into a DataFrame.

        Parameters
        ----------
        config : dict
            Must contain ``"path"``.

        Returns
        -------
        pandas.DataFrame
            All records from the JSON file as rows.

        Raises
        ------
        PluginConfigError
            ``"path"`` is missing, or the file cannot be parsed as either
            JSON array or JSON Lines format.
        FileNotFoundError
            The file at ``path`` does not exist.
        """
        self._require(config, "path")
        path: str = config["path"]

        try:
            # Attempt 1: standard JSON array of records
            df = pd.read_json(path, orient="records")
            return df
        except FileNotFoundError:
            raise FileNotFoundError(
                f"JsonSource: file not found at path '{path}'.  "
                "Check that the path is correct and the file exists."
            ) from None
        except ValueError:
            pass  # fall through to JSON Lines attempt

        try:
            # Attempt 2: JSON Lines (one object per line)
            df = pd.read_json(path, lines=True)
            return df
        except ValueError as exc:
            raise PluginConfigError(
                f"JsonSource: could not parse '{path}' as a JSON array or JSON Lines file.  "
                f"Underlying error: {exc}"
            ) from exc
        except Exception as exc:
            raise PluginConfigError(
                f"JsonSource: unexpected error reading '{path}': {exc}"
            ) from exc
