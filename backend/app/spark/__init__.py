"""
app/spark/__init__.py
---------------------
Backend Spark integration package.

Provides the configuration, job submitter, and exceptions for submitting
PySpark jobs to the Spark cluster from within the FastAPI backend process.
"""
from app.spark.exceptions import SparkJobFailedError, SparkJobTimeoutError, SparkSubmitError
from app.spark.spark_job_submitter import SparkJobSubmitter

__all__ = [
    "SparkJobSubmitter",
    "SparkSubmitError",
    "SparkJobTimeoutError",
    "SparkJobFailedError",
]
