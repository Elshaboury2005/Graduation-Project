"""
app/api/routes/pipeline_runs.py
-------------------------------
API routes for viewing pipeline execution history.
"""

import uuid
from typing import List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database.session import get_db
from app.models.pipeline_run import PipelineRun

router = APIRouter(tags=["pipeline_runs"])

@router.get("/api/pipeline-runs")
async def list_pipeline_runs(db: AsyncSession = Depends(get_db)) -> List[Dict[str, Any]]:
    """Return the last 50 pipeline runs ordered by created_at descending."""
    stmt = (
        select(PipelineRun)
        .options(
            selectinload(PipelineRun.pipeline),
            selectinload(PipelineRun.pipeline_version),
            selectinload(PipelineRun.metrics),
        )
        .order_by(PipelineRun.created_at.desc())
        .limit(50)
    )
    result = await db.execute(stmt)
    runs = result.scalars().all()
    
    return [
        {
            "id": str(r.id),
            "name": r.pipeline.name if r.pipeline else "Unknown",
            "status": r.status,
            "recordsProcessed": next(
                (metric.value for metric in r.metrics if metric.name == "records_processed"), 0
            ),
            "startedAt": r.started_at.isoformat() if r.started_at else None,
            "completedAt": r.finished_at.isoformat() if r.finished_at else None,
        }
        for r in runs
    ]

@router.get("/api/pipeline-runs/{run_id}")
async def get_pipeline_run(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Return detailed information for a specific pipeline run."""
    stmt = (
        select(PipelineRun)
        .options(
            selectinload(PipelineRun.pipeline),
            selectinload(PipelineRun.pipeline_version),
            selectinload(PipelineRun.metrics),
        )
        .where(PipelineRun.id == run_id)
    )
    result = await db.execute(stmt)
    run = result.scalar_one_or_none()
    
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found.")
        
    return {
        "id": str(run.id),
        "name": run.pipeline.name if run.pipeline else "Unknown",
        "status": run.status,
        "recordsProcessed": next(
            (metric.value for metric in run.metrics if metric.name == "records_processed"), 0
        ),
        "startedAt": run.started_at.isoformat() if run.started_at else None,
        "completedAt": run.finished_at.isoformat() if run.finished_at else None,
        "error_message": run.error_message,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "metrics": {metric.name: metric.value for metric in run.metrics},
        "configuration": run.pipeline_version.config if run.pipeline_version else None,
    }
