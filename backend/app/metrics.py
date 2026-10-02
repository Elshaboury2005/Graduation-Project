"""Prometheus metrics emitted by pipeline execution and ChaosLab."""

from prometheus_client import Counter, Histogram, REGISTRY


def _metric(factory, name: str, documentation: str, labels: list[str], **kwargs):
    """Reuse a registered collector during reloads without hiding the name."""
    return REGISTRY._names_to_collectors.get(name) or factory(
        name, documentation, labels, **kwargs
    )


pipeline_records_processed_total = _metric(
    Counter, "pipeline_records_processed_total", "Total records processed", ["pipeline_name"]
)
pipeline_processing_latency_seconds = _metric(
    Histogram, "pipeline_processing_latency_seconds", "Stage latency", ["stage"],
    buckets=[.01, .05, .1, .25, .5, 1, 2.5, 5, 10],
)
pipeline_errors_total = _metric(
    Counter, "pipeline_errors_total", "Pipeline execution errors", ["stage"]
)
pipeline_recovery_time_seconds = _metric(
    Histogram, "pipeline_recovery_time_seconds", "Fault recovery time", ["target_service"],
    buckets=[1, 2, 5, 10, 15, 20, 30, 60, 120],
)
experiment_duration_seconds = _metric(
    Histogram, "experiment_duration_seconds", "Chaos experiment duration", ["fault_type"],
    buckets=[5, 10, 20, 30, 60, 120, 300],
)
