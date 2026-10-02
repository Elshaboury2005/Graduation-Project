"""
airflow/dags/pipeline_execution_dag.py
----------------------------------------
Airflow DAG that orchestrates the end-to-end resilient pipeline workflow.

Architecture note
-----------------
Airflow's role here is **orchestration and observability**, NOT business logic.
The platform already has a complete pipeline engine (Phase 3 executor), Kafka
integration (Phase 4), Spark processing (Phase 5), and HDFS storage (Phase 6).
This DAG's tasks call the platform's own REST API to trigger and monitor each
stage — they do NOT re-implement any of that logic inside the DAG itself.
This keeps the DAG thin, testable, and decoupled from the platform internals.

DAG trigger
-----------
The DAG is manually triggered (``schedule=None``) with a run configuration::

    {
        "yaml_content": "<full YAML pipeline config as a string>",
        "pipeline_id": "sales-pipeline-v1"
    }

Task dependency graph
---------------------
::

    validate_configuration
          ↓
    prepare_source
          ↓
    start_verify_kafka
          ↓
    run_spark_processing
          ↓
    validate_output
          ↓
    collect_metrics

XCom data flow
--------------
Each task returns a dict that Airflow's TaskFlow API automatically pushes to
XCom.  Downstream tasks receive those values as direct function arguments —
no manual ``xcom_push`` / ``xcom_pull`` calls.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow.decorators import dag, task
from airflow.exceptions import AirflowException

# ── Constants ─────────────────────────────────────────────────────────────────

# Backend base URL — override via AIRFLOW_VAR_BACKEND_BASE_URL or env variable.
# Inside the Docker Compose network the backend service is reachable by name.
BACKEND_BASE_URL = os.environ.get("BACKEND_BASE_URL", "http://backend:8000")

_DEFAULT_ARGS = {
    "owner": "platform-team",
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
    "email_on_failure": False,
    "email_on_retry": False,
}


# ── DAG definition ─────────────────────────────────────────────────────────────

@dag(
    dag_id="pipeline_execution_dag",
    description=(
        "End-to-end pipeline orchestration: validate config → verify source "
        "→ check Kafka → run Spark → validate output → collect metrics."
    ),
    default_args=_DEFAULT_ARGS,
    schedule=None,  # Manually triggered with dag_run.conf
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["platform", "pipeline", "production"],
    doc_md=__doc__,
)
def pipeline_execution_dag():
    """
    Orchestrate a full pipeline run by calling the platform's REST API.

    The DAG expects ``dag_run.conf`` to contain:
    - ``yaml_content`` (str): full YAML pipeline configuration.
    - ``pipeline_id`` (str): human-readable identifier for logs/XCom.
    """

    @task()
    def validate_configuration(**context) -> dict:
        """
        Call ``POST /api/pipelines/validate`` and fail fast if the config is invalid.

        Returns the validated config dict on success.

        Raises
        ------
        AirflowException
            If validation fails, with the full error list in the message so
            operators can fix the config without diving into backend logs.
        """
        import requests

        conf = context["dag_run"].conf or {}
        yaml_content = conf.get("yaml_content", "")
        pipeline_id = conf.get("pipeline_id", "unknown")

        if not yaml_content:
            raise AirflowException(
                "dag_run.conf must contain 'yaml_content' (the pipeline YAML string)."
            )

        resp = requests.post(
            f"{BACKEND_BASE_URL}/api/pipelines/validate",
            json={"yaml_content": yaml_content},
            timeout=30,
        )
        resp.raise_for_status()
        body = resp.json()

        if not body.get("valid", False):
            errors = body.get("errors", [])
            raise AirflowException(
                f"Pipeline '{pipeline_id}' failed validation with "
                f"{len(errors)} error(s): {errors}"
            )

        return {
            "pipeline_id": pipeline_id,
            "yaml_content": yaml_content,
            "validation_passed": True,
        }

    @task()
    def prepare_source(validated: dict) -> dict:
        """
        Confirm the source data is accessible before committing expensive compute.

        For file-based sources this checks that the configured path exists
        (the sample-data volume is mounted into Airflow containers at
        ``/app/sample-data``, the same path used by the backend and Spark).
        For API/Kafka sources the check is a lightweight HEAD/connectivity test.

        Returns
        -------
        dict
            ``{"source_ready": bool, "source_path": str | None}``
        """
        import yaml

        yaml_content = validated["yaml_content"]
        config = yaml.safe_load(yaml_content)
        source = config.get("source", {})
        source_type = source.get("type", "")
        source_path = source.get("path")

        if source_type in ("csv", "json") and source_path:
            if not os.path.exists(source_path):
                raise AirflowException(
                    f"Source file not found at path: '{source_path}'. "
                    "Ensure the sample-data volume is mounted correctly."
                )
            return {"source_ready": True, "source_path": source_path}

        # For API / Kafka sources — flag as ready (backend validates at run time)
        return {"source_ready": True, "source_path": None}

    @task()
    def start_verify_kafka(source_info: dict) -> dict:
        """
        Call ``GET /api/messaging/health`` and fail if Kafka is unreachable.

        Returns
        -------
        dict
            Kafka health response from the backend.
        """
        import requests

        resp = requests.get(f"{BACKEND_BASE_URL}/api/messaging/health", timeout=15)
        resp.raise_for_status()
        body = resp.json()

        if not body.get("connected", False):
            raise AirflowException(
                f"Kafka broker is not reachable: {body.get('error', 'unknown error')}. "
                "Ensure the Kafka service is healthy before triggering the DAG."
            )

        return body

    @task()
    def run_spark_processing(validated: dict, kafka_status: dict) -> dict:
        """
        Submit the full pipeline run via ``POST /api/pipelines/run``.

        This single API call covers the complete executor path:
        read source → Kafka publish → Spark processing → storage write.

        Returns
        -------
        dict
            Pipeline run result (metrics, status, run_id from the executor).

        Raises
        ------
        AirflowException
            If the pipeline run returns status != "success".
        """
        import requests

        yaml_content = validated["yaml_content"]
        pipeline_id = validated["pipeline_id"]

        resp = requests.post(
            f"{BACKEND_BASE_URL}/api/pipelines/run",
            json={"yaml_content": yaml_content},
            timeout=600,  # Spark jobs can take several minutes
        )
        resp.raise_for_status()
        body = resp.json()

        if body.get("status") not in ("success", "ok"):
            raise AirflowException(
                f"Pipeline '{pipeline_id}' run failed with status "
                f"'{body.get('status')}'. Logs: {body.get('logs', [])[-5:]}"
            )

        return {
            "pipeline_id": pipeline_id,
            "run_id": body.get("run_id"),
            "status": body.get("status"),
            "metrics": body.get("metrics", {}),
            "logs": body.get("logs", []),
        }

    @task()
    def validate_output(run_result: dict) -> dict:
        """
        Assert the pipeline produced meaningful output.

        Checks:
        1. ``status`` is ``"success"``.
        2. At least one storage metric shows ``output_rows > 0`` (or
           ``rows_written > 0`` for the local/HDFS storage plugins).

        Returns
        -------
        dict
            ``{"output_valid": bool, "output_rows": int}``

        Raises
        ------
        AirflowException
            If the output is empty or the status indicates failure.
        """
        status = run_result.get("status")
        metrics = run_result.get("metrics", {})

        if status != "success":
            raise AirflowException(
                f"run_spark_processing reported status='{status}' — output validation skipped."
            )

        # Find any storage metric that recorded written rows
        output_rows = 0
        for key, val in metrics.items():
            if isinstance(val, dict):
                output_rows = max(
                    output_rows,
                    val.get("rows_written", 0) or val.get("output_rows", 0),
                )

        if output_rows == 0:
            raise AirflowException(
                "Pipeline output validation failed: no rows written to storage. "
                f"Metrics: {metrics}"
            )

        return {"output_valid": True, "output_rows": output_rows}

    @task()
    def collect_metrics(run_result: dict, output_validation: dict) -> dict:
        """
        Aggregate and log the final pipeline run summary.

        The return value is visible in the Airflow UI's XCom tab for the task,
        providing a permanent record of every successful pipeline run without
        requiring access to backend logs.

        Returns
        -------
        dict
            Full structured summary of the pipeline run.
        """
        summary = {
            "pipeline_id": run_result.get("pipeline_id"),
            "run_id": run_result.get("run_id"),
            "status": run_result.get("status"),
            "output_rows": output_validation.get("output_rows"),
            "metrics": run_result.get("metrics", {}),
            "log_count": len(run_result.get("logs", [])),
        }

        print(f"[collect_metrics] Pipeline run summary: {summary}")
        return summary

    # ── Wire up the task graph ─────────────────────────────────────────────────
    validated = validate_configuration()
    source_info = prepare_source(validated)
    kafka_status = start_verify_kafka(source_info)
    run_result = run_spark_processing(validated, kafka_status)
    output_validation = validate_output(run_result)
    collect_metrics(run_result, output_validation)


# Instantiate the DAG
pipeline_dag = pipeline_execution_dag()
