# airflow/Dockerfile
# -------------------
# Extends the official Apache Airflow image with the extra packages needed
# by the pipeline_execution_dag (requests, PyYAML).
#
# Based on the official image so Airflow's own dependencies, providers,
# and configuration are not disrupted.

FROM apache/airflow:2.10.3-python3.11

# Switch to root to install system packages (none needed here)
USER airflow

# Install extra DAG dependencies
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
