from unittest.mock import MagicMock

from app.reliability.experiment_models import ExperimentModel
from app.reliability.fault_injectors.base_fault import FAULT_INJECTOR_REGISTRY
from app.reliability.fault_injectors.service_delay_fault import ServiceDelayFault


def test_service_delay_is_registered() -> None:
    assert FAULT_INJECTOR_REGISTRY["service_delay"] is ServiceDelayFault


def test_service_delay_injects_and_rolls_back() -> None:
    docker = MagicMock()
    docker.exec_in_container.return_value = (0, "")
    injector = ServiceDelayFault(docker)

    result = injector.inject("kafka", {"delay_ms": 250, "duration": 10})
    injector.rollback("kafka", result)

    assert docker.exec_in_container.call_count == 2
    assert "delay" in docker.exec_in_container.call_args_list[0].args[1]
    assert "250ms" in docker.exec_in_container.call_args_list[0].args[1]
    assert result["fault_type"] == "service_delay"


def test_service_delay_config_enforces_safe_bound() -> None:
    config = ExperimentModel.model_validate(
        {
            "experiment": {"name": "delayed-kafka"},
            "target": {"service": "kafka"},
            "fault": {"type": "service_delay", "duration": 10, "delay_ms": 500},
            "validation": {"expected_data_loss": 0, "max_recovery_time": 30},
        }
    )
    assert config.fault.delay_ms == 500
