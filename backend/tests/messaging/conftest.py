"""
tests/messaging/conftest.py
----------------------------
Pytest fixtures and configuration for the Kafka messaging test suite.

Includes an autouse fixture that checks Kafka broker reachability for any test
marked with `@pytest.mark.integration`.  If Kafka is not reachable, the test is
skipped gracefully rather than failing, keeping unit test runs clean when Docker
is not running.
"""

from __future__ import annotations

import logging

import pytest

logger = logging.getLogger(__name__)


def is_kafka_reachable(timeout: float = 2.0) -> bool:
    """
    Probe the configured Kafka broker to verify connectivity.

    Parameters
    ----------
    timeout : float
        Timeout in seconds for metadata query.

    Returns
    -------
    bool
        True if Kafka broker responds, False otherwise.
    """
    try:
        from app.messaging.kafka_admin import KafkaAdminClient

        admin = KafkaAdminClient()
        health = admin.health_check(timeout=timeout)
        return bool(health.get("connected", False))
    except Exception as exc:
        logger.debug("Kafka reachability check failed: %s", exc)
        return False


@pytest.fixture(autouse=True)
def skip_if_no_kafka(request: pytest.FixtureRequest) -> None:
    """
    Automatically skip any test marked with `@pytest.mark.integration` if Kafka
    is not reachable.
    """
    if request.node.get_closest_marker("integration"):
        if not is_kafka_reachable():
            pytest.skip(
                "Kafka broker is not reachable (is Docker / Kafka container running?). Skipping integration test."
            )
