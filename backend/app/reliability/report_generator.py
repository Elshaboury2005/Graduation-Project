"""
app/reliability/report_generator.py
--------------------------------------
Assembles and persists the final experiment report.

The report is assembled from persisted ``ExperimentRun.results`` (metrics)
and the ``ExperimentRun`` record itself, then written to the ``Report`` model.

Report JSON shape (canonical — used by both the API and Phase 8 frontend):

.. code-block:: json

    {
        "experiment_name": "Kafka Failure Test",
        "target": "kafka",
        "failure_type": "container_stop",
        "failure_duration_seconds": 20,
        "recovery_time_seconds": 12.4,
        "expected_records": 10000,
        "processed_records": 10000,
        "data_loss": 0,
        "average_throughput": 1250.0,
        "availability_percentage": 99.8,
        "result": "PASS"
    }
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    Build and persist a structured experiment report.

    Reads from ``ExperimentRun.results`` (persisted by ``MetricsCollector``)
    and writes the canonical report dict to the ``Report`` model.
    """

    def generate(self, experiment_run_id: uuid.UUID, db_session) -> dict[str, Any]:
        """
        Assemble a complete experiment report from persisted run data.

        Parameters
        ----------
        experiment_run_id : uuid.UUID
            The completed experiment run to report on.
        db_session : sqlalchemy.orm.Session
            Active synchronous database session.

        Returns
        -------
        dict
            The canonical report structure (see module docstring).
        """
        from app.models.experiment_run import ExperimentRun
        from app.models.experiment import Experiment
        from app.models.report import Report

        run = db_session.get(ExperimentRun, experiment_run_id)
        if run is None:
            raise ValueError(f"ExperimentRun {experiment_run_id} not found.")

        # Retrieve the parent experiment for the name
        experiment = db_session.get(Experiment, run.experiment_id)
        experiment_name = experiment.name if experiment else "Unknown"

        results = run.results or {}

        # ── Extract metrics from results dict ──────────────────────────────────
        report_dict: dict[str, Any] = {
            "experiment_run_id": str(experiment_run_id),
            "experiment_name": experiment_name,
            "target": results.get("target_service", "unknown"),
            "failure_type": results.get("fault_type", "unknown"),
            "failure_duration_seconds": results.get("fault_duration", 0),
            "recovery_time_seconds": results.get("recovery_time_seconds"),
            "expected_records": results.get("expected_record_count", 0),
            "processed_records": results.get("actual_records", 0),
            "data_loss": results.get("data_loss", 0),
            "average_throughput": results.get("throughput_records_per_sec", 0.0),
            "availability_percentage": results.get("availability_percentage", 0.0),
            "result": results.get("result", "UNKNOWN"),
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "status": run.status,
        }

        # ── Persist to Report model ────────────────────────────────────────────
        report = Report(
            title=f"Experiment Report: {experiment_name}",
            report_type="chaos_experiment",
            content=None,
            storage_uri=None,
            metadata_=report_dict,
        )
        db_session.add(report)
        db_session.flush()
        db_session.refresh(report)

        report_dict["report_id"] = str(report.id)
        logger.info(
            "ReportGenerator: report %s generated for run %s (result=%s).",
            report.id,
            experiment_run_id,
            report_dict["result"],
        )
        return report_dict
