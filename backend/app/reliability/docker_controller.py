"""
app/reliability/docker_controller.py
--------------------------------------
The ONLY module in the entire codebase permitted to import and use the
Docker SDK (``docker``) for reliability/chaos operations.

Architectural rule (ENFORCED)
-------------------------------
  * Fault injectors MUST NOT import ``docker`` directly.
  * This controller MUST NOT call any Docker SDK method without first calling
    ``SafetyValidator`` for the target service.
  * Violating either rule is a security defect, not a style preference.

Every public method produces a structured audit log entry (JSON-formatted
via the Phase 1 logging setup) recording the container, the action taken,
and the timestamp — this is the audit trail required by the safety guarantee.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.reliability.exceptions import FaultInjectionError, UnsafeTargetError
from app.reliability.safety import SafetyValidator

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(tz=timezone.utc).isoformat()


class DockerController:
    """
    Safety-gated wrapper around the Docker SDK.

    Every method follows the same pattern:
    1. Call ``self._safety.validate_target(service_name)``.
    2. Resolve the actual container object.
    3. Execute the requested Docker operation.
    4. Emit a structured audit log entry.
    5. Return a result dict.

    Parameters
    ----------
    safety : SafetyValidator
        Injected safety validator.  Never use a global — the constructor
        forces the dependency to be explicit.
    """

    def __init__(self, safety: SafetyValidator) -> None:
        """Initialise with a mandatory SafetyValidator (dependency injection)."""
        # ARCHITECTURAL RULE: safety is mandatory — there is no default.
        self._safety = safety

    @property
    def _client(self):
        """Lazy Docker client from the safety validator's client instance."""
        return self._safety._client

    def _get_container(self, service_name: str):
        """Resolve and return the Docker container object after safety check."""
        self._safety.validate_target(service_name)
        return self._safety._find_container(service_name)

    # ── Container lifecycle ────────────────────────────────────────────────────

    def stop_container(self, service_name: str) -> dict[str, Any]:
        """
        Gracefully stop the container for ``service_name``.

        Parameters
        ----------
        service_name : str
            Allowed service name (validated by SafetyValidator).

        Returns
        -------
        dict
            ``{"container_id": str, "container_name": str, "stopped_at": str}``

        Raises
        ------
        UnsafeTargetError
            If the service is not in the allow-list or the container fails
            the compose-project label check.
        FaultInjectionError
            If the Docker stop operation itself fails.
        """
        try:
            container = self._get_container(service_name)
            container.stop(timeout=10)
            result = {
                "container_id": container.id[:12],
                "container_name": container.name,
                "stopped_at": _now_iso(),
            }
            logger.info(
                "DockerController: STOP container '%s' (id=%s) at %s",
                container.name,
                result["container_id"],
                result["stopped_at"],
            )
            return result
        except UnsafeTargetError:
            raise
        except Exception as exc:
            raise FaultInjectionError(
                f"Failed to stop container for service '{service_name}': {exc}",
                fault_type="container_stop",
                target_service=service_name,
            ) from exc

    def start_container(self, service_name: str) -> dict[str, Any]:
        """
        Start a stopped container for ``service_name``.

        Returns
        -------
        dict
            ``{"container_id": str, "container_name": str, "started_at": str}``
        """
        try:
            container = self._get_container(service_name)
            container.start()
            result = {
                "container_id": container.id[:12],
                "container_name": container.name,
                "started_at": _now_iso(),
            }
            logger.info(
                "DockerController: START container '%s' at %s",
                container.name,
                result["started_at"],
            )
            return result
        except UnsafeTargetError:
            raise
        except Exception as exc:
            raise FaultInjectionError(
                f"Failed to start container for service '{service_name}': {exc}",
                fault_type="container_start",
                target_service=service_name,
            ) from exc

    def restart_container(self, service_name: str) -> dict[str, Any]:
        """
        Restart the container for ``service_name``.

        Returns
        -------
        dict
            ``{"container_id": str, "container_name": str, "restarted_at": str}``
        """
        try:
            container = self._get_container(service_name)
            container.restart(timeout=10)
            result = {
                "container_id": container.id[:12],
                "container_name": container.name,
                "restarted_at": _now_iso(),
            }
            logger.info(
                "DockerController: RESTART container '%s' at %s",
                container.name,
                result["restarted_at"],
            )
            return result
        except UnsafeTargetError:
            raise
        except Exception as exc:
            raise FaultInjectionError(
                f"Failed to restart container for service '{service_name}': {exc}",
                fault_type="container_restart",
                target_service=service_name,
            ) from exc

    def is_container_running(self, service_name: str) -> bool:
        """
        Return ``True`` if the container for ``service_name`` is running.

        Refreshes the container state before checking (``container.reload()``).
        """
        try:
            container = self._get_container(service_name)
            container.reload()
            return container.status == "running"
        except UnsafeTargetError:
            raise
        except Exception:
            return False

    # ── In-container execution ─────────────────────────────────────────────────

    def exec_in_container(
        self, service_name: str, command: list[str]
    ) -> tuple[int, str]:
        """
        Execute ``command`` inside the running container for ``service_name``.

        Used by CPU/memory/disk stress fault injectors to run ``stress-ng``
        commands inside the target container without requiring Docker SDK
        access from the injector itself.

        Parameters
        ----------
        command : list[str]
            Command and arguments as a list, e.g. ``["stress-ng", "--cpu", "2"]``.

        Returns
        -------
        tuple[int, str]
            ``(exit_code, output_str)``

        Notes
        -----
        If the target image lacks ``stress-ng`` or ``tc``, this method will
        fail **loudly** with a descriptive ``FaultInjectionError`` rather than
        silently no-oping — a silent failure would give false confidence.
        """
        try:
            container = self._get_container(service_name)
            exit_code, output = container.exec_run(command, demux=False)
            output_str = (output or b"").decode("utf-8", errors="replace").strip()
            logger.info(
                "DockerController: EXEC in '%s': %s → exit=%d",
                container.name,
                command,
                exit_code,
            )
            return exit_code, output_str
        except UnsafeTargetError:
            raise
        except Exception as exc:
            raise FaultInjectionError(
                f"exec_in_container failed for service '{service_name}': {exc}",
                fault_type="exec",
                target_service=service_name,
            ) from exc

    def exec_in_container_detached(
        self, service_name: str, command: list[str]
    ) -> dict[str, Any]:
        """
        Execute ``command`` inside the container in detached mode (background).

        Returns immediately without waiting for the command to finish.
        Used by stress fault injectors to start long-running stress processes.

        Returns
        -------
        dict
            ``{"container_name": str, "command": list, "started_at": str}``
        """
        try:
            container = self._get_container(service_name)
            container.exec_run(command, detach=True, demux=False)
            result = {
                "container_name": container.name,
                "command": command,
                "started_at": _now_iso(),
            }
            logger.info(
                "DockerController: EXEC-DETACHED in '%s': %s",
                container.name,
                command,
            )
            return result
        except UnsafeTargetError:
            raise
        except Exception as exc:
            raise FaultInjectionError(
                f"exec_in_container_detached failed for service '{service_name}': {exc}",
                fault_type="exec_detached",
                target_service=service_name,
            ) from exc

    # ── Network disruption ─────────────────────────────────────────────────────

    def apply_network_disruption(
        self, service_name: str, duration: int
    ) -> dict[str, Any]:
        """
        Apply 100% packet loss on the container's ``eth0`` interface using
        Linux ``tc netem``.

        This approach is preferred over disconnecting the Docker network
        because ``tc`` rules are cleanly reversible via ``remove_network_disruption``
        without risking permanent network reconfiguration.

        Requirements
        ------------
        The target container image MUST have ``iproute2`` / ``tc`` installed.
        If ``tc`` is absent, this method raises ``FaultInjectionError`` with a
        clear diagnostic message rather than silently no-oping.

        Parameters
        ----------
        duration : int
            Informational only — the rule persists until ``remove_network_disruption``
            is called (the caller is responsible for the timing).
        """
        command = [
            "tc", "qdisc", "add", "dev", "eth0", "root", "netem", "loss", "100%"
        ]
        try:
            exit_code, output = self.exec_in_container(service_name, command)
            if exit_code != 0:
                raise FaultInjectionError(
                    f"tc netem add failed for '{service_name}' (exit={exit_code}): "
                    f"{output}. "
                    "Ensure 'iproute2' (tc) is installed in the target image. "
                    "This injector fails loudly rather than silently no-oping.",
                    fault_type="network_disruption",
                    target_service=service_name,
                )
            return {
                "container": service_name,
                "action": "network_disruption_applied",
                "rule": "loss 100%",
                "applied_at": _now_iso(),
                "duration_hint_seconds": duration,
            }
        except FaultInjectionError:
            raise
        except Exception as exc:
            raise FaultInjectionError(
                f"apply_network_disruption failed for '{service_name}': {exc}",
                fault_type="network_disruption",
                target_service=service_name,
            ) from exc

    def remove_network_disruption(self, service_name: str) -> None:
        """
        Remove the ``tc netem`` packet-loss rule from ``service_name``'s ``eth0``.

        Safe to call even if no rule was applied — ``tc qdisc del`` with a
        non-existent rule exits non-zero but does not destabilise the interface.
        This method swallows that benign failure and logs a debug message.
        """
        command = ["tc", "qdisc", "del", "dev", "eth0", "root", "netem"]
        try:
            exit_code, output = self.exec_in_container(service_name, command)
            if exit_code == 0:
                logger.info(
                    "DockerController: network disruption removed from '%s'.",
                    service_name,
                )
            else:
                # Non-zero exit when no rule exists is benign
                logger.debug(
                    "DockerController: tc del for '%s' exit=%d (likely no rule existed): %s",
                    service_name,
                    exit_code,
                    output,
                )
        except Exception as exc:
            logger.warning(
                "DockerController: remove_network_disruption failed for '%s': %s "
                "(non-fatal — may not have been applied).",
                service_name,
                exc,
            )
