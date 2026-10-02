"""
app/plugins/sources/api_source.py
-----------------------------------
Source plugin for fetching data from HTTP API endpoints.

plugin_type: "api"

Uses the ``requests`` library to perform an HTTP request, expects the
response body to be a JSON array of objects, and converts it to a DataFrame.
Non-200 responses and network errors are surfaced as :class:`PluginConfigError`
with actionable messages.
"""

from __future__ import annotations

import requests
import pandas as pd

from app.plugins.base import PluginConfigError, SourcePlugin
from app.plugins.registry import registry

_DEFAULT_TIMEOUT_SECONDS = 10
"""HTTP request timeout. Prevents the pipeline from hanging indefinitely."""


@registry.register_source
class ApiSource(SourcePlugin):
    """
    Fetches data from an HTTP API endpoint and returns it as a DataFrame.

    The API must return a JSON response whose top-level value is either:
    * A list of objects — ``[{"col": val, ...}, ...]`` (most common)
    * A single object wrapping a list — the first list value is used

    Required config keys
    --------------------
    url : str
        Full URL of the API endpoint, including scheme and any path params.

    Optional config keys
    --------------------
    method : str, default ``"GET"``
        HTTP method (``"GET"`` or ``"POST"``).
    headers : dict, default ``{}``
        HTTP headers to include in the request (e.g. ``Authorization``).
    timeout : int, default 10
        Request timeout in seconds.
    """

    plugin_type = "api"

    def read(self, config: dict) -> pd.DataFrame:
        """
        Perform the HTTP request and convert the JSON response to a DataFrame.

        Parameters
        ----------
        config : dict
            Must contain ``"url"``.

        Returns
        -------
        pandas.DataFrame
            Records from the API response.

        Raises
        ------
        PluginConfigError
            ``"url"`` is missing, the server returned a non-200 status code,
            the response body is not JSON, or the JSON does not contain a list
            of objects.
        """
        self._require(config, "url")
        url: str = config["url"]
        method: str = config.get("method", "GET").upper()
        headers: dict = config.get("headers") or {}
        timeout: int = config.get("timeout", _DEFAULT_TIMEOUT_SECONDS)

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                timeout=timeout,
            )
        except requests.exceptions.Timeout:
            raise PluginConfigError(
                f"ApiSource: request to '{url}' timed out after {timeout}s.  "
                "Consider increasing the 'timeout' config value."
            ) from None
        except requests.exceptions.ConnectionError as exc:
            raise PluginConfigError(
                f"ApiSource: connection error for '{url}': {exc}"
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise PluginConfigError(
                f"ApiSource: HTTP request failed for '{url}': {exc}"
            ) from exc

        if response.status_code != 200:
            raise PluginConfigError(
                f"ApiSource: received HTTP {response.status_code} from '{url}'.  "
                f"Response body: {response.text[:500]!r}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise PluginConfigError(
                f"ApiSource: response from '{url}' is not valid JSON: {exc}"
            ) from exc

        # Normalise: if the response is a dict, look for the first list value
        if isinstance(data, dict):
            lists = [v for v in data.values() if isinstance(v, list)]
            if not lists:
                raise PluginConfigError(
                    f"ApiSource: JSON response from '{url}' is a dict with no list "
                    "values.  Expected a list of records or a dict wrapping one."
                )
            data = lists[0]

        if not isinstance(data, list):
            raise PluginConfigError(
                f"ApiSource: expected a JSON array from '{url}', got {type(data).__name__!r}."
            )

        try:
            return pd.DataFrame(data)
        except Exception as exc:
            raise PluginConfigError(
                f"ApiSource: could not convert API response to DataFrame: {exc}"
            ) from exc
