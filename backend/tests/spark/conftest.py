"""
backend/tests/spark/conftest.py
---------------------------------
Shared fixtures and skip guards for backend Spark integration tests.

All tests in this directory are marked ``@pytest.mark.integration`` and
are skipped automatically when the Spark master is not reachable, using
the same pattern established for Kafka integration tests in Phase 4.
"""

from __future__ import annotations

from functools import lru_cache

import pytest


@lru_cache
def _spark_is_reachable() -> bool:
    """
    Return True if the Spark master REST API responds.

    Tries ``http://spark-master:8080/json/`` (container network) and then
    ``http://localhost:8080/json/`` (host-mapped port) so the check works
    both inside Docker and when running tests on the developer's laptop
    with ``docker-compose up`` active.
    """
    import httpx

    for url in ("http://spark-master:8080/json/", "http://localhost:8080/json/"):
        try:
            resp = httpx.get(url, timeout=3.0)
            if resp.status_code == 200:
                return True
        except Exception:
            continue
    return False


@pytest.fixture(autouse=True)
def skip_if_no_spark(request: pytest.FixtureRequest) -> None:
    """
    Skip the entire test session if the Spark cluster is not reachable.

    Applied automatically to every test in this directory. The probe is cached,
    while function scope lets the fixture inspect the current test's marker.
    """
    if request.node.get_closest_marker("integration") is None:
        return  # non-integration tests always run
    if not _spark_is_reachable():
        pytest.skip(
            "Spark master is not reachable — skipping integration tests. "
            "Start the full stack with: docker-compose up"
        )
