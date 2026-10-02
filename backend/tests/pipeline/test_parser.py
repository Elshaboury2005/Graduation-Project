"""
tests/pipeline/test_parser.py
------------------------------
Unit tests for :class:`~app.pipeline.parser.PipelineConfigParser`.

These tests run entirely in-process — no Docker, no database, no network.
They cover:

* Successful parsing of both valid sample YAML files into ``PipelineConfig``
  objects, with assertions on specific field values.
* ``ConfigParseError`` raised on syntactically broken YAML strings.
* ``ConfigValidationError`` raised when YAML is valid but violates the schema
  (e.g. unknown operation type).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.pipeline.config_models import (
    AggregateOperation,
    FilterOperation,
    PipelineConfig,
    RemoveDuplicatesOperation,
    RemoveNullsOperation,
    RenameColumnsOperation,
    SelectColumnsOperation,
    TypeConversionOperation,
)
from app.pipeline.exceptions import ConfigParseError, ConfigValidationError
from app.pipeline.parser import PipelineConfigParser

# ── Helpers ────────────────────────────────────────────────────────────────────

SAMPLE_DIR = Path(__file__).parent.parent.parent / "sample-configs"


def read_sample(filename: str) -> str:
    """Return the raw text content of a file in sample-configs/."""
    path = SAMPLE_DIR / filename
    if not path.exists():
        pytest.skip(f"Sample file not found: {path}")
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def parser() -> PipelineConfigParser:
    """A shared parser instance for the entire test module."""
    return PipelineConfigParser()


# ── Valid file: sales pipeline ─────────────────────────────────────────────────


class TestValidSalesPipeline:
    """Parser correctly handles the complete sales pipeline YAML."""

    @pytest.fixture(scope="class")
    def config(self, parser: PipelineConfigParser) -> PipelineConfig:
        """Parse the sales pipeline once for all tests in this class."""
        return parser.parse_string(read_sample("valid_sales_pipeline.yaml"))

    def test_returns_pipeline_config_instance(self, config: PipelineConfig) -> None:
        """parse_string() must return a PipelineConfig — not a plain dict."""
        assert isinstance(config, PipelineConfig)

    def test_pipeline_name(self, config: PipelineConfig) -> None:
        assert config.pipeline.name == "sales-pipeline"

    def test_pipeline_version(self, config: PipelineConfig) -> None:
        assert config.pipeline.version == "1.0"

    def test_source_type(self, config: PipelineConfig) -> None:
        assert config.source.type == "csv"

    def test_source_path(self, config: PipelineConfig) -> None:
        assert config.source.path == "/data/raw/sales.csv"

    def test_schema_has_expected_columns(self, config: PipelineConfig) -> None:
        names = [col.name for col in config.pipeline_schema]
        assert "transaction_id" in names
        assert "amount" in names
        assert "customer_id" in names

    def test_schema_column_types(self, config: PipelineConfig) -> None:
        by_name = {col.name: col.type for col in config.pipeline_schema}
        assert by_name["transaction_id"] == "string"
        assert by_name["amount"] == "double"

    def test_processing_operations_count(self, config: PipelineConfig) -> None:
        # Sales pipeline defines 7 operations
        assert len(config.processing.operations) == 7

    def test_remove_nulls_operation_present(self, config: PipelineConfig) -> None:
        assert any(
            isinstance(op, RemoveNullsOperation)
            for op in config.processing.operations
        )

    def test_remove_duplicates_operation_present(self, config: PipelineConfig) -> None:
        assert any(
            isinstance(op, RemoveDuplicatesOperation)
            for op in config.processing.operations
        )

    def test_filter_operation_has_condition(self, config: PipelineConfig) -> None:
        filters = [
            op for op in config.processing.operations if isinstance(op, FilterOperation)
        ]
        assert len(filters) == 1
        assert filters[0].condition == "amount > 0"

    def test_select_columns_operation(self, config: PipelineConfig) -> None:
        selects = [
            op for op in config.processing.operations
            if isinstance(op, SelectColumnsOperation)
        ]
        assert len(selects) == 1
        assert "transaction_id" in selects[0].columns
        assert "amount" in selects[0].columns

    def test_rename_columns_operation(self, config: PipelineConfig) -> None:
        renames = [
            op for op in config.processing.operations
            if isinstance(op, RenameColumnsOperation)
        ]
        assert len(renames) == 1
        assert renames[0].mapping["transaction_id"] == "txn_id"

    def test_type_conversion_operation(self, config: PipelineConfig) -> None:
        conversions = [
            op for op in config.processing.operations
            if isinstance(op, TypeConversionOperation)
        ]
        assert len(conversions) == 1
        assert conversions[0].column == "amount"
        assert conversions[0].to_type == "double"

    def test_aggregate_operation(self, config: PipelineConfig) -> None:
        aggs = [
            op for op in config.processing.operations
            if isinstance(op, AggregateOperation)
        ]
        assert len(aggs) == 1
        assert aggs[0].group_by == "customer_id"
        assert aggs[0].operation == "sum"
        assert aggs[0].field == "amount"

    def test_streaming_enabled(self, config: PipelineConfig) -> None:
        assert config.streaming.enabled is True

    def test_messaging_broker(self, config: PipelineConfig) -> None:
        assert config.messaging is not None
        assert config.messaging.broker == "kafka"
        assert config.messaging.topic == "sales-events"
        assert config.messaging.partitions == 3

    def test_processing_engine(self, config: PipelineConfig) -> None:
        assert config.processing_engine.type == "spark"

    def test_storage(self, config: PipelineConfig) -> None:
        assert config.storage.type == "hdfs"
        assert config.storage.path == "/data/processed/sales"

    def test_monitoring_enabled(self, config: PipelineConfig) -> None:
        assert config.monitoring is not None
        assert config.monitoring.enabled is True


# ── Valid file: IoT pipeline ───────────────────────────────────────────────────


class TestValidIoTPipeline:
    """Parser correctly handles the IoT sensor pipeline YAML."""

    @pytest.fixture(scope="class")
    def config(self, parser: PipelineConfigParser) -> PipelineConfig:
        return parser.parse_string(read_sample("valid_iot_pipeline.yaml"))

    def test_pipeline_name(self, config: PipelineConfig) -> None:
        assert config.pipeline.name == "iot-sensor-pipeline"

    def test_pipeline_version(self, config: PipelineConfig) -> None:
        assert config.pipeline.version == "2.1"

    def test_source_type_is_json(self, config: PipelineConfig) -> None:
        assert config.source.type == "json"

    def test_schema_has_temperature_column(self, config: PipelineConfig) -> None:
        names = [col.name for col in config.pipeline_schema]
        assert "temperature" in names
        assert "humidity" in names
        assert "device_id" in names

    def test_streaming_disabled(self, config: PipelineConfig) -> None:
        assert config.streaming.enabled is False

    def test_messaging_is_none_when_streaming_disabled(
        self, config: PipelineConfig
    ) -> None:
        # IoT pipeline is batch-mode — no messaging needed
        assert config.messaging is None

    def test_storage_type_is_local(self, config: PipelineConfig) -> None:
        assert config.storage.type == "local"

    def test_storage_path_is_absolute(self, config: PipelineConfig) -> None:
        assert config.storage.path.startswith("/")

    def test_aggregate_operation_uses_avg(self, config: PipelineConfig) -> None:
        aggs = [
            op for op in config.processing.operations
            if isinstance(op, AggregateOperation)
        ]
        assert len(aggs) == 1
        assert aggs[0].operation == "avg"
        assert aggs[0].field == "temperature"

    def test_parse_file_method(self, parser: PipelineConfigParser) -> None:
        """parse_file() must produce the same result as parse_string()."""
        path = str(SAMPLE_DIR / "valid_iot_pipeline.yaml")
        config_from_file = parser.parse_file(path)
        assert config_from_file.pipeline.name == "iot-sensor-pipeline"


# ── Error case: syntactically broken YAML ─────────────────────────────────────


class TestMalformedYAML:
    """parse_string() raises ConfigParseError on invalid YAML syntax."""

    def test_unclosed_bracket_raises_parse_error(
        self, parser: PipelineConfigParser
    ) -> None:
        broken = "pipeline:\n  name: [unclosed\nBROKEN{{"
        with pytest.raises(ConfigParseError) as exc_info:
            parser.parse_string(broken)
        msg = str(exc_info.value).lower()
        assert "yaml" in msg or "parse" in msg or "syntax" in msg

    def test_bad_indentation_raises_parse_error(
        self, parser: PipelineConfigParser
    ) -> None:
        broken = "pipeline:\nname: bad-indent\n  version: 1.0"
        with pytest.raises(ConfigParseError):
            parser.parse_string(broken)

    def test_tab_indentation_raises_parse_error(
        self, parser: PipelineConfigParser
    ) -> None:
        # YAML forbids tabs as indentation
        broken = "pipeline:\n\tname: tab-indent"
        with pytest.raises(ConfigParseError):
            parser.parse_string(broken)

    def test_bare_string_raises_parse_error(
        self, parser: PipelineConfigParser
    ) -> None:
        # A bare string is not a mapping — _validate catches this
        with pytest.raises((ConfigParseError, ConfigValidationError)):
            parser.parse_string("just a plain string")

    def test_error_message_is_informative(
        self, parser: PipelineConfigParser
    ) -> None:
        broken = "pipeline:\n  name: [\nBROKEN"
        with pytest.raises(ConfigParseError) as exc_info:
            parser.parse_string(broken)
        # Must not be an empty or generic message
        assert len(str(exc_info.value)) > 10

    def test_file_not_found_raises_file_not_found_error(
        self, parser: PipelineConfigParser
    ) -> None:
        with pytest.raises(FileNotFoundError) as exc_info:
            parser.parse_file("/nonexistent/path/pipeline.yaml")
        assert "not found" in str(exc_info.value).lower()


# ── Error case: valid YAML, invalid schema ─────────────────────────────────────


class TestSchemaValidationErrors:
    """parse_string() raises ConfigValidationError on schema violations."""

    def test_invalid_bad_operation_raises_validation_error(
        self, parser: PipelineConfigParser
    ) -> None:
        """Unknown operation type must produce a ConfigValidationError."""
        content = read_sample("invalid_bad_operation.yaml")
        with pytest.raises(ConfigValidationError) as exc_info:
            parser.parse_string(content)

        errors = exc_info.value.errors
        assert len(errors) > 0

    def test_invalid_bad_operation_error_references_processing(
        self, parser: PipelineConfigParser
    ) -> None:
        """Error field path must reference the processing.operations section."""
        content = read_sample("invalid_bad_operation.yaml")
        with pytest.raises(ConfigValidationError) as exc_info:
            parser.parse_string(content)

        fields = [e["field"] for e in exc_info.value.errors]
        assert any("processing" in f or "operation" in f for f in fields), (
            f"Expected a field containing 'processing' or 'operation', got: {fields}"
        )

    def test_invalid_bad_operation_has_meaningful_message(
        self, parser: PipelineConfigParser
    ) -> None:
        content = read_sample("invalid_bad_operation.yaml")
        with pytest.raises(ConfigValidationError) as exc_info:
            parser.parse_string(content)

        messages = [e["message"] for e in exc_info.value.errors]
        assert all(len(m) > 5 for m in messages), (
            f"All error messages must be non-trivial; got: {messages}"
        )

    def test_invalid_missing_storage_raises_validation_error(
        self, parser: PipelineConfigParser
    ) -> None:
        content = read_sample("invalid_missing_storage.yaml")
        with pytest.raises(ConfigValidationError) as exc_info:
            parser.parse_string(content)

        fields = [e["field"] for e in exc_info.value.errors]
        assert any("storage" in f for f in fields), (
            f"Expected a 'storage' field in errors, got: {fields}"
        )

    def test_invalid_pipeline_name_uppercase(
        self, parser: PipelineConfigParser
    ) -> None:
        """Pipeline names must be lowercase slug — reject uppercase."""
        yaml_content = """\
