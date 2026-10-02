"""
tests/airflow/test_dag_integrity.py
-------------------------------------
Lightweight DAG integrity tests — no running Airflow instance required.

Uses Airflow's ``DagBag`` to import ``pipeline_execution_dag.py`` directly
and validates its structure:

* No import errors.
* Exactly 6 tasks with the expected IDs.
* Tasks are connected in the correct dependency order.
* ``schedule`` is ``None`` (manually triggered only).

These tests run as part of the standard ``pytest tests/ -m "not integration"``
suite and are fast (< 2 seconds on first import once Airflow is installed).

Prerequisites
-------------
``apache-airflow`` must be installed in the test environment.  If it is not,
all tests in this module are skipped gracefully.  To install::

    pip install apache-airflow==2.10.3
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# ── Skip if airflow is not installed ──────────────────────────────────────────

try:
    import airflow  # noqa: F401
    AIRFLOW_AVAILABLE = True
except ImportError:
    AIRFLOW_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not AIRFLOW_AVAILABLE,
    reason="apache-airflow is not installed — run `pip install apache-airflow==2.10.3`",
)

# ── DAG path ──────────────────────────────────────────────────────────────────

# Resolve path regardless of where pytest is invoked from
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
_DAGS_DIR = _PROJECT_ROOT / "airflow" / "dags"

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def dagbag():
    """Load the DAGs directory using Airflow's DagBag."""
    from airflow.models import DagBag

    return DagBag(dag_folder=str(_DAGS_DIR), include_examples=False)


@pytest.fixture(scope="module")
def dag(dagbag):
    """Return the pipeline_execution_dag instance."""
    dag_obj = dagbag.get_dag("pipeline_execution_dag")
    assert dag_obj is not None, (
        f"pipeline_execution_dag not found in DagBag. "
        f"Import errors: {dagbag.import_errors}"
    )
    return dag_obj


# ── Tests ──────────────────────────────────────────────────────────────────────


class TestDagImport:
    """The DAG file must import without errors."""

    def test_no_import_errors(self, dagbag) -> None:
        """DagBag must have zero import errors for the pipeline_execution_dag."""
        assert dagbag.import_errors == {}, (
            f"DAG import errors: {dagbag.import_errors}"
        )

    def test_dag_exists_in_dagbag(self, dagbag) -> None:
        """pipeline_execution_dag must appear in the loaded DagBag."""
        assert "pipeline_execution_dag" in dagbag.dag_ids


class TestDagStructure:
    """The DAG must have the expected shape."""

    EXPECTED_TASK_IDS = {
        "validate_configuration",
        "prepare_source",
        "start_verify_kafka",
        "run_spark_processing",
        "validate_output",
        "collect_metrics",
    }

    def test_dag_has_exactly_six_tasks(self, dag) -> None:
        """The DAG must contain exactly 6 tasks."""
        assert len(dag.tasks) == 6, (
            f"Expected 6 tasks, got {len(dag.tasks)}: "
            f"{[t.task_id for t in dag.tasks]}"
        )

    def test_task_ids_are_correct(self, dag) -> None:
        """All 6 expected task IDs must be present."""
        actual_ids = {t.task_id for t in dag.tasks}
        assert actual_ids == self.EXPECTED_TASK_IDS, (
            f"Task ID mismatch.\nExpected: {self.EXPECTED_TASK_IDS}\nGot: {actual_ids}"
        )

    def test_schedule_is_none(self, dag) -> None:
        """schedule must be None — DAG is manually/API-triggered only."""
        assert dag.schedule_interval is None, (
            f"Expected schedule=None, got: {dag.schedule_interval!r}"
        )

    def test_catchup_is_false(self, dag) -> None:
        """catchup must be False to prevent historical backfill runs."""
        assert dag.catchup is False


class TestDagDependencies:
    """Tasks must be wired in the documented execution order."""

    def _downstream_ids(self, dag, task_id: str) -> set[str]:
        """Return the direct downstream task IDs of a named task."""
        task = dag.get_task(task_id)
        return {t.task_id for t in task.downstream_list}

    def _upstream_ids(self, dag, task_id: str) -> set[str]:
        """Return the direct upstream task IDs of a named task."""
        task = dag.get_task(task_id)
        return {t.task_id for t in task.upstream_list}

    def test_validate_configuration_has_no_upstream(self, dag) -> None:
        """validate_configuration is the root — no upstream tasks."""
        assert self._upstream_ids(dag, "validate_configuration") == set()

    def test_prepare_source_follows_validate(self, dag) -> None:
        """prepare_source must have validate_configuration as upstream."""
        assert "validate_configuration" in self._upstream_ids(dag, "prepare_source")

    def test_start_verify_kafka_follows_prepare(self, dag) -> None:
        """start_verify_kafka must follow prepare_source."""
        assert "prepare_source" in self._upstream_ids(dag, "start_verify_kafka")

    def test_run_spark_processing_follows_kafka(self, dag) -> None:
        """run_spark_processing must follow start_verify_kafka."""
        assert "start_verify_kafka" in self._upstream_ids(dag, "run_spark_processing")

    def test_validate_output_follows_run(self, dag) -> None:
        """validate_output must follow run_spark_processing."""
        assert "run_spark_processing" in self._upstream_ids(dag, "validate_output")

    def test_collect_metrics_is_terminal(self, dag) -> None:
        """collect_metrics must have no downstream tasks — it is the leaf node."""
        assert self._downstream_ids(dag, "collect_metrics") == set()

    def test_collect_metrics_has_correct_upstreams(self, dag) -> None:
        """collect_metrics must depend on both run_spark_processing and validate_output."""
        upstreams = self._upstream_ids(dag, "collect_metrics")
        assert "run_spark_processing" in upstreams
        assert "validate_output" in upstreams


class TestDagMetadata:
    """DAG-level metadata checks."""

    def test_dag_has_tags(self, dag) -> None:
        """DAG must be tagged for discoverability in the Airflow UI."""
        assert len(dag.tags) > 0

    def test_dag_has_default_args_with_retries(self, dag) -> None:
        """default_args must include retries >= 1."""
        retries = dag.default_args.get("retries", 0)
        assert retries >= 1, f"Expected retries >= 1, got {retries}"
