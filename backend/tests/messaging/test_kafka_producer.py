"""
tests/messaging/test_kafka_producer.py
---------------------------------------
Integration tests for KafkaProducerClient against a live Kafka broker.

Marked `@pytest.mark.integration` so they are automatically skipped if Kafka
is not running.
"""

from __future__ import annotations

import uuid
import pytest

from app.messaging.kafka_admin import KafkaAdminClient
from app.messaging.kafka_producer import KafkaProducerClient


@pytest.mark.integration
class TestKafkaProducerIntegration:
    """Integration tests for producing records to Kafka."""

    @pytest.fixture()
    def admin_client(self) -> KafkaAdminClient:
        return KafkaAdminClient()

    @pytest.fixture()
    def test_topic(self, admin_client: KafkaAdminClient) -> str:
        topic_name = f"test-producer-topic-{uuid.uuid4().hex[:8]}"
        admin_client.create_topic(topic_name, partitions=1, replication_factor=1)
        yield topic_name
        admin_client.delete_topic(topic_name)

    def test_produce_batch_publishes_20_records(self, test_topic: str) -> None:
        producer = KafkaProducerClient()

        # Generate 20 test records
        records = [
            {
                "id": i,
                "transaction_id": f"TXN_{i:03d}",
                "amount": float(i * 10.5),
                "customer": f"CUST_{i % 5}",
            }
            for i in range(20)
        ]

        result = producer.produce_batch(
            topic=test_topic,
            records=records,
            key_field="transaction_id",
            timeout=10.0,
        )

        assert result["produced"] == 20
        assert result["failed"] == 0
