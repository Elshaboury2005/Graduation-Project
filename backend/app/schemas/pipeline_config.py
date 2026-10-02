"""
app/schemas/pipeline_config.py
-------------------------------
Pydantic v2 request/response schemas for the pipeline configuration API.

These are *API wire-format* models, distinct from the internal domain models
in ``app.pipeline.config_models``.  Keeping them separate lets the API
contract evolve independently of the internal representation.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ValidatePipelineRequest(BaseModel):
    """
    Request body for ``POST /api/pipelines/validate``.

    The caller sends the raw YAML text; the server parses and validates it,
    returning a structured result without side effects (no DB writes).
    """

    model_config = ConfigDict(extra="forbid")

    yaml_content: str = Field(
        ...,
        description=(
            "Raw YAML text of the pipeline configuration to validate.  "
            "The server will parse, schema-check, and business-rule-check "
            "the content and return a structured result."
        ),
        examples=[
            "pipeline:\n  name: sales-pipeline\n  version: '1.0'\n..."
        ],
    )


class ValidationErrorItem(BaseModel):
    """A single structured validation failure returned by the validate endpoint."""

    model_config = ConfigDict(extra="forbid")

    field: str = Field(
        ...,
        description=(
            "Dot-path string identifying the offending field, "
            "e.g. 'storage.path' or 'processing.operations.0.type'."
        ),
    )
    message: str = Field(
        ...,
        description="Human-readable explanation of what went wrong.",
    )


class ValidatePipelineResponse(BaseModel):
    """
    Response body for ``POST /api/pipelines/validate``.

    The HTTP status code is always 200 — validity is communicated through
    the ``valid`` flag, not through 4xx codes.  This design lets clients
    display all errors at once rather than dealing with a cascade of
    individual error responses.
    """

    model_config = ConfigDict(extra="forbid")

    valid: bool = Field(
        ...,
        description="True when the configuration passed all checks.",
    )
    errors: list[ValidationErrorItem] = Field(
        default_factory=list,
        description=(
            "Ordered list of validation failures.  "
            "Empty when valid is True."
        ),
    )
