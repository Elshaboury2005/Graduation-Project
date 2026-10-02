"""
app/api/routes/spark.py
------------------------
Spark-related API endpoints.

``GET /api/spark/health``
    Calls ``SparkJobSubmitter.health_check()`` to probe the Spark master REST
    API and return worker count / status.

No business logic lives here — route handlers only call service functions
and return responses.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from app.spark.spark_job_submitter import SparkJobSubmitter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/spark", tags=["spark"])


@router.get(
    "/health",
    summary="Spark cluster health probe",
    response_description="Spark master connectivity and worker count",
)
async def spark_health() -> dict:
    """
    Probe the Spark master REST API and return cluster status.

    Returns
    -------
    dict
        ``{"connected": bool, "worker_count": int, "status": str, "error": str | None}``
    """
    submitter = SparkJobSubmitter()
    return await submitter.health_check()
