"""Metrics query endpoints for the platform dashboard."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.metric import Metric
from app.models.pipeline_run import PipelineRun

router = APIRouter(tags=["metrics"])


def _serialize(metric: Metric) -> dict[str, Any]:
    timestamp = metric.recorded_at or metric.created_at
    return {
        "id": str(metric.id),
        "pipeline_run_id": str(metric.pipeline_run_id),
        "name": metric.name,
        "value": metric.value,
        "unit": metric.unit,
        "step": metric.step,
        "recorded_at": timestamp.isoformat() if timestamp else None,
    }


@router.get("/api/metrics")
async def list_metrics(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    """Return the 500 newest metric points across pipeline runs."""
    result = await db.execute(select(Metric).order_by(Metric.created_at.desc()).limit(500))
    return [_serialize(metric) for metric in result.scalars().all()]


@router.get("/api/metrics/{pipeline_id}")
async def pipeline_metrics(
    pipeline_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    """Return the newest 500 metrics belonging to one pipeline."""
    statement = (
        select(Metric)
        .join(PipelineRun, Metric.pipeline_run_id == PipelineRun.id)
        .where(PipelineRun.pipeline_id == pipeline_id)
        .order_by(Metric.created_at.desc())
        .limit(500)
    )
    result = await db.execute(statement)
    return [_serialize(metric) for metric in result.scalars().all()]
