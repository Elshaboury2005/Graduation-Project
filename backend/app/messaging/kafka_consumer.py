"""
app/messaging/kafka_consumer.py
-------------------------------
Consumer wrapper for polling and consuming JSON records from Kafka topics.

Wraps confluent_kafka.Consumer to handle topic subscription, manual offset
commits, JSON deserialization, and error handling.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from confluent_kafka import Consumer, KafkaError, KafkaException

from app.core.config import Settings, get_settings
from app.messaging.exceptions import KafkaConsumeError
from app.messaging.kafka_config import get_consumer_config

logger = logging.getLogger(__name__)


class KafkaConsumerClient:
    """
    Wrapper around confluent_kafka.Consumer.

    Subscribes to a topic on initialization and pulls batches of JSON messages
    with manual offset commit for reliable, at-least-once processing.
    """

    def __init__(
        self,
        topic: str,
        group_id: str,
        settings: Settings | None = None,
        consumer: Consumer | None = None,
    ) -> None:
        self.topic = topic
        self.group_id = group_id
        self.settings = settings or get_settings()

        if consumer is not None:
            self._consumer = consumer
        else:
            config = get_consumer_config(group_id, self.settings)
            self._consumer = Consumer(config)

        try:
            self._consumer.subscribe([self.topic])
            logger.info("Kafka consumer subscribed to topic '%s' (group_id='%s')", self.topic, self.group_id)
        except Exception as exc:
            raise KafkaConsumeError(
                f"Failed to subscribe consumer to topic '{self.topic}': {exc}", cause=exc
            ) from exc

    def consume_batch(
        self,
        max_messages: int = 100,
        timeout: float = 5.0,
    ) -> list[dict[str, Any]]:
        """
        Poll up to max_messages or until timeout expires, deserializing JSON.

        After successfully collecting the batch, manually commits offset
        before returning.

        Parameters
        ----------
        max_messages : int
            Maximum number of messages to pull.
        timeout : float
            Total wall-clock timeout in seconds to wait for messages.

        Returns
        -------
        list[dict[str, Any]]
            Batch of deserialized JSON records.
        """
        records: list[dict[str, Any]] = []
        start_time = time.monotonic()

        while len(records) < max_messages:
            elapsed = time.monotonic() - start_time
            remaining_timeout = max(0.1, timeout - elapsed)
            if elapsed >= timeout:
                break

            try:
                msg = self._consumer.poll(timeout=min(1.0, remaining_timeout))
            except KafkaException as exc:
                raise KafkaConsumeError(
                    f"Error polling Kafka topic '{self.topic}': {exc}", cause=exc
                ) from exc
            except Exception as exc:
                raise KafkaConsumeError(
                    f"Unexpected error polling topic '{self.topic}': {exc}", cause=exc
                ) from exc

            if msg is None:
                continue

            if msg.error():
                err_code = msg.error().code()
                if err_code == KafkaError._PARTITION_EOF:
                    # End of partition event — normal during consumer catchup
                    continue
                else:
                    logger.error("Consumer received error for topic '%s': %s", self.topic, msg.error())
                    raise KafkaConsumeError(
                        f"Kafka error consuming from topic '{self.topic}': {msg.error()}",
                        cause=msg.error(),
                    )

            # Deserialize payload
            raw_value = msg.value()
            if raw_value is None:
                continue

            try:
                value = json.loads(raw_value.decode("utf-8"))
                if isinstance(value, dict):
                    records.append(value)
                elif isinstance(value, list):
                    # Handle case where individual message value is a JSON array
                    for item in value:
                        if isinstance(item, dict):
                            records.append(item)
            except Exception as exc:
                logger.warning(
                    "Skipping message on topic '%s' due to JSON deserialization failure: %s",
                    self.topic,
                    exc,
                )
                continue

        # Manually commit offset after batch collection if records were received
        if records:
            try:
                self._consumer.commit(asynchronous=False)
                logger.debug("Committed offset for batch of %d records on topic '%s'", len(records), self.topic)
            except Exception as exc:
                logger.warning("Failed to commit offset on topic '%s': %s", self.topic, exc)

        return records

    def close(self) -> None:
        """
        Commit final offsets and cleanly leave the consumer group.
        """
        try:
            self._consumer.close()
            logger.info("Kafka consumer closed for topic '%s'", self.topic)
        except Exception as exc:
            logger.warning("Error closing Kafka consumer: %s", exc)
