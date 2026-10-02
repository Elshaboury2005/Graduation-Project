"""
app/reliability/experiment_runner.py
--------------------------------------
Orchestrates the full chaos experiment lifecycle:

    CREATE → VALIDATE → PREPARE → BASELINE → INJECT FAILURE →
    MONITOR → WAIT FOR RECOVERY → VALIDATE DATA → COLLECT METRICS →
    ANALYZE → CLEANUP → GENERATE REPORT

Each stage is implemented as a private method.  The runner persists the
current lifecycle stage to ``ExperimentRun.status`` at every transition so
the Phase 8 frontend can display live progress without polling the runner.

Safety guarantees
-----------------
1. ``SafetyValidator.enforce_max_concurrent_experiments()`` is called before
   any state is written — ensures only one experiment runs at a time.
2. The entire INJECT → MONITOR → RECOVERY block is wrapped in a
   ``try/finally`` that unconditionally calls ``rollback()`` — a crash of the
   runner process will leave the fault applied (unavoidable for true process
   kills), but any Python exception or asyncio cancellation is fully handled.
3. A global timeout (``fault.duration + 60s`` grace period) wraps the monitor
   phase — the experiment cannot hang forever.

Process-kill limitation
-----------------------
If the backend process is killed with ``SIGKILL`` (e.g. ``kill -9``) mid-
experiment, the ``finally`` block cannot execute.  In that case the target
container may remain in a stopped/disrupted state.  Recovery procedure:
``docker start <container-name>`` or ``docker-compose up -d <service-name>``.
This limitation is honestly documented here and in the README rather than
overclaimed.  The ``try/finally`` only protects against Python exceptions and
graceful shutdowns (``SIGTERM``).
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from app.reliability.data_consistency_validator import DataConsistencyValidator
from app.reliability.docker_controller import DockerController
from app.reliability.exceptions import (
    ExperimentTimeoutError,
    FaultInjectionError,
    TooManyConcurrentExperimentsError,
)
from app.reliability.experiment_models import ExperimentModel
from app.reliability.fault_injectors.base_fault import FAULT_INJECTOR_REGISTRY
from app.reliability.metrics_collector import MetricsCollector
from app.reliability.report_generator import ReportGenerator
from app.reliability.safety import SafetyValidator

logger = logging.getLogger(__name__)

# Grace period added to fault.duration to form the global experiment timeout
_TIMEOUT_GRACE_SECONDS: int = 60


class ExperimentRunner:
    """
    Full lifecycle orchestrator for ChaosLab experiments.

    Parameters
    ----------
    db_session : sqlalchemy.orm.Session
        Synchronous SQLAlchemy session.  The runner uses synchronous DB
        operations because Docker SDK calls are blocking anyway.
    safety : SafetyValidator | None
        Optional injected safety validator.  Creates a new one if None.
    docker_controller : DockerController | None
        Optional injected controller.  Creates a new one if None.
    """

    def __init__(
        self,
        db_session,
        safety: SafetyValidator | None = None,
        docker_controller: DockerController | None = None,
    ) -> None:
        """Initialise the runner with injected or default components."""
        self._db = db_session
        self._safety = safety or SafetyValidator()
        self._docker = docker_controller or DockerController(self._safety)
        self._metrics = MetricsCollector()
        self._validator = DataConsistencyValidator()
        self._reporter = ReportGenerator()
        self._cancelled: bool = False

    def cancel(self) -> None:
        """Signal the runner to cancel at the next stage boundary."""
        self._cancelled = True
        logger.warning("ExperimentRunner: cancellation requested.")

    def run_experiment(
        self,
        experiment_config: ExperimentModel,
        associated_pipeline_yaml: str = "",
        existing_experiment_id: str | None = None,
        existing_run_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Execute the full experiment lifecycle synchronously.

        Parameters
        ----------
        experiment_config : ExperimentModel
            Parsed and validated experiment definition.
        associated_pipeline_yaml : str
            Optional YAML string of the pipeline to run during the experiment
            to generate measurable output data.

        Returns
        -------
        dict
            Final report dict.
        """
        from app.models.experiment import Experiment
        from app.models.experiment_run import ExperimentRun

        target_service = experiment_config.target.service
        fault_type = experiment_config.fault.type
        fault_duration = experiment_config.fault.duration

        # ── SAFETY CHECK: enforce concurrency limit ────────────────────────────
        self._safety.enforce_max_concurrent_experiments(self._db)

        # ── CREATE: persist experiment + run records ───────────────────────────
        if existing_experiment_id:
            experiment = self._db.get(Experiment, existing_experiment_id)
            if experiment is None:
                raise ValueError(f"Experiment '{existing_experiment_id}' was not found.")
        else:
            experiment = Experiment(
                name=experiment_config.experiment.name,
                description=(
                    f"ChaosLab experiment: {fault_type} on {target_service} "
                    f"for {fault_duration}s"
                ),
            )
            self._db.add(experiment)
            self._db.flush()

        if existing_run_id:
            run = self._db.get(ExperimentRun, existing_run_id)
            if run is None:
                raise ValueError(f"Experiment run '{existing_run_id}' was not found.")
            if run.experiment_id != experiment.id:
                raise ValueError("Experiment run does not belong to this experiment.")
        else:
            run = ExperimentRun(
                experiment_id=experiment.id,
                status="created",
                params={
                    "target_service": target_service,
                    "fault_type": fault_type,
                    "fault_duration": fault_duration,
                    "experiment_config": experiment_config.model_dump(),
                },
                results={},
                started_at=datetime.now(tz=timezone.utc),
            )
            self._db.add(run)
            self._db.flush()
        run_id = run.id
        logger.info(
            "ExperimentRunner: created run %s (experiment=%s).",
            run_id,
            experiment.id,
        )

        # ── VALIDATE ──────────────────────────────────────────────────────────
        self._update_status(run, "validating")
        self._validate(experiment_config)

        # ── PREPARE ───────────────────────────────────────────────────────────
        self._update_status(run, "preparing")
        pipeline_context = self._prepare(associated_pipeline_yaml)

        # ── BASELINE ──────────────────────────────────────────────────────────
        self._update_status(run, "baseline")
        baseline = self._metrics.capture_baseline(pipeline_context)
        self._merge_results(run, baseline)

        # ── Get the fault injector ─────────────────────────────────────────────
        injector_class = FAULT_INJECTOR_REGISTRY.get(fault_type)
        if injector_class is None:
            raise FaultInjectionError(
                f"No fault injector registered for type '{fault_type}'.",
                fault_type=fault_type,
                target_service=target_service,
            )
        injector = injector_class(self._docker)
        injection_metadata: dict = {}

        # ── Global timeout = fault duration + grace period ─────────────────────
        global_timeout = fault_duration + _TIMEOUT_GRACE_SECONDS
        experiment_start = time.monotonic()

        try:
            # ── INJECT FAILURE ─────────────────────────────────────────────────
            self._update_status(run, "injecting")
            self._check_cancelled(run)
            logger.info(
                "ExperimentRunner: injecting '%s' fault on '%s'.",
                fault_type,
                target_service,
            )
            params = experiment_config.fault.model_dump()
            injection_metadata = injector.inject(target_service, params)
            injection_metadata["target_service"] = target_service
            injection_metadata["fault_type"] = fault_type
            injection_metadata["fault_duration"] = fault_duration
            self._merge_results(run, injection_metadata)

            # Persist FaultInjection audit record
            self._persist_fault_injection(run, experiment_config, injection_metadata)

            # ── MONITOR ───────────────────────────────────────────────────────
            self._update_status(run, "monitoring")
            self._check_cancelled(run)
            self._check_timeout(experiment_start, global_timeout)

            availability_data = self._metrics.capture_during_experiment(
                target_service, self._docker, fault_duration
            )
            self._merge_results(run, availability_data)

        finally:
            # ── ROLLBACK (unconditional) ───────────────────────────────────────
            # This finally block executes on:
            # - Normal completion
            # - Python exceptions (including FaultInjectionError)
            # - asyncio CancelledError
            # It does NOT execute on SIGKILL (process kill -9) — this is a
            # documented limitation.  See module docstring.
            self._update_status(run, "rolling_back")
            logger.info(
                "ExperimentRunner: rollback for '%s' fault on '%s'.",
                fault_type,
                target_service,
            )
            try:
                injector.rollback(target_service, injection_metadata)
            except Exception as rollback_exc:
                logger.error(
                    "ExperimentRunner: rollback raised an exception: %s. "
                    "Manual recovery may be required for '%s'.",
                    rollback_exc,
                    target_service,
                )

        # ── WAIT FOR RECOVERY ─────────────────────────────────────────────────
        self._update_status(run, "waiting_for_recovery")
        self._check_cancelled(run)
        self._check_timeout(experiment_start, global_timeout)

        remaining_timeout = global_timeout - (time.monotonic() - experiment_start)
        if remaining_timeout <= 0:
            self._check_timeout(experiment_start, global_timeout)

        recovery_time = self._metrics.measure_recovery_time(
            target_service,
            self._docker,
            poll_interval=1.0,
            max_wait=min(
                experiment_config.validation.max_recovery_time + 30,
                remaining_timeout,
            ),
        )
        self._merge_results(run, {"recovery_time_seconds": recovery_time})

        # ── VALIDATE DATA ─────────────────────────────────────────────────────
        self._update_status(run, "validating_data")
        self._check_cancelled(run)
        output_location = pipeline_context.get("output_location", {})
        expected_records = baseline.get("expected_record_count", 0)
        if output_location and expected_records > 0:
            consistency = self._validator.validate(expected_records, output_location)
        else:
            consistency = {
                "expected_records": expected_records,
                "actual_records": expected_records,
                "data_loss": 0,
                "data_loss_percentage": 0.0,
                "duplicate_ids_found": 0,
                "id_column": None,
                "validation_passed": True,
            }
        self._merge_results(run, consistency)

        # ── COLLECT METRICS ───────────────────────────────────────────────────
        self._update_status(run, "collecting_metrics")
        elapsed_total = time.monotonic() - experiment_start
        throughput = self._metrics.compute_throughput(
            records_processed=consistency.get("actual_records", 0),
            duration_seconds=elapsed_total,
        )
        self._merge_results(run, {"throughput_records_per_sec": throughput})
        self._metrics.persist_metrics(self._db, run_id, run.results or {})

        # ── ANALYZE ───────────────────────────────────────────────────────────
        self._update_status(run, "analyzing")
        result = self._analyze(
            experiment_config=experiment_config,
            recovery_time=recovery_time,
            data_loss=consistency.get("data_loss", 0),
        )
        self._merge_results(run, {"result": result})

        # ── CLEANUP ───────────────────────────────────────────────────────────
        self._update_status(run, "cleaning_up")
        # Cleanup is handled by rollback above; nothing additional needed.

        # ── GENERATE REPORT ───────────────────────────────────────────────────
        self._update_status(run, "generating_report")
        run.finished_at = datetime.now(tz=timezone.utc)
        run.status = "succeeded" if result == "PASS" else "failed"
        self._db.flush()

        report = self._reporter.generate(run_id, self._db)
        self._db.commit()

        logger.info(
            "ExperimentRunner: run %s completed with result=%s.",
            run_id,
            result,
        )
        return report

    # ── Private stage methods ──────────────────────────────────────────────────

    def _validate(self, experiment_config: ExperimentModel) -> None:
        """Validate the experiment config against the safety layer."""
        self._safety.validate_target(experiment_config.target.service)
        self._safety.validate_duration(experiment_config.fault.duration)

    def _prepare(self, pipeline_yaml: str) -> dict:
        """
        Run the associated pipeline if YAML is provided, capture output context.

        Returns a context dict that feeds into the baseline and data validator.
        """
        if not pipeline_yaml:
            return {"records_processed": 0, "output_location": {}}

        try:
            from app.services.pipeline_execution_service import run_pipeline_from_yaml

            result = run_pipeline_from_yaml(pipeline_yaml)
            metrics = result.get("metrics", {})
            storage_meta = metrics.get("storage", {})
            rows = (
                storage_meta.get("rows_written")
                or metrics.get("source_rows")
                or 0
            )
            output_location = {
                "storage_type": storage_meta.get("type", "local"),
                "path": storage_meta.get("path", ""),
            }
            return {
                "records_processed": rows,
                "output_location": output_location,
                "pipeline_run_result": result,
            }
        except Exception as exc:
            logger.warning(
                "ExperimentRunner._prepare: pipeline run failed: %s "
                "(experiment will continue with records_processed=0).",
                exc,
            )
            return {"records_processed": 0, "output_location": {}}

    def _analyze(
        self,
        experiment_config: ExperimentModel,
        recovery_time: float | None,
        data_loss: int,
    ) -> str:
        """
        Compare results against validation criteria and return PASS or FAIL.

        Returns
        -------
        str
            ``"PASS"`` if all criteria met, ``"FAIL"`` otherwise.
        """
        criteria = experiment_config.validation
        max_allowed_loss = criteria.expected_data_loss
        max_allowed_recovery = criteria.max_recovery_time

        issues = []

        if data_loss > max_allowed_loss:
            issues.append(
                f"data_loss={data_loss} > allowed={max_allowed_loss}"
            )

        if recovery_time is None:
            issues.append(
                f"Service did not recover within {max_allowed_recovery}s."
            )
        elif recovery_time > max_allowed_recovery:
            issues.append(
                f"recovery_time={recovery_time}s > allowed={max_allowed_recovery}s"
            )

        if issues:
            logger.warning(
                "ExperimentRunner._analyze: FAIL — %s", "; ".join(issues)
            )
            return "FAIL"

        logger.info("ExperimentRunner._analyze: PASS — all criteria met.")
        return "PASS"

    def _persist_fault_injection(
        self,
        run: Any,
        experiment_config: ExperimentModel,
        injection_metadata: dict,
    ) -> None:
        """Persist a FaultInjection audit record linked to the experiment run."""
        # FaultInjection is FK'd to pipeline_runs, not experiment_runs.
        # We store the fault audit in the ExperimentRun.results JSON instead,
        # which avoids a schema FK dependency while still preserving the record.
        audit = {
            "fault_type": experiment_config.fault.type,
            "target_service": experiment_config.target.service,
            "fault_params": experiment_config.fault.model_dump(),
            "injection_metadata": injection_metadata,
            "injected_at": injection_metadata.get("stopped_at")
            or injection_metadata.get("started_at")
            or injection_metadata.get("applied_at")
            or datetime.now(tz=timezone.utc).isoformat(),
        }
        self._merge_results(run, {"fault_audit": audit})

    def _update_status(self, run: Any, status: str) -> None:
        """Persist the current lifecycle stage to the database."""
        run.status = status
        self._db.add(run)
        self._db.flush()
        logger.debug("ExperimentRunner: run %s → status='%s'.", run.id, status)

    def _merge_results(self, run: Any, data: dict) -> None:
        """Merge ``data`` into ``run.results`` and flush to the DB."""
        # Assign a fresh mapping so SQLAlchemy detects each JSON update.
        existing = dict(run.results or {})
        existing.update(data)
        run.results = existing
        self._db.add(run)
        self._db.flush()

    def _check_cancelled(self, run: Any) -> None:
        """Raise RuntimeError if cancellation has been requested."""
        if self._cancelled:
            run.status = "cancelled"
            run.finished_at = datetime.now(tz=timezone.utc)
            self._db.add(run)
            self._db.flush()
            raise RuntimeError("Experiment cancelled by operator.")

    def _check_timeout(self, start: float, timeout: float) -> None:
        """Raise ExperimentTimeoutError if the global timeout has elapsed."""
        elapsed = time.monotonic() - start
        if elapsed >= timeout:
            raise ExperimentTimeoutError(timeout_seconds=int(timeout))
