"""
spark-jobs/base_job.py
-----------------------
Abstract base class for all PySpark job scripts.

Each concrete job (``batch_processing_job.py``, ``streaming_processing_job.py``)
extends ``BaseSparkJob``, implements ``run()``, and is submitted to the cluster
via ``spark-submit``.

Design rationale
-----------------
* ``argparse`` is used for CLI parameters so the backend can pass the full
  pipeline configuration as a JSON string without any file I/O.
* The ``SparkSession`` is created with the Kafka connector package pre-loaded
  so both batch and streaming jobs can read Kafka topics without extra setup.
* Structured JSON logging (matching the FastAPI backend's format) is written
  to stdout, which Spark captures and forwards to the driver log.
"""

from __future__ import annotations

import abc
import argparse
import json
import logging
import sys
from typing import Any

from pyspark.sql import SparkSession

# ── Constants ──────────────────────────────────────────────────────────────────

# Kafka-Spark connector coordinates.  The version must match the Spark version
# bundled in the bitnami/spark:3.5.0 image (Spark 3.5.x uses Scala 2.12).
KAFKA_SPARK_PACKAGE = "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0"


# ── JSON logging ───────────────────────────────────────────────────────────────


class _JsonFormatter(logging.Formatter):
    """
    Emit every log record as a single-line JSON object.

    Matching the format used by the FastAPI backend so log aggregation tools
    can parse both backends and Spark jobs with the same schema.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def _configure_logging(log_level: str = "INFO") -> None:
    """Configure root logger with JSON formatter writing to stdout."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level.upper())


# ── Base job ───────────────────────────────────────────────────────────────────


class BaseSparkJob(abc.ABC):
    """
    Abstract base for PySpark job scripts.

    Subclasses must implement :meth:`run`.  The :meth:`main` classmethod
    is the standard entry-point called from ``if __name__ == "__main__"``.

    Attributes
    ----------
    spark : SparkSession
        Configured SparkSession (created lazily in :meth:`_build_session`).
    args : argparse.Namespace
        Parsed CLI arguments.
    config : dict
        Parsed ``--config-json`` argument as a Python dict.
    """

    def __init__(self, args: argparse.Namespace) -> None:
        """Initialise the job with parsed CLI arguments."""
        self.args = args
        self.config: dict[str, Any] = json.loads(args.config_json)
        self.spark: SparkSession = self._build_session()
        _configure_logging(self.config.get("log_level", "INFO"))
        self.logger = logging.getLogger(self.__class__.__name__)

    # ── Abstract interface ────────────────────────────────────────────────────

    @abc.abstractmethod
    def run(self) -> None:
        """
        Execute the job.

        Implementations should read data, apply transformations, and write
        output.  They must print a ``SPARK_JOB_RESULT:`` line to stdout on
        success (see :func:`_emit_result`) so the backend can parse metrics.
        """

    # ── SparkSession factory ──────────────────────────────────────────────────

    def _build_session(self) -> SparkSession:
        """
        Create and return a configured ``SparkSession``.

        The Kafka connector package is declared here so both batch and
        streaming jobs inherit it automatically.
        """
        builder = (
            SparkSession.builder.appName(self.__class__.__name__)
            .config("spark.jars.packages", KAFKA_SPARK_PACKAGE)
            # Reduce chattiness of Spark's own log output to stderr
            .config("spark.sql.adaptive.enabled", "true")
        )
        return builder.getOrCreate()

    # ── CLI argument parser ───────────────────────────────────────────────────

    @classmethod
    def _build_arg_parser(cls) -> argparse.ArgumentParser:
        """Build the shared argument parser for all jobs."""
        parser = argparse.ArgumentParser(
            description=cls.__doc__ or "Spark job",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )
        parser.add_argument(
            "--config-json",
            required=True,
            help="Full pipeline processing configuration as a JSON string.",
        )
        parser.add_argument(
            "--input-source",
            required=True,
            help="Path to the input file (CSV or JSON) or Kafka topic.",
        )
        parser.add_argument(
            "--output-path",
            required=True,
            help="Absolute path where Parquet output should be written.",
        )
        return parser

    # ── Result emission ───────────────────────────────────────────────────────

    @staticmethod
    def _emit_result(result: dict[str, Any]) -> None:
        """
        Print a parseable result line to stdout.

        The backend's ``SparkJobSubmitter`` greps stdout for lines starting
        with ``SPARK_JOB_RESULT:`` to extract job metrics without relying on
        any side-channel.

        Parameters
        ----------
        result : dict
            Metrics dict with at minimum: ``input_rows``, ``output_rows``,
            ``duration_seconds``, ``status``.
        """
        print(f"SPARK_JOB_RESULT:{json.dumps(result)}", flush=True)

    # ── Entry-point ───────────────────────────────────────────────────────────

    @classmethod
    def main(cls) -> None:
        """
        Parse CLI arguments, instantiate the job, and call :meth:`run`.

        This classmethod is called from ``if __name__ == "__main__"`` in each
        concrete job script.
        """
        parser = cls._build_arg_parser()
        args = parser.parse_args()
        job = cls(args)
        job.run()
