"""
app/pipeline/executor.py
--------------------------
Executes an :class:`~app.pipeline.generator.ExecutionPlan` step-by-step,
collecting per-stage metrics and structured logs into a
:class:`~app.pipeline.context.PipelineExecutionContext`.

Error handling contract
------------------------
The executor catches *every* exception raised by any plugin and wraps it in
:class:`PipelineExecutionError`.  This guarantees:

* The HTTP layer never receives an unhandled exception from a plugin.
* The partial :class:`~app.pipeline.context.PipelineExecutionContext` (showing
  how far execution reached and what metrics were collected) is always
  accessible via ``PipelineExecutionError.context``.
* Stack traces are preserved in the ``__cause__`` chain for debugging.

Execution order
---------------
1. Source step  → ``plugin.read(config)`` → DataFrame
2. [Optional] Kafka publish — if ``plan.messaging_config`` is set
3. [Branch A — Spark] if ``plan.processing_engine_type == "spark"``:
     a. Write DataFrame to a temp CSV
     b. Submit ``batch_processing_job.py`` via ``SparkJobSubmitter``
     c. Record ``spark_job`` metrics; storage step reads from Parquet output
4. [Branch B — Pandas] otherwise:
     Processor steps (in plan order) → ``plugin.process(df, config)`` → DataFrame
     then Storage step → ``plugin.write(df, config)`` → metadata dict

Each step's row count and wall-clock duration are recorded in
``context.metrics[step_name]``.
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import time
from typing import Any

import pandas as pd

from app.pipeline.context import PipelineExecutionContext
from app.pipeline.generator import ExecutionPlan, ExecutionStep
from app.spark.spark_job_submitter import SparkJobSubmitter

logger = logging.getLogger(__name__)


# ── Executor exception ─────────────────────────────────────────────────────────


class PipelineExecutionError(Exception):
    """
    Raised when any plugin step fails during pipeline execution.

    Wraps the original exception and carries the partial execution context so
    callers can inspect how far the pipeline progressed before failing.

    Attributes
    ----------
    step_name : str
        Name of the step that failed (e.g. ``"processor:filter:2"``).
    context : PipelineExecutionContext
        The partial context accumulated up to the point of failure.  Metrics
        and logs for all *successfully completed* steps are present.
    cause : Exception
        The original exception raised by the failing plugin.
    """

    def __init__(
        self,
        message: str,
        step_name: str,
        context: PipelineExecutionContext,
        cause: Exception,
    ) -> None:
        super().__init__(message)
        self.step_name = step_name
        self.context = context
        self.cause = cause


# ── Executor ───────────────────────────────────────────────────────────────────


class PipelineExecutor:
    """
    Executes a :class:`~app.pipeline.generator.ExecutionPlan` produced by
    :class:`~app.pipeline.generator.PipelineGenerator`.

    Each call to :meth:`execute` is independent — a new
    :class:`~app.pipeline.context.PipelineExecutionContext` is created for
    every run.

    Usage::

        plan = PipelineGenerator().generate(config)
        context = PipelineExecutor().execute(plan)
        print(context.status)   # "success"
        print(context.metrics)  # {step: {rows_out, duration_ms}, ...}
    """

    def execute(self, plan: ExecutionPlan) -> PipelineExecutionContext:
        """
        Run all steps in *plan* in order and return the execution context.

        Parameters
        ----------
        plan : ExecutionPlan
            Resolved execution plan from :class:`~app.pipeline.generator.PipelineGenerator`.

        Returns
        -------
        PipelineExecutionContext
            Context with ``status="success"`` and metrics/logs for every step.

        Raises
        ------
        PipelineExecutionError
            Any step raises an exception.  The partial context is embedded in
            the error object.
        """
        ctx = PipelineExecutionContext()
        ctx.log_info(
            "executor",
            f"Starting pipeline '{plan.pipeline_name}' v{plan.pipeline_version} "
            f"— run_id={ctx.run_id} engine={plan.processing_engine_type or 'pandas'}",
        )

        df: pd.DataFrame | None = None

        # ── Source step ────────────────────────────────────────────────────────
        source_step = next(s for s in plan.steps if s.step_type == "source")
        df = self._run_source(source_step, ctx)

        # ── Optional Kafka publish ─────────────────────────────────────────────
        if plan.messaging_config:
            self._publish_to_kafka(plan.messaging_config, df, ctx)

        # ── Processing branch ──────────────────────────────────────────────────
        if plan.processing_engine_type == "spark":
            # Spark path: submit the whole processing block as a Spark job.
            # The storage step afterward is skipped — Spark writes Parquet directly.
            self._run_spark_job(plan, df, ctx)
        else:
            # Pandas path (Phase 3): run processors in-process, then storage.
            for step in plan.steps:
                if step.step_type == "processor":
                    df = self._run_processor(step, df, ctx)
                elif step.step_type == "storage":
                    self._run_storage(step, df, ctx)
                # source already handled above

        ctx.status = "success"
        from app.metrics import pipeline_records_processed_total
        pipeline_records_processed_total.labels(plan.pipeline_name).inc(len(df))
        ctx.log_info("executor", f"Pipeline '{plan.pipeline_name}' completed successfully.")
        logger.info("Pipeline '%s' run %s completed.", plan.pipeline_name, ctx.run_id)
        return ctx

    # ── Step runners ───────────────────────────────────────────────────────────

    def _run_source(
        self,
        step: ExecutionStep,
        ctx: PipelineExecutionContext,
    ) -> pd.DataFrame:
        """Execute the source step and record metrics."""
        ctx.log_info(step.name, f"Reading data via '{step.plugin_type}' source.")
        t0 = time.perf_counter()

        try:
            df = step.plugin.read(step.config)
        except Exception as exc:
            self._handle_failure(step, ctx, exc)

        duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        rows = len(df)
        ctx.record_stage(step.name, {"rows_out": rows, "duration_ms": duration_ms})
        from app.metrics import pipeline_processing_latency_seconds
        pipeline_processing_latency_seconds.labels(step.name).observe(duration_ms / 1000)
        ctx.log_info(step.name, f"Read {rows} row(s) in {duration_ms}ms.")
        return df

    def _run_processor(
        self,
        step: ExecutionStep,
        df: pd.DataFrame,
        ctx: PipelineExecutionContext,
    ) -> pd.DataFrame:
        """Execute a processor step, feeding in *df* and recording metrics."""
        rows_in = len(df)
        ctx.log_info(
            step.name, f"Applying '{step.plugin_type}' processor ({rows_in} rows in)."
        )
        t0 = time.perf_counter()

        try:
            df_out = step.plugin.process(df, step.config)
        except Exception as exc:
            self._handle_failure(step, ctx, exc)

        duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        rows_out = len(df_out)
        ctx.record_stage(
            step.name,
            {"rows_in": rows_in, "rows_out": rows_out, "duration_ms": duration_ms},
        )
        from app.metrics import pipeline_processing_latency_seconds
        pipeline_processing_latency_seconds.labels(step.name).observe(duration_ms / 1000)
        ctx.log_info(
            step.name,
            f"Processor '{step.plugin_type}' complete: {rows_in} → {rows_out} rows "
            f"in {duration_ms}ms.",
        )
        return df_out

    def _run_storage(
        self,
        step: ExecutionStep,
        df: pd.DataFrame,
        ctx: PipelineExecutionContext,
    ) -> None:
        """Execute the storage step and record write metadata."""
        ctx.log_info(
            step.name, f"Writing {len(df)} row(s) via '{step.plugin_type}' storage."
        )
        t0 = time.perf_counter()

        try:
            write_meta: dict = step.plugin.write(df, step.config)
        except Exception as exc:
            self._handle_failure(step, ctx, exc)

        duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        meta_with_timing = {**write_meta, "duration_ms": duration_ms}
        ctx.record_stage(step.name, meta_with_timing)
        from app.metrics import pipeline_processing_latency_seconds
        pipeline_processing_latency_seconds.labels(step.name).observe(duration_ms / 1000)
        ctx.log_info(
            step.name,
            f"Wrote {write_meta.get('rows_written', '?')} row(s) to "
            f"'{write_meta.get('path', '?')}' in {duration_ms}ms.",
        )

    # ── Kafka publish ──────────────────────────────────────────────────────────

    def _publish_to_kafka(
        self,
        messaging_config: dict,
        df: pd.DataFrame,
        ctx: PipelineExecutionContext,
    ) -> None:
        """
        Publish raw source records to Kafka if messaging configuration is present.

        Parameters
        ----------
        messaging_config : dict
            Messaging section from PipelineConfig.
        df : pandas.DataFrame
            Raw source DataFrame to publish.
        ctx : PipelineExecutionContext
            Execution context to record metrics and logs.
        """
        topic = messaging_config.get("topic")
        if not topic:
            return

        partitions = messaging_config.get("partitions", 1)
        replication_factor = messaging_config.get("replication_factor", 1)

        ctx.log_info(
            "kafka_publish", f"Publishing raw source records to Kafka topic '{topic}'."
        )
        t0 = time.perf_counter()

        try:
            import json

            from app.messaging.kafka_admin import KafkaAdminClient
            from app.messaging.kafka_producer import KafkaProducerClient

            admin = KafkaAdminClient()
            admin.create_topic(
                topic,
                partitions=partitions,
                replication_factor=replication_factor,
            )

            producer = KafkaProducerClient()
            records = json.loads(df.to_json(orient="records", date_format="iso"))
            result = producer.produce_batch(topic, records)

            duration_ms = round((time.perf_counter() - t0) * 1000, 2)
            meta_with_timing = {**result, "duration_ms": duration_ms}
            ctx.record_stage("kafka_publish", meta_with_timing)
            ctx.log_info(
                "kafka_publish",
                f"Published {result.get('produced', 0)} record(s) to topic "
                f"'{topic}' in {duration_ms}ms.",
            )
        except Exception as exc:
            publish_step = ExecutionStep(
                name="kafka_publish",
                step_type="messaging",
                plugin_type="kafka",
                plugin=None,
                config=messaging_config,
            )
            self._handle_failure(publish_step, ctx, exc)

    # ── Spark branch ───────────────────────────────────────────────────────────

    def _run_spark_job(
        self,
        plan: ExecutionPlan,
        df: pd.DataFrame,
        ctx: PipelineExecutionContext,
    ) -> None:
        """
        Submit a Spark batch job for the pipeline's processing + storage steps.

        Workflow
        --------
        1. Write the post-source DataFrame to a temporary CSV (accessible by
           the Spark cluster via the shared ``spark-jobs`` volume mount).
        2. Collect the processing operations from the plan's processor steps
           back into a config dict for ``batch_processing_job.py``.
        3. Use the storage step's configured ``path`` as the Parquet output
           destination (skipping the pandas storage plugin entirely).
        4. Call ``SparkJobSubmitter.submit_batch_job()`` and record the returned
           metrics under ``"spark_job"`` in the execution context.

        Parameters
        ----------
        plan : ExecutionPlan
            The full execution plan (used to extract operations and output path).
        df : pandas.DataFrame
            Post-source, post-Kafka DataFrame to process.
        ctx : PipelineExecutionContext
            Execution context for logging and metrics.

        Raises
        ------
        PipelineExecutionError
            If the Spark job fails or times out.
        """
        from app.spark.exceptions import SparkJobFailedError, SparkJobTimeoutError

        ctx.log_info("spark_job", "Submitting batch Spark job for processing steps.")
        t0 = time.perf_counter()

        # ── Build temp input file ──────────────────────────────────────────────
        # Prefer the original mounted CSV/JSON source. It is available to
        # backend, Spark master, and worker containers via docker-compose.
        # A temporary file is only used for non-file sources such as API/Kafka.
        tmp_file = None
        try:
            source_step = next(s for s in plan.steps if s.step_type == "source")
            input_source = source_step.config.get("path")
            if not input_source:
                with tempfile.NamedTemporaryFile(
                    suffix=".csv", delete=False, mode="w", encoding="utf-8"
                ) as f:
                    df.to_csv(f, index=False)
                    tmp_file = f.name
                    input_source = tmp_file

            # ── Collect operations from plan ───────────────────────────────────
            operations = []
            for step in plan.steps:
                if step.step_type == "processor":
                    operations.append(step.config)

            # ── Determine output path from storage step ────────────────────────
            storage_step = next(
                (s for s in plan.steps if s.step_type == "storage"), None
            )
            output_path = (
                storage_step.config.get("path", "/tmp/spark-output")
                if storage_step
                else "/tmp/spark-output"
            )
            if storage_step and storage_step.plugin_type == "hdfs" and output_path.startswith("/"):
                output_path = f"hdfs://namenode:9000{output_path}"

            processing_config = {"processing": {"operations": operations}}

            # ── Submit job (async bridge) ──────────────────────────────────────
            # executor.execute() is called synchronously from the FastAPI service
            # layer, but SparkJobSubmitter.submit_batch_job() is async.  We run
            # it in a new event loop on the current thread to avoid blocking the
            # uvicorn event loop.
            submitter = SparkJobSubmitter()

            async def _submit() -> dict[str, Any]:
                return await submitter.submit_batch_job(
                    input_source=input_source,
                    output_path=output_path,
                    processing_config=processing_config,
                )

            result = asyncio.run(_submit())

            duration_ms = round((time.perf_counter() - t0) * 1000, 2)
            ctx.record_stage(
                "spark_job",
                {
                    "input_rows": result.get("input_rows"),
                    "output_rows": result.get("output_rows"),
                    "duration_seconds": result.get("duration_seconds"),
                    "output_path": output_path,
                    "duration_ms": duration_ms,
                },
            )
            ctx.log_info(
                "spark_job",
                f"Spark job completed: {result.get('input_rows')} → "
                f"{result.get('output_rows')} rows in {result.get('duration_seconds')}s. "
                f"Output: {output_path}",
            )

        except (SparkJobFailedError, SparkJobTimeoutError) as exc:
            spark_step = ExecutionStep(
                name="spark_job",
                step_type="spark",
                plugin_type="spark",
                plugin=None,
                config={},
            )
            # Surface stderr in logs for debugging
            if hasattr(exc, "stderr") and exc.stderr:
                logger.error(
                    "Spark job stderr:\n%s", "\n".join(exc.stderr.splitlines()[-30:])
                )
            self._handle_failure(spark_step, ctx, exc)
        except Exception as exc:
            spark_step = ExecutionStep(
                name="spark_job",
                step_type="spark",
                plugin_type="spark",
                plugin=None,
                config={},
            )
            self._handle_failure(spark_step, ctx, exc)
        finally:
            if tmp_file and os.path.exists(tmp_file):
                os.unlink(tmp_file)

    # ── Error handling ─────────────────────────────────────────────────────────

    def _handle_failure(
        self,
        step: ExecutionStep,
        ctx: PipelineExecutionContext,
        exc: Exception,
    ) -> None:
        """
        Record the failure in the context and raise :class:`PipelineExecutionError`.

        This method **always raises** — the ``-> None`` return type is a
        typing convenience so callers don't need ``raise self._handle_failure()``.
        """
        msg = f"Step '{step.name}' failed: {type(exc).__name__}: {exc}"
        ctx.log_error(step.name, msg)
        ctx.status = "failed"
        from app.metrics import pipeline_errors_total
        pipeline_errors_total.labels(step.name).inc()
        logger.error("Pipeline step '%s' failed: %s", step.name, exc, exc_info=True)
        raise PipelineExecutionError(
            message=msg,
            step_name=step.name,
            context=ctx,
            cause=exc,
        ) from exc
