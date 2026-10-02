"""Persist canonical experiment and pipeline YAML definitions.

Revision ID: 0002_persist_experiment_definitions
Revises: 0001_initial_schema
Create Date: 2026-10-02 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_persist_experiment_definitions"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "experiments",
        sa.Column("experiment_yaml", sa.Text(), nullable=True),
    )
    op.add_column(
        "experiments",
        sa.Column("pipeline_yaml", sa.Text(), nullable=True),
    )
    op.execute(
        "UPDATE experiments SET experiment_yaml = '' WHERE experiment_yaml IS NULL"
    )
    op.alter_column("experiments", "experiment_yaml", nullable=False)
    op.execute(
        "CREATE UNIQUE INDEX uq_experiment_runs_single_active ON experiment_runs "
        "((1)) WHERE status IN ('created', 'pending', 'validating', 'preparing', "
        "'baseline', 'injecting', 'monitoring', 'rolling_back', "
        "'waiting_for_recovery', 'validating_data', 'collecting_metrics', "
        "'analyzing', 'cleaning_up', 'generating_report')"
    )


def downgrade() -> None:
    op.drop_index("uq_experiment_runs_single_active", table_name="experiment_runs")
    op.drop_column("experiments", "pipeline_yaml")
    op.drop_column("experiments", "experiment_yaml")
