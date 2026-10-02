"""
app/api/routes/messaging.py
----------------------------
Kafka messaging API routes.

Endpoints:
  GET  /api/messaging/health                     — Probe Kafka cluster health
  POST /api/messaging/topics                     — Create a new topic
  GET  /api/messaging/topics/{topic_name}/exists — Check if topic exists
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.messaging.exceptions import KafkaMessagingError
from app.messaging.kafka_admin import KafkaAdminClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/messaging", tags=["messaging"])


class CreateTopicRequest(BaseModel):
    """Payload model for creating a Kafka topic."""

    topic: str = Field(..., description="Name of the topic to create.")
    partitions: Optional[int] = Field(
        None, ge=1, description="Number of partitions. Defaults to system setting."
    )
    replication_factor: Optional[int] = Field(
        None, ge=1, description="Replication factor. Defaults to system setting."
    )


@router.get(
    "/health",
    summary="Kafka cluster health probe",
    response_description="Status of Kafka broker connectivity, broker count, and topic count.",
)
async def messaging_health() -> dict:
    """
    Check Kafka broker connectivity and topic metadata.

    Never fails with HTTP 500 — returns ``connected: false`` with error details
    if broker is unreachable.
    """
    admin = KafkaAdminClient()
    return admin.health_check()


@router.post(
    "/topics",
    summary="Create a Kafka topic",
    response_description="Topic creation result.",
)
async def create_topic(request: CreateTopicRequest) -> dict:
    """
    Create a new Kafka topic on the cluster if it does not already exist.
    """
    try:
        admin = KafkaAdminClient()
        return admin.create_topic(
            topic_name=request.topic,
            partitions=request.partitions,
            replication_factor=request.replication_factor,
        )
    except KafkaMessagingError as exc:
        logger.error("Failed to create topic '%s': %s", request.topic, exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Unexpected error creating topic '%s': %s", request.topic, exc)
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}") from exc


@router.get(
    "/topics/{topic_name}/exists",
    summary="Check if a Kafka topic exists",
    response_description="Returns whether the specified topic exists.",
)
async def topic_exists(topic_name: str) -> dict:
    """
    Check if a topic exists on the Kafka cluster.
    """
    try:
        admin = KafkaAdminClient()
        exists = admin.topic_exists(topic_name)
        return {"topic": topic_name, "exists": exists}
    except KafkaMessagingError as exc:
        logger.warning("Error checking if topic '%s' exists: %s", topic_name, exc)
        return {"topic": topic_name, "exists": False, "error": str(exc)}
