"""
app/api/routes/storage.py
--------------------------
HDFS storage health endpoint.

``GET /api/storage/health``
    Returns live HDFS NameNode connectivity status and cluster capacity
    statistics (total/used GB, live DataNode count) sourced from the
    NameNode's JMX endpoint.  Mirrors the pattern established by
    ``/api/messaging/health`` (Phase 4) and ``/api/spark/health`` (Phase 5).

No business logic lives here — the route delegates to
:class:`~app.storage.HdfsStorageClient`.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["storage"])


@router.get(
    "/api/storage/health",
    summary="HDFS NameNode connectivity and capacity check",
    response_description="HDFS health status with live capacity stats",
)
async def storage_health() -> dict:
    """
    Return HDFS NameNode reachability and live cluster capacity statistics.

    Calls :meth:`~app.storage.HdfsStorageClient.health_check` which:

    1. Verifies the NameNode's WebHDFS root path is accessible.
    2. Optionally fetches capacity/DataNode metrics from the JMX endpoint.

    The response shape mirrors :class:`~app.storage.hdfs_client.HdfsStorageClient`
    ``health_check()`` output::

        {
            "connected": true,
            "namenode_url": "http://namenode:9870",
            "error": null,
            "capacity_total_gb": 50.0,
            "capacity_used_gb": 0.001,
            "num_live_datanodes": 1
        }
    """
    try:
        from app.storage.hdfs_client import HdfsStorageClient

        client = HdfsStorageClient()
        return client.health_check()
    except Exception as exc:
        logger.warning("HDFS health check endpoint error: %s", exc)
        return {
            "connected": False,
            "namenode_url": None,
            "error": str(exc),
            "capacity_total_gb": None,
            "capacity_used_gb": None,
            "num_live_datanodes": None,
        }
