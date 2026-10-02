"""
app/pipeline/parser.py
-----------------------
Converts raw YAML text (or a file path) into a fully-validated
:class:`~app.pipeline.config_models.PipelineConfig` object.

The parser deliberately separates two failure modes so callers can give
targeted feedback to users:

1. **YAML syntax errors** — caught from ``yaml.YAMLError`` and re-raised as
   :class:`~app.pipeline.exceptions.ConfigParseError` with the line/column
   hint preserved.

2. **Schema validation errors** — caught from Pydantic's ``ValidationError``
   and converted into a structured :class:`~app.pipeline.exceptions.ConfigValidationError`
   whose ``errors`` list uses dot-path field names instead of Pydantic's
   tuple ``loc`` format.

No business rules are checked here — that responsibility belongs to
:class:`~app.pipeline.validator.PipelineBusinessValidator`.
"""

from __future__ import annotations

import logging
from typing import Any

import yaml
from pydantic import ValidationError

from app.pipeline.config_models import PipelineConfig
from app.pipeline.exceptions import (
    ConfigParseError,
    ConfigValidationError,
    ValidationErrorDetail,
)

logger = logging.getLogger(__name__)


def _loc_to_dotpath(loc: tuple[int | str, ...]) -> str:
    """
    Convert a Pydantic ``ValidationError`` location tuple to a dot-path string.

    Pydantic stores the error location as a tuple of mixed ``str``/``int``
    components, e.g. ``("processing", "operations", 0, "type")``.
    This function joins them with dots, converting integers to strings so the
    result reads like ``"processing.operations.0.type"``.

    Parameters
    ----------
    loc:
        The ``loc`` tuple from a single Pydantic ``ErrorDetails`` dict.

    Returns
    -------
    str
        Dot-separated path, or ``"(root)"`` when the tuple is empty.
    """
    if not loc:
        return "(root)"
    return ".".join(str(part) for part in loc)


class PipelineConfigParser:
    """
    Parses pipeline configuration documents from YAML text or file paths.

    Typical usage::

        parser = PipelineConfigParser()
        config = parser.parse_file("/configs/sales.yaml")

    Raises
    ------
    ConfigParseError
        When the input is not valid YAML syntax.
    ConfigValidationError
        When the YAML is valid but the data violates the config schema.
    """

    # ── Public API ─────────────────────────────────────────────────────────────

    def parse_string(self, yaml_content: str) -> PipelineConfig:
        """
        Parse and validate a YAML string into a :class:`PipelineConfig`.

        Parameters
        ----------
        yaml_content:
            Raw YAML text representing a pipeline configuration document.

        Returns
        -------
        PipelineConfig
            A fully-validated, type-safe configuration object.

        Raises
        ------
        ConfigParseError
            The YAML string has a syntax error (e.g. bad indentation, unclosed
            bracket).  The error message includes the line and column number
            when PyYAML provides them.
        ConfigValidationError
            The YAML parsed successfully but the resulting dict does not match
            the :class:`PipelineConfig` schema.  The ``errors`` attribute
            contains one ``{"field": ..., "message": ...}`` entry per failure.
        """
        raw: Any = self._load_yaml(yaml_content)
        return self._validate(raw)

    def parse_file(self, file_path: str) -> PipelineConfig:
        """
        Read a YAML file from disk and parse it.

        Parameters
        ----------
        file_path:
            Absolute or relative path to the YAML configuration file.

        Returns
        -------
        PipelineConfig
            A fully-validated, type-safe configuration object.

        Raises
        ------
        FileNotFoundError
            The file does not exist at *file_path*.
        ConfigParseError
            The file content is not valid YAML.
        ConfigValidationError
            The file content is valid YAML but fails schema validation.
        """
        try:
            with open(file_path, encoding="utf-8") as fh:
                yaml_content = fh.read()
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Pipeline configuration file not found: {file_path!r}. "
                "Check that the path is correct and the file exists."
            ) from None

        logger.debug("Parsing pipeline config from file: %s", file_path)
        return self.parse_string(yaml_content)

    # ── Private helpers ────────────────────────────────────────────────────────

    def _load_yaml(self, yaml_content: str) -> Any:
        """
        Run PyYAML's ``safe_load`` and convert any syntax error to
        :class:`ConfigParseError`.

        ``safe_load`` is used (never ``load``) to prevent arbitrary Python
        object instantiation from untrusted YAML documents.
        """
        try:
            return yaml.safe_load(yaml_content)
        except yaml.YAMLError as exc:
            # PyYAML attaches a ``problem_mark`` with line/column info when
            # it can determine where parsing failed.
            location = ""
            if hasattr(exc, "problem_mark") and exc.problem_mark is not None:
                mark = exc.problem_mark
                # YAML lines/columns are 0-indexed; add 1 for human-friendly output.
                location = (
                    f" at line {mark.line + 1}, column {mark.column + 1}"
                )
            raise ConfigParseError(
                f"YAML syntax error{location}: {exc.problem if hasattr(exc, 'problem') else exc}"
            ) from exc

    def _validate(self, raw: Any) -> PipelineConfig:
        """
        Run Pydantic validation on the parsed Python object.

        Converts each ``ErrorDetails`` entry from Pydantic's ``ValidationError``
        into a ``{"field": str, "message": str}`` dict using dot-path field
        names.
        """
        if not isinstance(raw, dict):
            raise ConfigParseError(
                "Pipeline configuration must be a YAML mapping (got "
                f"{type(raw).__name__!r}).  Check that the document is not an "
                "empty file or a bare list."
            )

        try:
            return PipelineConfig.model_validate(raw)
        except ValidationError as exc:
            errors: list[ValidationErrorDetail] = [
                {
                    "field": _loc_to_dotpath(error["loc"]),
                    "message": error["msg"],
                }
                for error in exc.errors()
            ]
            n = len(errors)
            raise ConfigValidationError(
                errors=errors,
                message=f"Pipeline config has {n} validation error{'s' if n != 1 else ''}",
            ) from exc
