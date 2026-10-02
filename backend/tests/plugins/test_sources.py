"""
tests/plugins/test_sources.py
------------------------------
Unit tests for all built-in source plugins.

Covers:
* CsvSource reads the sample CSV file correctly (row/column assertions).
* JsonSource reads the sample JSON array correctly.
* ApiSource uses a mocked requests.get — no real network calls.
* PluginConfigError raised when required config keys are missing.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

import app.plugins  # noqa: F401 — ensures all plugins are registered

from app.plugins.base import PluginConfigError
from app.plugins.sources.api_source import ApiSource
from app.plugins.sources.csv_source import CsvSource
from app.plugins.sources.json_source import JsonSource

SAMPLE_DIR = Path(__file__).parent.parent.parent / "sample-data"


# ── CsvSource ──────────────────────────────────────────────────────────────────


class TestCsvSource:
    """CsvSource reads sample CSV files into correctly shaped DataFrames."""

    @pytest.fixture(scope="class")
    def sales_df(self) -> pd.DataFrame:
        """Parse the sales sample CSV once for all tests in this class."""
        source = CsvSource()
        return source.read({"path": str(SAMPLE_DIR / "sales_sample.csv")})

    def test_returns_dataframe(self, sales_df: pd.DataFrame) -> None:
        assert isinstance(sales_df, pd.DataFrame)

    def test_correct_row_count(self, sales_df: pd.DataFrame) -> None:
        # 20 rows total (including nulls and duplicates)
        assert len(sales_df) == 20

    def test_correct_column_names(self, sales_df: pd.DataFrame) -> None:
        expected = {"transaction_id", "amount", "customer_id", "product_id", "sale_date"}
        assert expected == set(sales_df.columns)

    def test_null_values_present(self, sales_df: pd.DataFrame) -> None:
        # 3 rows have null amounts — verify nulls exist
        assert sales_df["amount"].isna().sum() == 3

    def test_duplicate_rows_present(self, sales_df: pd.DataFrame) -> None:
        # 2 pairs of exact duplicates → 2 duplicated rows (keep=False counts all)
        assert sales_df.duplicated().sum() == 2

    def test_amount_column_is_numeric(self, sales_df: pd.DataFrame) -> None:
        # pandas reads numeric columns as float64 when nulls are present
        assert pd.api.types.is_float_dtype(sales_df["amount"])

    def test_missing_path_raises_plugin_config_error(self) -> None:
        source = CsvSource()
        with pytest.raises(PluginConfigError):
            source.read({})

    def test_nonexistent_file_raises_file_not_found(self) -> None:
        source = CsvSource()
        with pytest.raises(FileNotFoundError):
            source.read({"path": "/nonexistent/path/file.csv"})

    def test_plugin_type_is_csv(self) -> None:
        assert CsvSource.plugin_type == "csv"


# ── JsonSource ─────────────────────────────────────────────────────────────────


class TestJsonSource:
    """JsonSource reads sample JSON array files into correctly shaped DataFrames."""

    @pytest.fixture(scope="class")
    def iot_df(self) -> pd.DataFrame:
        """Parse the IoT sample JSON once for all tests in this class."""
        source = JsonSource()
        return source.read({"path": str(SAMPLE_DIR / "iot_sample.json")})

    def test_returns_dataframe(self, iot_df: pd.DataFrame) -> None:
        assert isinstance(iot_df, pd.DataFrame)

    def test_correct_row_count(self, iot_df: pd.DataFrame) -> None:
        # 20 records in iot_sample.json
        assert len(iot_df) == 20

    def test_correct_column_names(self, iot_df: pd.DataFrame) -> None:
        expected = {"device_id", "temperature", "humidity", "pressure", "recorded_at"}
        assert expected == set(iot_df.columns)

    def test_null_values_present(self, iot_df: pd.DataFrame) -> None:
        # 2 null values in iot_sample.json (one null temperature, one null humidity)
        total_nulls = iot_df.isnull().sum().sum()
        assert total_nulls == 2

    def test_duplicate_rows_present(self, iot_df: pd.DataFrame) -> None:
        # 2 exact duplicate rows
        assert iot_df.duplicated().sum() == 2

    def test_temperature_column_is_numeric(self, iot_df: pd.DataFrame) -> None:
        assert pd.api.types.is_numeric_dtype(iot_df["temperature"])

    def test_missing_path_raises_plugin_config_error(self) -> None:
        source = JsonSource()
        with pytest.raises(PluginConfigError):
            source.read({})

    def test_nonexistent_file_raises_file_not_found(self) -> None:
        source = JsonSource()
        with pytest.raises(FileNotFoundError):
            source.read({"path": "/nonexistent/path/file.json"})

    def test_plugin_type_is_json(self) -> None:
        assert JsonSource.plugin_type == "json"

    def test_json_lines_format(self, tmp_path: Path) -> None:
        """JsonSource must also handle JSON Lines (one object per line)."""
        ndjson = tmp_path / "data.ndjson"
        ndjson.write_text(
            '{"id": 1, "val": "a"}\n{"id": 2, "val": "b"}\n{"id": 3, "val": "c"}\n',
            encoding="utf-8",
        )
        source = JsonSource()
        df = source.read({"path": str(ndjson)})
        assert len(df) == 3
        assert set(df.columns) == {"id", "val"}


# ── ApiSource ──────────────────────────────────────────────────────────────────


class TestApiSource:
    """ApiSource converts HTTP JSON responses to DataFrames without hitting the network."""

    def _make_mock_response(
        self,
        status_code: int = 200,
        json_data: object = None,
    ) -> MagicMock:
        """Create a mock requests.Response object."""
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.json.return_value = json_data if json_data is not None else []
        mock_resp.text = str(json_data)
        return mock_resp

    def test_reads_json_array_response(self) -> None:
        data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        mock_resp = self._make_mock_response(json_data=data)

        with patch("requests.request", return_value=mock_resp):
            source = ApiSource()
            df = source.read({"url": "https://api.example.com/data"})

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert set(df.columns) == {"id", "name"}

    def test_reads_dict_wrapping_list(self) -> None:
        """API responses that wrap the list in a dict key should also work."""
        data = {"results": [{"x": 1}, {"x": 2}, {"x": 3}]}
        mock_resp = self._make_mock_response(json_data=data)

        with patch("requests.request", return_value=mock_resp):
            source = ApiSource()
            df = source.read({"url": "https://api.example.com/wrapped"})

        assert len(df) == 3

    def test_passes_custom_headers(self) -> None:
        """Custom headers must be forwarded to requests.request."""
        data = [{"k": "v"}]
        mock_resp = self._make_mock_response(json_data=data)

        with patch("requests.request", return_value=mock_resp) as mock_req:
            source = ApiSource()
            source.read({
                "url": "https://api.example.com/secure",
                "headers": {"Authorization": "Bearer token123"},
                "method": "GET",
            })

        call_kwargs = mock_req.call_args
        assert "Authorization" in call_kwargs.kwargs["headers"]

    def test_non_200_response_raises_plugin_config_error(self) -> None:
        mock_resp = self._make_mock_response(status_code=403, json_data={"error": "Forbidden"})

        with patch("requests.request", return_value=mock_resp):
            source = ApiSource()
            with pytest.raises(PluginConfigError) as exc_info:
                source.read({"url": "https://api.example.com/secret"})

        assert "403" in str(exc_info.value)

    def test_missing_url_raises_plugin_config_error(self) -> None:
        source = ApiSource()
        with pytest.raises(PluginConfigError):
            source.read({"method": "GET"})

    def test_timeout_error_raises_plugin_config_error(self) -> None:
        import requests as req_lib

        with patch("requests.request", side_effect=req_lib.exceptions.Timeout()):
            source = ApiSource()
            with pytest.raises(PluginConfigError) as exc_info:
                source.read({"url": "https://slow.api.example.com/data"})
        assert "timed out" in str(exc_info.value).lower()

    def test_connection_error_raises_plugin_config_error(self) -> None:
        import requests as req_lib

        with patch(
            "requests.request",
            side_effect=req_lib.exceptions.ConnectionError("refused"),
        ):
            source = ApiSource()
            with pytest.raises(PluginConfigError) as exc_info:
                source.read({"url": "https://unreachable.example.com/data"})
        assert "connection" in str(exc_info.value).lower()

    def test_plugin_type_is_api(self) -> None:
        assert ApiSource.plugin_type == "api"

    def test_empty_response_returns_empty_dataframe(self) -> None:
        mock_resp = self._make_mock_response(json_data=[])

        with patch("requests.request", return_value=mock_resp):
            source = ApiSource()
            df = source.read({"url": "https://api.example.com/empty"})

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
