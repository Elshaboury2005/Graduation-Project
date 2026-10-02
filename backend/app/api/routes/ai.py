"""Optional, explainable AI-assisted reliability analysis API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.ai import ReliabilityAnalyzer
from app.core.config import get_settings

router = APIRouter(tags=["ai"])


class ReliabilityAnalysisRequest(BaseModel):
    """Historical metrics and optional log excerpts to analyse."""

    observations: list[dict[str, float]] = Field(min_length=1, max_length=10_000)
    logs: list[str] = Field(default_factory=list, max_length=1_000)


@router.post("/api/ai/reliability-analysis")
async def analyze_reliability(request: ReliabilityAnalysisRequest) -> dict[str, Any]:
    """Return explainable anomaly signals, risk indicators, and recommendations."""
    settings = get_settings()
    if not settings.AI_ANALYSIS_ENABLED:
        raise HTTPException(status_code=503, detail="AI reliability analysis is disabled.")
    try:
        return ReliabilityAnalyzer(settings.AI_ANOMALY_CONTAMINATION).analyze(
            request.observations, request.logs
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
