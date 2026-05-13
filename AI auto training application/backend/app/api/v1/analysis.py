"""Analysis + recommendations endpoints (Phase 4)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser, current_user
from app.db import get_session
from app.jobs.runner import create_job, schedule
from app.models.dataset import Dataset, DatasetVersion
from app.models.enums import JobKind
from app.models.project import Project
from app.schemas.analysis import (
    AnalysisOut,
    RecommendationItem,
    RecommendationsOut,
    TrainingRecommendationOut,
    TrainingRecommendationRequest,
)
from app.schemas.envelope import Envelope, ok
from app.schemas.job import JobAcceptedOut
from app.services import projects as project_svc
from app.services.analysis import runner as analysis_runner
from app.services.recommend import training as training_rec

router = APIRouter(tags=["analysis"])


async def _load_version_authz(
    session: AsyncSession, dataset_version_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[DatasetVersion, Dataset]:
    version = await session.get(DatasetVersion, dataset_version_id)
    if version is None:
        raise HTTPException(404, detail={
            "code": "DATASET_VERSION_NOT_FOUND",
            "message": "Dataset version not found.",
            "details": {},
        })
    ds = await session.get(Dataset, version.dataset_id)
    if ds is None or ds.deleted_at is not None:
        raise HTTPException(404, detail={
            "code": "DATASET_NOT_FOUND", "message": "Dataset not found.", "details": {},
        })
    await project_svc.get_project(session, ds.project_id, user_id=user_id)
    return version, ds


@router.post(
    "/dataset-versions/{dataset_version_id}/analyze",
    response_model=Envelope[JobAcceptedOut],
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_analysis(
    dataset_version_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[JobAcceptedOut]:
    version, ds = await _load_version_authz(session, dataset_version_id, uuid.UUID(user.id))
    job = await create_job(
        session,
        kind=JobKind.ANALYZE,
        project_id=ds.project_id,
        dataset_id=ds.id,
        payload={
            "project_id": str(ds.project_id),
            "dataset_id": str(ds.id),
            "dataset_version_id": str(dataset_version_id),
        },
    )
    await session.commit()
    schedule(background_tasks, job, analysis_runner.run_analysis)
    return ok(JobAcceptedOut(job_id=job.id))


@router.get(
    "/dataset-versions/{dataset_version_id}/analysis",
    response_model=Envelope[AnalysisOut],
)
async def get_latest_analysis(
    dataset_version_id: uuid.UUID,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[AnalysisOut]:
    await _load_version_authz(session, dataset_version_id, uuid.UUID(user.id))
    analysis = await analysis_runner.get_latest_for_version(session, dataset_version_id)
    if analysis is None:
        raise HTTPException(404, detail={
            "code": "NO_ANALYSIS",
            "message": "No analysis has been run on this version yet. POST /analyze first.",
            "details": {},
        })
    return ok(AnalysisOut.model_validate(analysis))


@router.get(
    "/dataset-versions/{dataset_version_id}/recommendations",
    response_model=Envelope[RecommendationsOut],
)
async def get_recommendations(
    dataset_version_id: uuid.UUID,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[RecommendationsOut]:
    await _load_version_authz(session, dataset_version_id, uuid.UUID(user.id))
    analysis = await analysis_runner.get_latest_for_version(session, dataset_version_id)
    if analysis is None:
        raise HTTPException(404, detail={
            "code": "NO_ANALYSIS",
            "message": "No analysis has been run on this version yet.",
            "details": {},
        })
    return ok(RecommendationsOut(
        items=[RecommendationItem(**r) for r in analysis.recommendations],
        ready_for_training=analysis.ready_for_training,
        health_score=analysis.health_score,
    ))


@router.post(
    "/dataset-versions/{dataset_version_id}/training-recommendation",
    response_model=Envelope[TrainingRecommendationOut],
)
async def get_training_recommendation(
    dataset_version_id: uuid.UUID,
    payload: TrainingRecommendationRequest | None = None,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[TrainingRecommendationOut]:
    version, ds = await _load_version_authz(session, dataset_version_id, uuid.UUID(user.id))
    project = await session.get(Project, ds.project_id)
    if project is None:
        raise HTTPException(404, detail={
            "code": "PROJECT_NOT_FOUND", "message": "Project not found.", "details": {},
        })

    analysis = await analysis_runner.get_latest_for_version(session, dataset_version_id)
    findings = analysis.findings.get("checks", {}) if analysis else {
        "counts": {"image_count": version.num_images or 0},
        "resolution": {},
    }

    payload = payload or TrainingRecommendationRequest()
    rec = training_rec.recommend(
        model_family=project.model_family,
        task_type=project.task_type,
        findings=findings,
        gpu_mem_gb=payload.gpu_mem_gb,
    )
    return ok(TrainingRecommendationOut(**rec))
