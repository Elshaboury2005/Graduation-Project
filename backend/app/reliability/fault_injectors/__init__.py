"""
app/reliability/fault_injectors/__init__.py
--------------------------------------------
Fault injector registry and auto-discovery.

All concrete injector modules in this package register themselves via the
``@register_fault_injector`` decorator, mirroring the Phase 3 plugin system.
Import this package to populate the ``FAULT_INJECTOR_REGISTRY``.
"""

from app.reliability.fault_injectors.base_fault import (
    BaseFaultInjector,
    FAULT_INJECTOR_REGISTRY,
    register_fault_injector,
)

# Import all concrete injectors to trigger their registration
from app.reliability.fault_injectors import (  # noqa: F401
    container_stop_fault,
    container_restart_fault,
    network_disruption_fault,
    cpu_stress_fault,
    memory_stress_fault,
    disk_pressure_fault,
    service_delay_fault,
)

__all__ = [
    "BaseFaultInjector",
    "FAULT_INJECTOR_REGISTRY",
    "register_fault_injector",
]
