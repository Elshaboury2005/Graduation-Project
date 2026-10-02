"""
app/api/routes/pipelines.py
-----------------------------
Pipeline management API routes.

Phase 2: POST /api/pipelines/validate — config validation only.
Phase 3: POST /api/pipelines/run     — full pipeline execution.

Route responsibility is strictly limited to:
  - Declaring the HTTP method, path, and request/response models.
  - Calling into the service layer.
  - Returning the HTTP response.

No parsing, validation logic, business rules, or plugin calls live here.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import yaml
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.pipeline_config import (
    ValidatePipelineRequest,
    ValidatePipelineResponse,
)
from app.services.pipeline_config_service import validate_pipeline_config
from app.services.pipeline_execution_service import run_pipeline_from_yaml
from app.database.session import get_db
from app.models.metric import Metric
from app.models.pipeline import Pipeline
from app.models.pipeline_run import PipelineRun
from app.models.pipeline_version import PipelineVersion

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pipelines", tags=["pipelines"])


async def _record_pipeline_run(
    db: AsyncSession, yaml_content: str, result: dict[str, Any]
) -> str:
    """Persist an execution summary so it is visible in the dashboard history."""
    config = yaml.safe_load(yaml_content)
    pipeline_data = config.get("pipeline") if isinstance(config, dict) else None
    if not isinstance(pipeline_data, dict) or not pipeline_data.get("name"):
        # Validation failures have no stable pipeline identity and therefore
        # cannot be represented in the run-history tables.
        return ""
    name = pipeline_data["name"]

    pipeline = (
        await db.execute(select(Pipeline).where(Pipeline.name == name))
    ).scalar_one_or_none()
    if pipeline is None:
        pipeline = Pipeline(name=name)
        db.add(pipeline)
        await db.flush()

    version = (
        await db.execute(
            select(PipelineVersion)
            .where(PipelineVersion.pipeline_id == pipeline.id)
            .order_by(PipelineVersion.version_number.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if version is None or version.config != config:
        next_version = (
            await db.scalar(
                select(func.coalesce(func.max(PipelineVersion.version_number), 0) + 1)
                .where(PipelineVersion.pipeline_id == pipeline.id)
            )
        )
        version = PipelineVersion(
            pipeline_id=pipeline.id,
            version_number=int(next_version),
            config=config,
        )
        db.add(version)
        await db.flush()

    failed_log = next(
        (entry.get("message") for entry in reversed(result.get("logs", [])) if entry.get("level") == "ERROR"),
        None,
    )
    if failed_log:
        # The database column is VARCHAR(4096); preserve a useful error prefix
        # without turning a clean pipeline failure into an API 500 response.
        failed_log = failed_log[:4000]
    run = PipelineRun(
        pipeline_id=pipeline.id,
        pipeline_version_id=version.id,
        status="succeeded" if result.get("status") == "success" else "failed",
        started_at=datetime.now(tz=timezone.utc),
        finished_at=datetime.now(tz=timezone.utc),
        error_message=failed_log,
    )
    db.add(run)
    await db.flush()

    stages = result.get("metrics", {})
    spark_metrics = stages.get("spark_job", {})
    source_metrics = next((value for key, value in stages.items() if key.startswith("source:")), {})
    records_processed = spark_metrics.get("output_rows", source_metrics.get("rows_out"))
    if records_processed is not None:
        db.add(
            Metric(
                pipeline_run_id=run.id,
                name="records_processed",
                value=float(records_processed),
                unit="records",
            )
        )
    duration_ms = spark_metrics.get("duration_ms")
    if duration_ms is not None:
        db.add(
            Metric(
                pipeline_run_id=run.id,
                name="duration_ms",
                value=float(duration_ms),
                unit="ms",
            )
        )
    return str(run.id)


# ── POST /api/pipelines/validate ───────────────────────────────────────────────


@router.post(
    "/validate",
    response_model=ValidatePipelineResponse,
    summary="Validate a pipeline YAML configuration",
    response_description=(
        "Validation result — HTTP 200 always.  "
        "Inspect the 'valid' flag and 'errors' list for the outcome."
    ),
)
async def validate_pipeline(
    request: ValidatePipelineRequest,
) -> ValidatePipelineResponse:
    """
    Parse and validate a pipeline configuration YAML document.

    Accepts raw YAML text in the request body and runs it through two
    validation stages:

    1. **Structural validation** — Pydantic checks types, required fields,
       and discriminated-union operation types.
    2. **Business rules** — cross-section constraints such as "streaming
       pipelines must have a messaging config" or "aggregate columns must
       exist in the schema".

    The response is always HTTP 200.  Use the ``valid`` boolean and ``errors``
    list to determine the outcome — do not rely on 4xx codes.

    This endpoint has **no side effects**: it does not persist anything to
    the database.
    """
    logger.info("Received pipeline config validation request")

    result = validate_pipeline_config(request.yaml_content)

    return ValidatePipelineResponse(
        valid=result["valid"],
        errors=result["errors"],
    )


# ── POST /api/pipelines/run ────────────────────────────────────────────────────


@router.post(
    "/run",
    summary="Execute a pipeline from a YAML configuration",
    response_description=(
        "Execution result — HTTP 200 for success, validation failures, and "
        "clean execution failures.  HTTP 500 only for unexpected server errors "
        "that escape the service layer (should never occur in practice)."
    ),
)
async def run_pipeline(
    request: ValidatePipelineRequest,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Parse, validate, and fully execute a pipeline from a YAML configuration.

    Execution phases (in order):
    1. **YAML parse + schema validation** — same as ``/validate``.
    2. **Business rules** — same as ``/validate``.
    3. **Plan generation** — resolves all plugin types from the registry.
    4. **Execution** — source → processors → storage, collecting metrics and
       structured logs at each stage.

    Response shapes:

    - **Validation failure**: ``{"status": "invalid", "valid": false, "errors": [...], ...}``
    - **Execution failure**: ``{"status": "failed", "run_id": "...", "metrics": {...}, "logs": [...]}``
    - **Success**: ``{"status": "success", "run_id": "...", "metrics": {...}, "logs": [...]}``

    The response HTTP status code is always 200.  Inspect ``status`` to
    determine the outcome.
    """
    logger.info("Received pipeline run request")

    # The execution engine owns a Spark subprocess and must run outside the
    # request event loop. This also keeps the API responsive while Spark works.
    result: dict[str, Any] = await asyncio.to_thread(run_pipeline_from_yaml, request.yaml_content)
    if result.get("status") != "invalid":
        result["pipeline_run_id"] = await _record_pipeline_run(db, request.yaml_content, result)

    logger.info(
        "Pipeline run completed with status='%s'",
        result.get("status", "unknown"),
    )

    return JSONResponse(content=result, status_code=200)