pipeline:
  name: Invalid Pipeline Name
  version: "1.0"
source:
  type: csv
  path: /data/in.csv
schema:
  - name: id
    type: string
processing:
  operations:
    - type: remove_nulls
streaming:
  enabled: false
processing_engine:
  type: spark
storage:
  type: local
  path: /data/out
"""
        with pytest.raises(ConfigValidationError) as exc_info:
            parser.parse_string(yaml_content)
        fields = [e["field"] for e in exc_info.value.errors]
        assert any("name" in f for f in fields)

    def test_invalid_version_string(self, parser: PipelineConfigParser) -> None:
        """Version must be N.N or N.N.N — 'latest' must be rejected."""
        yaml_content = """\
pipeline:
  name: test-pipeline
  version: latest
source:
  type: csv
  path: /data/in.csv
schema:
  - name: id
    type: string
processing:
  operations:
    - type: remove_nulls
streaming:
  enabled: false
processing_engine:
  type: spark
storage:
  type: local
  path: /data/out
"""
        with pytest.raises(ConfigValidationError) as exc_info:
            parser.parse_string(yaml_content)
        fields = [e["field"] for e in exc_info.value.errors]
        assert any("version" in f for f in fields)

    def test_extra_unknown_field_rejected(
        self, parser: PipelineConfigParser
    ) -> None:
        """extra='forbid' must reject unknown top-level keys."""
        yaml_content = """\
pipeline:
  name: test-pipeline
  version: "1.0"
source:
  type: csv
  path: /data/in.csv
schema:
  - name: id
    type: string
processing:
  operations:
    - type: remove_nulls
streaming:
  enabled: false
processing_engine:
  type: spark
storage:
  type: local
  path: /data/out
completely_unknown_section:
  foo: bar
"""
        with pytest.raises(ConfigValidationError):
            parser.parse_string(yaml_content)
