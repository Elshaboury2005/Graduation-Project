"""
app/services/pipeline_config_service.py
-----------------------------------------
Service-layer orchestration for pipeline configuration parsing and validation.

This module is the single entry point that API routes call.  It composes the
:class:`~app.pipeline.parser.PipelineConfigParser` (structural + type checks)
with the :class:`~app.pipeline.validator.PipelineBusinessValidator`
(cross-section business rules), and normalises all possible outcomes into a
single ``{"valid": bool, "errors": [...]}`` dict.

Key design decisions
--------------------
* **Never raises** — this function always returns a dict.  All exceptions
  from the parser and validator are caught and translated into error items.
  This prevents unhandled 500 responses on the validate endpoint.
* **Two-phase validation** — structural validation (Pydantic) runs first;
  business rules only run if structural validation passes.  This prevents
  misleading business-rule errors on a structurally broken config.
* **No side effects** — this function does not write to the database or
  trigger any external calls.  Persistence is a later-phase concern.
"""

from __future__ import annotations

import logging

from app.pipeline.exceptions import ConfigParseError, ConfigValidationError
from app.pipeline.parser import PipelineConfigParser
from app.pipeline.validator import PipelineBusinessValidator

logger = logging.getLogger(__name__)

# Module-level singletons — both are stateless so sharing is safe.
_parser = PipelineConfigParser()
_validator = PipelineBusinessValidator()


def validate_pipeline_config(yaml_content: str) -> dict:
    """
    Parse and validate a pipeline configuration YAML string.

    This function orchestrates the full validation pipeline:

    1. ``PipelineConfigParser.parse_string`` — YAML → ``PipelineConfig``
    2. ``PipelineBusinessValidator.validate`` — cross-section business rules

    It catches every known exception and returns a normalised result dict
    rather than propagating errors to the caller.

    Parameters
    ----------
    yaml_content:
        Raw YAML string to parse and validate.

    Returns
    -------
    dict
        Always has the shape::

            {
                "valid": bool,
                "errors": [
                    {"field": str, "message": str},
                    ...
                ]
            }

        ``errors`` is an empty list when ``valid`` is True.

    Examples
    --------
    Success::

        result = validate_pipeline_config("pipeline:\\n  name: my-pipeline\\n ...")
        # {"valid": True, "errors": []}

    Failure::

        result = validate_pipeline_config("pipeline:\\n  name: MY PIPELINE\\n ...")
        # {"valid": False, "errors": [{"field": "pipeline.name", "message": "..."}]}
    """
    # ── Phase 1: YAML parsing + Pydantic schema validation ─────────────────────
    try:
        config = _parser.parse_string(yaml_content)
    except ConfigParseError as exc:
        logger.info("YAML parse error: %s", exc.message)
        return {
            "valid": False,
            "errors": [
                {
                    "field": "yaml",
                    "message": f"YAML parse error: {exc.message}",
                }
            ],
        }
    except ConfigValidationError as exc:
        logger.info(
            "Schema validation failed with %d error(s): %s",
            len(exc.errors),
            exc.message,
        )
        return {"valid": False, "errors": exc.errors}

    # ── Phase 2: business rules ─────────────────────────────────────────────────
    business_errors = _validator.validate(config)
    if business_errors:
        logger.info(
            "Business validation failed for pipeline '%s' with %d error(s)",
            config.pipeline.name,
            len(business_errors),
        )
        return {"valid": False, "errors": business_errors}

    logger.info(
        "Pipeline config '%s' v%s passed all validation checks",
        config.pipeline.name,
        config.pipeline.version,
    )
    return {"valid": True, "errors": []}
