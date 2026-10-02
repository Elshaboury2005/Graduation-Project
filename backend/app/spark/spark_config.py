"""
app/spark/spark_config.py
--------------------------
Spark-related configuration fields injected into the central Settings class.

This module is intentionally thin — it only documents what env vars are
expected.  Actual field definitions are added directly to ``Settings`` in
``app/core/config.py`` via a mixin approach to keep all settings together.

Constants
---------
KAFKA_SPARK_PACKAGE : str
    Maven coordinates for the Kafka-Spark connector.  Centralised here so
    ``spark_job_submitter.py`` and ``base_job.py`` (spark-jobs side) both
    reference the same string without duplicating it.
"""

# ── Centralised package version constant ──────────────────────────────────────
# Must match: Spark version in bitnami/spark image + Scala binary version.
# bitnami/spark:3.5.0 ships Spark 3.5.0 with Scala 2.12.
KAFKA_SPARK_PACKAGE: str = "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0"
