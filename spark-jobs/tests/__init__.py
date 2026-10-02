"""
spark-jobs/tests/__init__.py
-----------------------------
Package marker for spark-jobs unit tests.

Tests here use ``pyspark.sql.SparkSession.builder.master("local[2]")`` — no
Docker cluster is required.
"""
