"""
spark-jobs/streaming_processing_job.py
-----------------------------------------
PySpark Structured Streaming job.

Reads from a Kafka topic (specified in the ``messaging`` section of
``--config-json``), parses the JSON-encoded message values using the
pipeline schema, applies the processing operations, and writes the result
to ``--output-path`` as a Parquet streaming sink.

The stream triggers every 10 seconds.  For testing, ``--max-batches N``
stops the stream after N micro-batches.

Submitted via::

    spark-submit \\
        --master spark://spark-master:7077 \\
        --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \\
        streaming_processing_job.py \\
        --config-json '{"messaging": {...}, "processing": {...}, "schema": [...]}' \\
        --input-source kafka \\
        --output-path /output/stream-sink \\
        --max-batches 5
"""

from __future__ import annotations

import argparse
import time

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.streaming import StreamingQuery
from pyspark.sql.types import (
    BooleanType,
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from base_job import BaseSparkJob
from operations.aggregate_ops import aggregate
from operations.cleaning_ops import remove_duplicates, remove_nulls
from operations.column_ops import convert_type, rename_columns, select_columns
from operations.filter_ops import apply_filter

# Map Phase 2 ColumnType strings to Spark SQL types
_COLUMN_TYPE_MAP: dict[str, object] = {
    "string": StringType(),
    "integer": IntegerType(),
    "double": DoubleType(),
    "boolean": BooleanType(),
    "timestamp": TimestampType(),
}


class StreamingProcessingJob(BaseSparkJob):
    """
    Structured Streaming job: Kafka → parse JSON → apply operations → Parquet sink.

    Uses ``trigger(processingTime='10 seconds')`` and a checkpoint location
    derived from ``--output-path`` so the stream can be resumed after restarts.
    """

    def run(self) -> None:
        """Start the structured streaming query and await termination."""
        start = time.perf_counter()
        messaging_cfg = self.config.get("messaging", {})
        kafka_topic = messaging_cfg.get("topic", "")
        bootstrap_servers = messaging_cfg.get("bootstrap_servers", "kafka:9092")

        self.logger.info(
            "StreamingProcessingJob starting — topic: %s, output: %s",
            kafka_topic,
            self.args.output_path,
        )

        # ── Build Kafka source ─────────────────────────────────────────────────
        raw_stream = (
            self.spark.readStream.format("kafka")
            .option("kafka.bootstrap.servers", bootstrap_servers)
            .option("subscribe", kafka_topic)
            .option("startingOffsets", "earliest")
            .load()
        )

        # ── Parse JSON value column ────────────────────────────────────────────
        schema_def = self.config.get("schema", [])
        spark_schema = self._build_schema(schema_def)
        parsed = raw_stream.select(
            F.from_json(F.col("value").cast("string"), spark_schema).alias("data")
        ).select("data.*")

        # ── Apply operations (static mode for schema inference) ───────────────
        # We can't call .count() inside a streaming query, so operations that
        # require .count() (like cleaning_ops) are applied in foreachBatch mode.
        processing_cfg = self.config.get("processing", {})
        operations = processing_cfg.get("operations", [])

        checkpoint_path = f"{self.args.output_path}/_checkpoints"

        query: StreamingQuery = (
            parsed.writeStream.foreachBatch(
                lambda batch_df, batch_id: self._process_batch(
                    batch_df, batch_id, operations, self.args.output_path
                )
            )
            .option("checkpointLocation", checkpoint_path)
            .trigger(processingTime="10 seconds")
            .start()
        )

        self.logger.info("Streaming query started — query ID: %s", query.id)

        # ── Termination control ────────────────────────────────────────────────
        max_batches = getattr(self.args, "max_batches", None)
        if max_batches is not None and max_batches > 0:
            self._await_max_batches(query, max_batches)
        else:
            query.awaitTermination()

        duration = round(time.perf_counter() - start, 3)
        self._emit_result(
            {
                "input_rows": -1,  # unknown in streaming mode
                "output_rows": -1,
                "duration_seconds": duration,
                "status": "success",
            }
        )

    # ── Batch processing callback ─────────────────────────────────────────────

    def _process_batch(
        self,
        batch_df: DataFrame,
        batch_id: int,
        operations: list[dict],
        output_path: str,
    ) -> None:
        """
        Process a single micro-batch.

        Called by Spark's ``foreachBatch`` API.  This runs in the driver
        process and has access to full DataFrame operations including
        ``count()``.

        Parameters
        ----------
        batch_df : DataFrame
            The current micro-batch as a static DataFrame.
        batch_id : int
            Incrementing batch identifier from Spark.
        operations : list[dict]
            Operation list from the pipeline config.
        output_path : str
            Parquet sink path.
        """
        if batch_df.rdd.isEmpty():
            self.logger.info("Batch %d: empty — skipping.", batch_id)
            return

        input_rows = batch_df.count()
        self.logger.info("Batch %d: %d rows received.", batch_id, input_rows)

        df = batch_df
        for op in operations:
            op_type = op.get("type")
            if op_type == "remove_nulls":
                df = remove_nulls(df)
            elif op_type == "remove_duplicates":
                df = remove_duplicates(df)
            elif op_type == "filter":
                df = apply_filter(df, op["condition"])
            elif op_type == "select_columns":
                df = select_columns(df, op["columns"])
            elif op_type == "rename_columns":
                df = rename_columns(df, op["mapping"])
            elif op_type == "type_conversion":
                df = convert_type(df, op["column"], op["to_type"])
            elif op_type == "aggregate":
                df = aggregate(df, op["group_by"], op["operation"], op["field"])

        df.write.mode("append").parquet(output_path)
        self.logger.info(
            "Batch %d: wrote %d rows to %s", batch_id, df.count(), output_path
        )

    # ── Schema builder ────────────────────────────────────────────────────────

    def _build_schema(self, schema_def: list[dict]) -> StructType:
        """
        Convert the pipeline's schema definition into a Spark ``StructType``.

        Parameters
        ----------
        schema_def : list[dict]
            List of ``{"name": str, "type": str}`` dicts from the config.

        Returns
        -------
        StructType
            Spark schema for parsing JSON message values.
        """
        fields = []
        for col_def in schema_def:
            spark_type = _COLUMN_TYPE_MAP.get(col_def.get("type", "string"), StringType())
            fields.append(StructField(col_def["name"], spark_type, nullable=True))
        return StructType(fields)

    # ── Streaming termination helper ──────────────────────────────────────────

    def _await_max_batches(self, query: StreamingQuery, max_batches: int) -> None:
        """
        Stop the stream after *max_batches* micro-batches have been processed.

        Polls ``query.lastProgress`` every 2 seconds until the batch count
        reaches *max_batches* or the query fails.

        Parameters
        ----------
        query : StreamingQuery
            The running streaming query.
        max_batches : int
            Number of batches to process before stopping.
        """
        import time as _time

        self.logger.info("Will stop after %d micro-batch(es).", max_batches)
        while query.isActive:
            progress = query.lastProgress
            if progress and progress.get("batchId", -1) >= max_batches - 1:
                self.logger.info("Reached max_batches=%d — stopping query.", max_batches)
                query.stop()
                break
            _time.sleep(2)

    # ── Extended arg parser ────────────────────────────────────────────────────

    @classmethod
    def _build_arg_parser(cls) -> argparse.ArgumentParser:
        """Extend base parser with ``--max-batches`` for testing."""
        parser = super()._build_arg_parser()
        parser.add_argument(
            "--max-batches",
            type=int,
            default=0,
            help="Stop after N micro-batches (0 = run indefinitely).",
        )
        return parser


if __name__ == "__main__":
    StreamingProcessingJob.main()
