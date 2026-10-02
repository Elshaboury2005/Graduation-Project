"""
tests/messaging/test_kafka_consumer.py
---------------------------------------
Integration tests for KafkaConsumerClient and KafkaSource plugin against a live
Kafka broker.

Marked `@pytest.mark.integration` so they are automatically skipped if Kafka
is not running.
"""

from __future__ import annotations

import uuid
import pandas as pd
import pytest

from app.messaging.kafka_admin import KafkaAdminClient
from app.messaging.kafka_consumer import KafkaConsumerClient
from app.messaging.kafka_producer import KafkaProducerClient
from app.plugins.sources.kafka_source import KafkaSource


@pytest.mark.integration
class TestKafkaConsumerIntegration:
    """Integration tests for Kafka consumer functionality and manual offset commit."""

    @pytest.fixture()
    def admin_client(self) -> KafkaAdminClient:
        return KafkaAdminClient()

    @pytest.fixture()
    def test_topic(self, admin_client: KafkaAdminClient) -> str:
        topic_name = f"test-consumer-topic-{uuid.uuid4().hex[:8]}"
        admin_client.create_topic(topic_name, partitions=1, replication_factor=1)
        yield topic_name
        admin_client.delete_topic(topic_name)

    def test_produce_and_consume_batch_with_offset_commit(
        self, test_topic: str
    ) -> None:
        group_id = f"test-group-{uuid.uuid4().hex[:6]}"
        producer = KafkaProducerClient()

        known_records = [
            {"sensor_id": "S1", "temp": 22.4, "status": "OK"},
            {"sensor_id": "S2", "temp": 31.0, "status": "WARN"},
            {"sensor_id": "S3", "temp": 19.8, "status": "OK"},
        ]

        # Produce records
        prod_result = producer.produce_batch(test_topic, known_records)
        assert prod_result["produced"] == 3

        # First consumer in group reads records and commits offsets
        consumer_1 = KafkaConsumerClient(topic=test_topic, group_id=group_id)
        consumed_1 = consumer_1.consume_batch(max_messages=10, timeout=5.0)
        consumer_1.close()

        assert len(consumed_1) == 3
        consumed_ids = [r["sensor_id"] for r in consumed_1]
        assert consumed_ids == ["S1", "S2", "S3"]

        # Second consumer in the SAME group should find 0 new records because offsets were committed
        consumer_2 = KafkaConsumerClient(topic=test_topic, group_id=group_id)
        consumed_2 = consumer_2.consume_batch(max_messages=10, timeout=3.0)
        consumer_2.close()

        assert len(consumed_2) == 0

    def test_kafka_source_plugin_reads_dataframe(self, test_topic: str) -> None:
        group_id = f"test-source-group-{uuid.uuid4().hex[:6]}"
        producer = KafkaProducerClient()

        sample_data = [
            {"device_id": "D100", "reading": 10.5},
            {"device_id": "D200", "reading": 20.0},
        ]
        producer.produce_batch(test_topic, sample_data)

        source = KafkaSource()
        df = source.read({
            "topic": test_topic,
            "group_id": group_id,
            "max_messages": 10,
            "timeout": 5.0,
        })

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert set(df.columns) == {"device_id", "reading"}
        assert list(df["device_id"]) == ["D100", "D200"]
