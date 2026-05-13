from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class RecommendationItem(BaseModel):
    code: str
    severity: str   # blocker | warning | info
    message: str
    fix: str | None = None
    meta: dict[str, Any] = {}


class AnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_version_id: uuid.UUID
    health_score: Decimal | None
    findings: dict[str, Any]
    recommendations: list[RecommendationItem]
    ready_for_training: bool
    created_at: datetime


class RecommendationsOut(BaseModel):
    items: list[RecommendationItem]
    ready_for_training: bool
    health_score: Decimal | None


class TrainingRecommendationRequest(BaseModel):
    """Optional overrides — body is allowed to be empty."""
    gpu_mem_gb: float | None = None


class TrainingRecommendationOut(BaseModel):
    model_family: str
    task_type: str
    params: dict[str, Any]
    reasons: dict[str, str]
    assumptions: dict[str, Any]
