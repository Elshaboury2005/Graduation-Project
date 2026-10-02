import pytest
from fastapi.testclient import TestClient

from app.ai.reliability_analyzer import ReliabilityAnalyzer
from app.main import app


def test_analyzer_returns_explainable_risk_and_recommendations() -> None:
    report = ReliabilityAnalyzer().analyze(
        [
            {"error_rate": 0.01, "latency_ms": 100},
            {"error_rate": 0.08, "latency_ms": 2_000, "consumer_lag": 2_000},
        ],
        ["Kafka consumer timeout while polling"],
    )

    assert report["risk_level"] in {"medium", "high"}
    assert "Kafka consumer lag" in report["likely_contributors"]
    assert report["recommendations"]
    assert "does not establish root cause" in report["limitations"]


def test_analyzer_rejects_empty_observations() -> None:
    with pytest.raises(ValueError, match="At least one"):
        ReliabilityAnalyzer().analyze([])


def test_analysis_api_returns_explainable_response() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/ai/reliability-analysis",
            json={"observations": [{"error_rate": 0.1, "latency_ms": 1_500}]},
        )

    assert response.status_code == 200
    assert response.json()["risk_level"] in {"low", "medium", "high"}
