"""
app/core/config.py
------------------
Application configuration via Pydantic Settings.

All values are sourced exclusively from environment variables (or a .env file).
Hard-coding secrets or environment-specific values here is forbidden.
"""

from functools import lru_cache
from typing import List

from pydantic import AnyUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration object for the platform.

    Every field maps directly to an environment variable of the same name
    (upper-cased).  Provide defaults that are safe for local development;
    production deployments must override them via the environment.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────────────────
    APP_NAME: str = "Resilient Big Data Pipeline Platform"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    AI_ANALYSIS_ENABLED: bool = True
    AI_ANOMALY_CONTAMINATION: float = 0.1

    # ── Database ───────────────────────────────────────────────────────────────
    DATABASE_URL: str = (
        "postgresql+asyncpg://platform_user:platform_pass@postgres:5432/platform_db"
    )

    # ── JWT Auth ───────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "CHANGE_ME_in_production_use_a_long_random_string"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    # ── Auth Phase 8 ───────────────────────────────────────────────────────────
    ADMIN_USERNAME: str = 'mohamed'
    ADMIN_PASSWORD: str = '123456'

    # ── CORS ───────────────────────────────────────────────────────────────────
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    # ── Spark ──────────────────────────────────────────────────────────────────
    SPARK_MASTER_URL: str = "spark://spark-master:7077"
    SPARK_JOBS_PATH: str = "/app/spark-jobs"
    SPARK_SUBMIT_TIMEOUT_SECONDS: int = 300

    # ── Kafka Messaging ────────────────────────────────────────────────────────
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9093"
    KAFKA_CLIENT_ID: str = "pipeline-platform"
    KAFKA_DEFAULT_PARTITIONS: int = 3
    KAFKA_DEFAULT_REPLICATION_FACTOR: int = 1
    KAFKA_PRODUCER_ACKS: str = "all"
    KAFKA_CONSUMER_GROUP_PREFIX: str = "pipeline-group"

    # ── HDFS Storage (Phase 6) ─────────────────────────────────────────────────
    HDFS_NAMENODE_URL: str = "http://namenode:9870"
    HDFS_USER: str = "root"
    HDFS_DEFAULT_REPLICATION: int = 1  # single-datanode local dev default

    # ── ChaosLab Reliability Engine (Phase 7) ──────────────────────────────────
    PROJECT_CONTAINER_PREFIX: str = "resilient-big-data-platform"
    """
    Docker Compose project name / container name prefix.
    Used by SafetyValidator to:
    1. Resolve the expected container name for each target service.
    2. Verify the container's com.docker.compose.project label matches
       this platform's own project — prevents targeting foreign containers.
    Override with the value of COMPOSE_PROJECT_NAME if set.
    """

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> List[str]:
        """Accept a comma-separated string or a JSON list from the environment."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v  # type: ignore[return-value]


@lru_cache
def get_settings() -> Settings:
    """
    Return the singleton Settings instance.

    Decorated with lru_cache so the .env file is read only once per process.
    """
    return Settings()
