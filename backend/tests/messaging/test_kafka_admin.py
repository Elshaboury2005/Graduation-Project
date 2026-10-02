"""
tests/messaging/test_kafka_admin.py
------------------------------------
Integration tests for KafkaAdminClient against a live Kafka broker.

Marked `@pytest.mark.integration` so they are automatically skipped if Kafka
is not running.
"""

from __future__ import annotations

import uuid
import pytest

from app.messaging.kafka_admin import KafkaAdminClient


@pytest.mark.integration
class TestKafkaAdminIntegration:
    """Integration tests for topic creation, existence check, deletion, and health probe."""

    @pytest.fixture()
    def admin_client(self) -> KafkaAdminClient:
        return KafkaAdminClient()

    @pytest.fixture()
    def test_topic_name(self, admin_client: KafkaAdminClient) -> str:
        """Generate a unique test topic name and ensure clean teardown."""
        topic_name = f"test-admin-topic-{uuid.uuid4().hex[:8]}"
        yield topic_name
        # Teardown: delete topic if created
        admin_client.delete_topic(topic_name)

    def test_health_check_returns_connected_true(
        self, admin_client: KafkaAdminClient
    ) -> None:
        health = admin_client.health_check()
        assert health["connected"] is True
        assert health["broker_count"] >= 1
        assert health["error"] is None

    def test_topic_lifecycle_create_exists_delete(
        self, admin_client: KafkaAdminClient, test_topic_name: str
    ) -> None:
        # Initially topic should not exist
        assert admin_client.topic_exists(test_topic_name) is False

        # Create topic
        result = admin_client.create_topic(
            topic_name=test_topic_name, partitions=2, replication_factor=1
        )
        assert result["created"] is True
        assert result["already_existed"] is False
        assert result["partitions"] == 2

        # Verify topic exists
        assert admin_client.topic_exists(test_topic_name) is True

        # Re-creating the same topic should be a no-op (already_existed=True)
        recreate_result = admin_client.create_topic(
            topic_name=test_topic_name, partitions=2, replication_factor=1
        )
        assert recreate_result["created"] is False
        assert recreate_result["already_existed"] is True

        # Delete topic
        deleted = admin_client.delete_topic(test_topic_name)
        assert deleted is True
