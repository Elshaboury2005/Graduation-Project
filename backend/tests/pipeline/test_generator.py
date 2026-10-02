"""
tests/pipeline/test_generator.py
----------------------------------
Unit tests for :class:`~app.pipeline.generator.PipelineGenerator`.

Covers:
* Generating a plan from the valid sales pipeline config produces the correct
  ordered list of steps (source → processors in order → storage).
* Each step has the correct step_type, plugin_type, and name.
* Generating a plan for a config that references an unregistered plugin type
  raises :class:`~app.plugins.registry.PluginNotFoundError`.
* ExecutionPlan property accessors (source_step, processor_steps, storage_step)
  return the expected steps.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import app.plugins  # noqa: F401 — ensures all plugins are registered

from app.pipeline.config_models import PipelineConfig
from app.pipeline.generator import ExecutionPlan, ExecutionStep, PipelineGenerator
from app.plugins.registry import PluginNotFoundError

SAMPLE_CONFIGS_DIR = Path(__file__).parent.parent.parent / "sample-configs"
SAMPLE_DATA_DIR = Path(__file__).parent.parent.parent / "sample-data"


# ── Shared fixtures ────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def generator() -> PipelineGenerator:
    """Shared PipelineGenerator instance (stateless)."""
    return PipelineGenerator()


def make_minimal_config(overrides: dict | None = None) -> PipelineConfig:
    """
    Build a minimal valid PipelineConfig.

    Uses ``local`` storage so all plugins are registered.  Accepts top-level
    ``overrides`` (shallow merge) for testing specific scenarios.
    """
    base = {
        "pipeline": {"name": "gen-test-pipeline", "version": "1.0"},
        "source": {"type": "csv", "path": str(SAMPLE_DATA_DIR / "sales_sample.csv")},
        "schema": [
            {"name": "transaction_id", "type": "string"},
            {"name": "amount", "type": "double"},
            {"name": "customer_id", "type": "string"},
            {"name": "product_id", "type": "string"},
            {"name": "sale_date", "type": "string"},
        ],
        "processing": {
            "operations": [
                {"type": "remove_nulls"},
                {"type": "remove_duplicates"},
                {"type": "filter", "condition": "amount > 0"},
            ]
        },
        "streaming": {"enabled": False},
        "processing_engine": {"type": "spark"},
        "storage": {"type": "local", "path": "/tmp/test_output"},
    }
    if overrides:
        base.update(overrides)
    return PipelineConfig.model_validate(base)


# ── Plan structure ─────────────────────────────────────────────────────────────


class TestPlanStructure:
    """The generated plan must have the correct step count and ordering."""

    def test_returns_execution_plan(self, generator: PipelineGenerator) -> None:
        config = make_minimal_config()
        plan = generator.generate(config)
        assert isinstance(plan, ExecutionPlan)

    def test_plan_has_correct_pipeline_name(self, generator: PipelineGenerator) -> None:
        config = make_minimal_config()
        plan = generator.generate(config)
        assert plan.pipeline_name == "gen-test-pipeline"

    def test_plan_has_correct_pipeline_version(self, generator: PipelineGenerator) -> None:
        config = make_minimal_config()
        plan = generator.generate(config)
        assert plan.pipeline_version == "1.0"

    def test_step_count_is_source_plus_processors_plus_storage(
        self, generator: PipelineGenerator
    ) -> None:
        config = make_minimal_config()
        # 1 source + 3 processors + 1 storage = 5
        plan = generator.generate(config)
        assert len(plan.steps) == 5

    def test_first_step_is_source(self, generator: PipelineGenerator) -> None:
        plan = generator.generate(make_minimal_config())
        assert plan.steps[0].step_type == "source"

    def test_last_step_is_storage(self, generator: PipelineGenerator) -> None:
        plan = generator.generate(make_minimal_config())
        assert plan.steps[-1].step_type == "storage"

    def test_middle_steps_are_all_processors(
        self, generator: PipelineGenerator
    ) -> None:
        plan = generator.generate(make_minimal_config())
        middle = plan.steps[1:-1]
        assert all(s.step_type == "processor" for s in middle)

    def test_processor_steps_in_config_order(
        self, generator: PipelineGenerator
    ) -> None:
        plan = generator.generate(make_minimal_config())
        proc_types = [s.plugin_type for s in plan.processor_steps]
        assert proc_types == ["remove_nulls", "remove_duplicates", "filter"]


# ── Step properties ────────────────────────────────────────────────────────────


class TestStepProperties:
    """Each step must have the correct plugin_type, name, and instantiated plugin."""

    def test_source_step_plugin_type(self, generator: PipelineGenerator) -> None:
        plan = generator.generate(make_minimal_config())
        assert plan.source_step.plugin_type == "csv"

    def test_source_step_name_format(self, generator: PipelineGenerator) -> None:
        plan = generator.generate(make_minimal_config())
        assert plan.source_step.name == "source:csv"

    def test_storage_step_plugin_type(self, generator: PipelineGenerator) -> None:
        plan = generator.generate(make_minimal_config())
        assert plan.storage_step.plugin_type == "local"

    def test_storage_step_name_format(self, generator: PipelineGenerator) -> None:
        plan = generator.generate(make_minimal_config())
        assert plan.storage_step.name == "storage:local"

    def test_processor_step_names_include_index(
        self, generator: PipelineGenerator
    ) -> None:
        plan = generator.generate(make_minimal_config())
        proc_names = [s.name for s in plan.processor_steps]
        assert proc_names == [
            "processor:remove_nulls:0",
            "processor:remove_duplicates:1",
            "processor:filter:2",
        ]

    def test_source_step_config_contains_path(
        self, generator: PipelineGenerator
    ) -> None:
        plan = generator.generate(make_minimal_config())
        assert "path" in plan.source_step.config

    def test_storage_step_config_contains_path(
        self, generator: PipelineGenerator
    ) -> None:
        plan = generator.generate(make_minimal_config())
        assert "path" in plan.storage_step.config

    def test_filter_step_config_contains_condition(
        self, generator: PipelineGenerator
    ) -> None:
        plan = generator.generate(make_minimal_config())
        filter_step = next(s for s in plan.processor_steps if s.plugin_type == "filter")
        assert "condition" in filter_step.config
        assert filter_step.config["condition"] == "amount > 0"

    def test_steps_have_instantiated_plugins(
        self, generator: PipelineGenerator
    ) -> None:
        plan = generator.generate(make_minimal_config())
        for step in plan.steps:
            assert step.plugin is not None


# ── ExecutionPlan property accessors ───────────────────────────────────────────


class TestExecutionPlanAccessors:
    """source_step, processor_steps, and storage_step must return the right steps."""

    def test_source_step_accessor(self, generator: PipelineGenerator) -> None:
        plan = generator.generate(make_minimal_config())
        assert plan.source_step is plan.steps[0]

    def test_storage_step_accessor(self, generator: PipelineGenerator) -> None:
        plan = generator.generate(make_minimal_config())
        assert plan.storage_step is plan.steps[-1]

    def test_processor_steps_accessor_count(
        self, generator: PipelineGenerator
    ) -> None:
        plan = generator.generate(make_minimal_config())
        assert len(plan.processor_steps) == 3


# ── Valid sales pipeline YAML ──────────────────────────────────────────────────


class TestSalesPipelineYaml:
    """Generate a plan from the valid_sales_pipeline.yaml sample config."""

    @pytest.fixture(scope="class")
    def plan(self, generator: PipelineGenerator) -> ExecutionPlan:
        """Parse the YAML and generate a plan (storage is hdfs — registered stub)."""
        from app.pipeline.parser import PipelineConfigParser
        content = (SAMPLE_CONFIGS_DIR / "valid_sales_pipeline.yaml").read_text(encoding="utf-8")
        config = PipelineConfigParser().parse_string(content)
        return generator.generate(config)

    def test_plan_has_correct_name(self, plan: ExecutionPlan) -> None:
        assert plan.pipeline_name == "sales-pipeline"

    def test_plan_has_7_processor_steps(self, plan: ExecutionPlan) -> None:
        # valid_sales_pipeline.yaml defines 7 operations
        assert len(plan.processor_steps) == 7

    def test_plan_source_is_csv(self, plan: ExecutionPlan) -> None:
        assert plan.source_step.plugin_type == "csv"

    def test_plan_storage_is_hdfs(self, plan: ExecutionPlan) -> None:
        # hdfs is registered as a stub — generator should succeed
        assert plan.storage_step.plugin_type == "hdfs"


# ── Unregistered plugin type ───────────────────────────────────────────────────


class TestUnregisteredPluginType:
    """Generating a plan for a config with an unregistered plugin must fail fast."""

    def test_unregistered_storage_raises_plugin_not_found(
        self, generator: PipelineGenerator
    ) -> None:
        """
        'minio' is a valid Pydantic storage type (it's in the Literal) but
        has no registered plugin in Phase 3 — should raise PluginNotFoundError.
        """
        config = make_minimal_config(
            {"storage": {"type": "minio", "path": "/minio/bucket/output"}}
        )
        with pytest.raises(PluginNotFoundError) as exc_info:
            generator.generate(config)
        assert "minio" in str(exc_info.value)

    def test_error_message_lists_available_storage_types(
        self, generator: PipelineGenerator
    ) -> None:
        config = make_minimal_config(
            {"storage": {"type": "minio", "path": "/minio/output"}}
        )
        with pytest.raises(PluginNotFoundError) as exc_info:
            generator.generate(config)
        # Must mention at least the registered types in the error
        error_text = str(exc_info.value)
        assert "local" in error_text or "hdfs" in error_text
