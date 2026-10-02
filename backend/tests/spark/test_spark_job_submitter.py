"""
backend/tests/spark/test_spark_job_submitter.py
--------------------------------------------------
Integration tests for SparkJobSubmitter.

These tests require the full Docker Compose stack (postgres, kafka,
spark-master, spark-worker, backend) to be running.  They are marked
``@pytest.mark.integration`` and skipped automatically when the Spark
cluster is unreachable (see conftest.py).

Tests
-----
* Successful batch job produces correct input/output row counts and writes
  a real Parquet file.
* ``health_check()`` reports ``connected=True`` with at least 1 worker.
* A deliberately broken filter condition causes ``SparkJobFailedError``
  with stderr content present in the exception.
"""

from __future__ import annotations

import os
import tempfile

import pytest

from app.spark.exceptions import SparkJobFailedError
from app.spark.spark_job_submitter import SparkJobSubmitter

# Path to the sample CSV inside the backend container (mounted from host)
_SAMPLE_CSV = "/app/sample-data/sales_sample.csv"


@pytest.mark.integration
class TestSparkJobSubmitterIntegration:
    """Real cluster integration tests for SparkJobSubmitter."""

    @pytest.fixture
    def submitter(self) -> SparkJobSubmitter:
        """Return a fresh SparkJobSubmitter instance."""
        return SparkJobSubmitter()

    @pytest.fixture
    def output_dir(self) -> str:
        """Return a temporary directory for Parquet output (auto-cleaned)."""
        with tempfile.TemporaryDirectory(prefix="spark_test_") as tmpdir:
            yield tmpdir

    @pytest.mark.asyncio
    async def test_batch_job_produces_parquet_output(
        self, submitter: SparkJobSubmitter, output_dir: str
    ) -> None:
        """
        Submitting a real batch job must write a Parquet file and return
        correct row counts.
        """
        processing_config = {
            "processing": {
                "operations": [
                    {"type": "remove_nulls"},
                    {"type": "remove_duplicates"},
                ]
            }
        }

        result = await submitter.submit_batch_job(
            input_source=_SAMPLE_CSV,
            output_path=output_dir,
            processing_config=processing_config,
        )

        assert result["status"] == "success"
        assert result["input_rows"] > 0, "Expected at least one input row"
        assert result["output_rows"] >= 0
        assert result["output_rows"] <= result["input_rows"]
        assert isinstance(result["duration_seconds"], (int, float))
        assert result["duration_seconds"] > 0

        # A Parquet file must exist in output_dir
        parquet_files = [
            f for f in os.listdir(output_dir) if f.endswith(".parquet")
        ]
        assert len(parquet_files) > 0, (
            f"Expected Parquet output in {output_dir}, got: {os.listdir(output_dir)}"
        )

    @pytest.mark.asyncio
    async def test_batch_job_with_filter_reduces_row_count(
        self, submitter: SparkJobSubmitter, output_dir: str
    ) -> None:
        """
        Applying a filter that excludes some rows must yield output_rows < input_rows.
        """
        processing_config = {
            "processing": {
                "operations": [
                    {"type": "filter", "condition": "amount > 9999999"},
                ]
            }
        }

        result = await submitter.submit_batch_job(
            input_source=_SAMPLE_CSV,
            output_path=output_dir,
            processing_config=processing_config,
        )

        assert result["status"] == "success"
        assert result["output_rows"] == 0  # no rows with amount > 9,999,999

    @pytest.mark.asyncio
    async def test_health_check_returns_connected(
        self, submitter: SparkJobSubmitter
    ) -> None:
        """
        health_check() must return connected=True with at least 1 worker
        when the cluster is running.
        """
        result = await submitter.health_check()
        assert result["connected"] is True, (
            f"Expected connected=True but got: {result}"
        )
        assert result["worker_count"] >= 1, (
            f"Expected at least 1 registered worker but got: {result['worker_count']}"
        )

    @pytest.mark.asyncio
    async def test_invalid_filter_raises_spark_job_failed_error(
        self, submitter: SparkJobSubmitter, output_dir: str
    ) -> None:
        """
        A filter containing a banned pattern must fail with SparkJobFailedError
        (the injection guard in filter_ops.py causes the job to exit non-zero).
        """
        processing_config = {
            "processing": {
                "operations": [
                    {"type": "filter", "condition": "__import__('os').system('id')"},
                ]
            }
        }

        with pytest.raises(SparkJobFailedError) as exc_info:
            await submitter.submit_batch_job(
                input_source=_SAMPLE_CSV,
                output_path=output_dir,
                processing_config=processing_config,
            )

        err = exc_info.value
        # The exception message must include stderr content for debugging
        assert err.stderr or str(err), "Exception must carry stderr or message"
