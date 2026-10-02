# spark-jobs/Dockerfile
# ----------------------
# Based on the same bitnami/spark version used in docker-compose.yml so the
# Python/PySpark environment in this image exactly matches the cluster.
#
# Usage (via spark-submit from the backend container):
#   The spark-jobs/ directory is mounted into the cluster nodes as a volume
#   so no separate image build is required for job submission.  This Dockerfile
#   exists as documentation and for running spark-jobs tests locally.

FROM bitnami/spark:3.5.0

USER root

# Install extra Python packages if requirements.txt is non-empty
COPY requirements.txt /tmp/spark-jobs-requirements.txt
RUN pip install --no-cache-dir -r /tmp/spark-jobs-requirements.txt || true

# Copy job scripts into the image (for standalone testing)
COPY . /opt/spark-jobs/

USER 1001

WORKDIR /opt/spark-jobs
