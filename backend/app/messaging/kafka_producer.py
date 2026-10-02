"""
app/messaging/kafka_producer.py
-------------------------------
Producer wrapper for publishing JSON records to Kafka topics.

Wraps confluent_kafka.Producer to handle JSON serialization, delivery callbacks,
batch publishing, and error management.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from confluent_kafka import KafkaError, KafkaException, Producer

from app.core.config import Settings, get_settings
from app.messaging.exceptions import KafkaProduceError
from app.messaging.kafka_config import get_producer_config

logger = logging.getLogger(__name__)


class KafkaProducerClient:
    """
    Wrapper around confluent_kafka.Producer.

    Provides synchronous or asynchronously-polled message publishing with
    delivery reports and batch helpers.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        producer: Producer | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        if producer is not None:
            self._producer = producer
        else:
            config = get_producer_config(self.settings)
            self._producer = Producer(config)

    def produce(
        self,
        topic: str,
        value: dict[str, Any],
        key: str | None = None,
    ) -> None:
        """
        Produce a single JSON record to a Kafka topic.

        Parameters
        ----------
        topic : str
            Target topic name.
        value : dict[str, Any]
            Record payload dict to serialize as JSON.
        key : str | None
            Optional record key for partition routing.

        Raises
        ------
        KafkaProduceError
            If message queueing fails (e.g. BufferError).
        """
        try:
            payload = json.dumps(value).encode("utf-8")
            key_bytes = key.encode("utf-8") if key is not None else None
        except Exception as exc:
            raise KafkaProduceError(
                f"Failed to serialize record to JSON for topic '{topic}': {exc}", cause=exc
            ) from exc

        def _delivery_report(err: KafkaError | None, msg: Any) -> None:
            if err is not None:
                logger.error(
                    "Kafka message delivery failed",
                    extra={
                        "topic": topic,
                        "error": str(err),
                        "err_code": err.code() if hasattr(err, "code") else None,
                    },
                )
            else:
                logger.debug(
                    "Kafka message delivered successfully",
                    extra={
                        "topic": msg.topic(),
                        "partition": msg.partition(),
                        "offset": msg.offset(),
                    },
                )

        try:
            self._producer.produce(
                topic=topic,
                value=payload,
                key=key_bytes,
                on_delivery=_delivery_report,
            )
            # Poll events to serve delivery callbacks
            self._producer.poll(0)
        except BufferError as exc:
            raise KafkaProduceError(
                f"Producer local queue buffer full while producing to topic '{topic}': {exc}",
                cause=exc,
            ) from exc
        except KafkaException as exc:
            raise KafkaProduceError(
                f"Kafka producer exception for topic '{topic}': {exc}", cause=exc
            ) from exc
        except Exception as exc:
            raise KafkaProduceError(
                f"Unexpected error producing to topic '{topic}': {exc}", cause=exc
            ) from exc

    def produce_batch(
        self,
        topic: str,
        records: list[dict[str, Any]],
        key_field: str | None = None,
        timeout: float = 10.0,
    ) -> dict[str, int]:
        """
        Produce a batch of JSON records to a topic and flush.

        Parameters
        ----------
        topic : str
            Target topic name.
        records : list[dict[str, Any]]
            List of dictionary payloads.
        key_field : str | None
            Optional field name in dicts to use as the record key.
        timeout : float
            Flush timeout in seconds.

        Returns
        -------
        dict[str, int]
            ``{"produced": int, "failed": int}``
        """
        produced = 0
        failed = 0

        for rec in records:
            key = str(rec[key_field]) if (key_field and key_field in rec) else None
            try:
                self.produce(topic, rec, key=key)
                produced += 1
            except KafkaProduceError as exc:
                logger.error("Failed to queue record in batch: %s", exc)
                failed += 1

        self.flush(timeout=timeout)
        return {"produced": produced, "failed": failed}

    def flush(self, timeout: float = 10.0) -> int:
        """
        Flush outstanding producer messages and wait for delivery callbacks.

        Parameters
        ----------
        timeout : float
            Maximum time in seconds to wait for flush to complete.

        Returns
        -------
        int
            Number of messages still remaining in queue after timeout.
        """
        return self._producer.flush(timeout)

    def close(self) -> None:
        """Flush pending messages before closing the producer."""
        self.flush(timeout=10.0)
