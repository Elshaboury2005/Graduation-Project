"""
app/pipeline/exceptions.py
--------------------------
Custom exception hierarchy for the pipeline configuration engine.

Two distinct failure modes are modelled:

``ConfigParseError``
    The YAML text itself is malformed — safe_load() could not produce a Python
    dict.  Wraps ``yaml.YAMLError`` and preserves the line/column hint.

``ConfigValidationError``
    The YAML parsed fine but the resulting dict fails the Pydantic schema or a
    business rule.  Carries a structured list of ``{"field": str, "message": str}``
    error objects so callers can surface precise, field-level feedback without
    inspecting raw Pydantic internals.
"""

from __future__ import annotations

from typing import TypedDict


class ValidationErrorDetail(TypedDict):
    """
    A single structured validation failure.

    Attributes
    ----------
    field:
        Dot-path string identifying the offending field, e.g.
        ``"storage.path"`` or ``"processing.operations.0.type"``.
    message:
        Human-readable explanation of why the value was rejected.
    """

    field: str
    message: str


class ConfigParseError(Exception):
    """
    Raised when the raw YAML cannot be parsed at all.

    This is a hard failure — there is no structured field list because the
    input was not even valid YAML.  The exception message includes the
    line/column hint from PyYAML when available.

    Example
    -------
    ::

        raise ConfigParseError("YAML syntax error at line 4, column 3: ...")
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:  # noqa: D105
        return self.message


class ConfigValidationError(Exception):
    """
    Raised when YAML is syntactically valid but violates the config schema.

    Carries a list of :class:`ValidationErrorDetail` objects so callers
    (e.g. ``pipeline_config_service.py``) can translate them into the
    ``{"valid": false, "errors": [...]}`` API response shape without
    needing to inspect Pydantic internals.

    Parameters
    ----------
    errors:
        One or more structured error dicts, each with ``field`` and
        ``message`` keys.
    message:
        Optional human-readable summary used as the exception string.

    Example
    -------
    ::

        raise ConfigValidationError(
            errors=[{"field": "storage.path", "message": "Must be absolute"}],
            message="1 validation error",
        )
    """

    def __init__(
        self,
        errors: list[ValidationErrorDetail],
        message: str = "Pipeline configuration validation failed",
    ) -> None:
        super().__init__(message)
        self.errors: list[ValidationErrorDetail] = errors
        self.message = message

    def __str__(self) -> str:  # noqa: D105
        detail = "; ".join(
            f"{e['field']}: {e['message']}" for e in self.errors
        )
        return f"{self.message} — {detail}"
