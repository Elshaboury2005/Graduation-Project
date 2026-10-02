"""
app/metrics.py
--------------
Prometheus metrics definitions for the platform.

Defines the core metrics for tracking pipeline performance, latency, errors,
and reliability experiments. 
"""

from prometheus_client import Counter, Gauge, Histogram

# pipeline_records_processed_total: Counts total records processed by pipelines.
try:
    pipeline_records_processed_total = Counter(
        'pipeline_records_processed_total',
        'Total number of records processed by pipelines',
        ['pipeline_name']
    )
except ValueError:
    pass

# pipeline_processing_latency_seconds: Tracks distribution of processing latency.
try:
    pipeline_processing_latency_seconds = Histogram(
        'pipeline_processing_latency_seconds',
        'Latency of pipeline processing stages in seconds',
        ['stage'],
        buckets=[.01, .05, .1, .25, .5, 1, 2.5, 5, 10]
    )
except ValueError:
    pass

# pipeline_errors_total: Counts total errors during pipeline execution.
try:
    pipeline_errors_total = Counter(
        'pipeline_errors_total',
        'Total number of errors encountered during pipeline execution',
        ['stage']
    )
except ValueError:
    pass

# pipeline_recovery_time_seconds: Measures time to recover from faults.
try:
    pipeline_recovery_time_seconds = Histogram(
        'pipeline_recovery_time_seconds',
        'Time taken to recover from faults in seconds',
        ['target_service'],
        buckets=[1, 2, 5, 10, 15, 20, 30, 60, 120]
    )
except ValueError:
    pass

# experiment_duration_seconds: Tracks duration of chaos experiments.
try:
    experiment_duration_seconds = Histogram(
        'experiment_duration_seconds',
        'Duration of chaos experiments in seconds',
        ['fault_type'],
        buckets=[5, 10, 20, 30, 60, 120, 300]
    )
except ValueError:
    pass
