"""Regression coverage for persisted ChaosLab definitions."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from fastapi import BackgroundTasks

from app.api.routes.experiments import run_experiment


class _AsyncDb:
    def __init__(self, experiment) -> None:
        self.experiment = experiment
        self.added = []

    async def get(self, _model, _identifier):
        return self.experiment

    def add(self, item) -> None:
        self.added.append(item)

    async def commit(self) -> None:
        return None

    async def refresh(self, item) -> None:
        item.id = uuid.uuid4()


def test_run_without_body_uses_persisted_definitions() -> None:
    from app.models.experiment import Experiment

    experiment = Experiment(
        id=uuid.uuid4(),
        name="stored-definition",
        experiment_yaml="""experiment:
  name: stored-definition
target:
  service: kafka
fault:
  type: container_stop
  duration: 1
validation:
  expected_data_loss: 0
  max_recovery_time: 5
""",
        pipeline_yaml="pipeline:\n  name: stored\n",
    )
    experiment.created_at = datetime.now(tz=timezone.utc)
    db = _AsyncDb(experiment)
    tasks = BackgroundTasks()

    response = asyncio.run(
        run_experiment(
            experiment_id=experiment.id,
            background_tasks=tasks,
            db=db,
            request=None,
        )
    )

    assert response["status"] == "running"
    assert len(tasks.tasks) == 1
    assert tasks.tasks[0].args[-1] == experiment.pipeline_yaml
