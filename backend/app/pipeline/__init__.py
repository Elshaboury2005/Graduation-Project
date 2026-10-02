"""
app/pipeline/__init__.py
------------------------
Package marker for the pipeline configuration engine sub-package.

This package implements the full lifecycle of a pipeline config:

  YAML text  ──►  PipelineConfigParser  ──►  PipelineConfig (Pydantic)
                                          ──►  PipelineBusinessValidator
                                          ──►  structured error list
"""
