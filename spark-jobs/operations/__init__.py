"""
spark-jobs/operations/__init__.py
----------------------------------
PySpark DataFrame operation modules.

Each module exposes pure functions that accept and return ``pyspark.sql.DataFrame``
objects.  Functions are stateless and free of side-effects — they can be tested
independently using a local ``SparkSession`` without a running cluster.
"""
