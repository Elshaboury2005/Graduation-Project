"""Explainable anomaly detection for reliability metric snapshots."""

from __future__ import annotations

from collections.abc import Iterable
from statistics import median
from typing import Any

try:
    from sklearn.ensemble import IsolationForest
except ImportError:
    IsolationForest = None  # type: ignore[misc,assignment]


class ReliabilityAnalyzer:
    """Analyze historical metric snapshots without making causal guarantees."""

    def __init__(self, contamination: float = 0.1) -> None:
        self.contamination = min(max(contamination, 0.01), 0.5)

    def analyze(
        self, observations: Iterable[dict[str, float]], logs: Iterable[str] = ()
    ) -> dict[str, Any]:
        snapshots = [self._numeric_snapshot(item) for item in observations]
        if not snapshots:
            raise ValueError("At least one metric observation is required.")

        metric_names = sorted({name for snapshot in snapshots for name in snapshot})
        anomalies, method = self._detect_anomalies(snapshots, metric_names)
        contributors = self._contributors(snapshots[-1])
        contributors.extend(self._log_contributors(logs))
        contributors = list(dict.fromkeys(contributors))
        risk_score = min(100, len(anomalies) * 25 + len(contributors) * 12)
        risk_level = "high" if risk_score >= 60 else "medium" if risk_score >= 25 else "low"
        return {
            "method": method,
            "observation_count": len(snapshots),
            "risk_score": risk_score,
            "risk_level": risk_level,
            "anomalies": anomalies,
            "likely_contributors": contributors,
            "recommendations": self._recommendations(contributors),
            "limitations": (
                "This is an explainable risk indicator based on supplied metrics and logs; "
                "it does not establish root cause or predict failures with certainty."
            ),
        }

    @staticmethod
    def _numeric_snapshot(snapshot: dict[str, float]) -> dict[str, float]:
        values = {key: float(value) for key, value in snapshot.items()}
        if not values:
            raise ValueError("Metric observations cannot be empty.")
        return values

    def _detect_anomalies(
        self, snapshots: list[dict[str, float]], metric_names: list[str]
    ) -> tuple[list[dict[str, Any]], str]:
        if len(snapshots) >= 8 and IsolationForest is not None:
            rows = [[snapshot.get(name, 0.0) for name in metric_names] for snapshot in snapshots]
            labels = IsolationForest(
                contamination=self.contamination, random_state=42
            ).fit_predict(rows)
            return (
                [
                    {"index": index, "metrics": snapshots[index]}
                    for index, label in enumerate(labels)
                    if label == -1
                ],
                "isolation_forest",
            )

        anomalies: list[dict[str, Any]] = []
        for name in metric_names:
            values = [snapshot.get(name, 0.0) for snapshot in snapshots]
            centre = median(values)
            deviations = [abs(value - centre) for value in values]
            mad = median(deviations)
            if mad == 0:
                continue
            for index, value in enumerate(values):
                robust_z = 0.6745 * (value - centre) / mad
                if abs(robust_z) >= 3.5:
                    anomalies.append({"index": index, "metric": name, "value": value})
        return anomalies, "robust_z_score"

    @staticmethod
    def _contributors(snapshot: dict[str, float]) -> list[str]:
        contributors: list[str] = []
        if snapshot.get("error_rate", 0) > 0.05:
            contributors.append("elevated error rate")
        if snapshot.get("consumer_lag", 0) > 1_000:
            contributors.append("Kafka consumer lag")
        if snapshot.get("latency_ms", 0) > 1_000:
            contributors.append("high processing latency")
        if snapshot.get("recovery_time_seconds", 0) > 30:
            contributors.append("slow service recovery")
        if snapshot.get("cpu_percent", 0) > 85:
            contributors.append("high CPU utilisation")
        if snapshot.get("memory_percent", 0) > 85:
            contributors.append("high memory utilisation")
        return contributors

    @staticmethod
    def _log_contributors(logs: Iterable[str]) -> list[str]:
        joined = " ".join(logs).lower()
        return [
            label
            for token, label in {
                "kafka": "Kafka-related log signals",
                "timeout": "timeout log signals",
                "out of memory": "out-of-memory log signals",
            }.items()
            if token in joined
        ]

    @staticmethod
    def _recommendations(contributors: list[str]) -> list[str]:
        recommendations: list[str] = []
        if any("Kafka" in item for item in contributors):
            recommendations.append("Review consumer instances, partition distribution, and consumer processing latency.")
        if any("CPU" in item or "memory" in item for item in contributors):
            recommendations.append("Review resource limits and scale the affected worker before the next experiment.")
        if any("latency" in item or "timeout" in item for item in contributors):
            recommendations.append("Inspect upstream dependency latency and retry/backoff settings.")
        if any("recovery" in item for item in contributors):
            recommendations.append("Review readiness probes and service startup dependencies.")
        return recommendations or ["Continue monitoring; no dominant reliability risk was identified."]
