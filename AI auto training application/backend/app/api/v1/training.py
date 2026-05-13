"""Training endpoints (Phase 5)."""
from __future__ import annotations

import asyncio
import uuid
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser, current_user
from app.db import get_session
from app.models.dataset import Dataset, DatasetVersion
from app.models.enums import JobStatus
from app.models.training import TrainingArtifact, TrainingJob
from app.realtime.sse import event_stream
from app.schemas.envelope import Envelope, ok
from app.schemas.training import (
    TrainingArtifactOut,
    TrainingArtifactsOut,
    TrainingJobListOut,
    TrainingJobOut,
    TrainingMetricOut,
    TrainingMetricsOut,
    TrainingStartRequest,
)
from app.services import projects as project_svc
from app.services.training import runner as training_runner
from app.services.training import stop as stop_svc

router = APIRouter(tags=["training"])


# ---------- start ----------
@router.post(
    "/projects/{project_id}/training-jobs",
    response_model=Envelope[TrainingJobOut],
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_training(
    project_id: uuid.UUID,
    payload: TrainingStartRequest,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[TrainingJobOut]:
    project = await project_svc.get_project(session, project_id, user_id=uuid.UUID(user.id))
    version = await session.get(DatasetVersion, payload.dataset_version_id)
    if version is None:
        raise HTTPException(404, detail={
            "code": "DATASET_VERSION_NOT_FOUND",
            "message": "Dataset version not found.",
            "details": {},
        })
    ds = await session.get(Dataset, version.dataset_id)
    if ds is None or ds.project_id != project_id:
        raise HTTPException(400, detail={
            "code": "DATASET_NOT_IN_PROJECT",
            "message": "Dataset version does not belong to this project.",
            "details": {},
        })

    tj = await training_runner.start_training(
        session, project=project, dataset_version=version, params=payload.params,
    )
    await session.commit()

    # Schedule the background runner (opens its own session)
    job_id = tj.id

    async def _entry() -> None:
        await training_runner.run_training_job(job_id)

    background_tasks.add_task(_entry)
    return ok(TrainingJobOut.model_validate(tj))


# ---------- list / get ----------
@router.get(
    "/projects/{project_id}/training-jobs",
    response_model=Envelope[TrainingJobListOut],
)
async def list_training_jobs(
    project_id: uuid.UUID,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[TrainingJobListOut]:
    await project_svc.get_project(session, project_id, user_id=uuid.UUID(user.id))
    stmt = (
        select(TrainingJob)
        .where(TrainingJob.project_id == project_id)
        .order_by(desc(TrainingJob.created_at))
    )
    items = list((await session.execute(stmt)).scalars())
    return ok(TrainingJobListOut(
        items=[TrainingJobOut.model_validate(t) for t in items],
        total=len(items),
    ))


@router.get(
    "/training-jobs/{training_job_id}",
    response_model=Envelope[TrainingJobOut],
)
async def get_training_job(
    training_job_id: uuid.UUID,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[TrainingJobOut]:
    tj = await session.get(TrainingJob, training_job_id)
    if tj is None:
        raise HTTPException(404, detail={
            "code": "TRAINING_JOB_NOT_FOUND",
            "message": "Training job not found.",
            "details": {},
        })
    await project_svc.get_project(session, tj.project_id, user_id=uuid.UUID(user.id))
    return ok(TrainingJobOut.model_validate(tj))


# ---------- metrics ----------
@router.get(
    "/training-jobs/{training_job_id}/metrics",
    response_model=Envelope[TrainingMetricsOut],
)
async def get_metrics(
    training_job_id: uuid.UUID,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[TrainingMetricsOut]:
    tj = await session.get(TrainingJob, training_job_id)
    if tj is None:
        raise HTTPException(404, detail={"code": "TRAINING_JOB_NOT_FOUND",
                                         "message": "Training job not found.",
                                         "details": {}})
    await project_svc.get_project(session, tj.project_id, user_id=uuid.UUID(user.id))
    rows = await training_runner.list_metrics(session, training_job_id)
    return ok(TrainingMetricsOut(items=[TrainingMetricOut.model_validate(m) for m in rows]))


# ---------- artifacts ----------
@router.get(
    "/training-jobs/{training_job_id}/artifacts",
    response_model=Envelope[TrainingArtifactsOut],
)
async def list_artifacts(
    training_job_id: uuid.UUID,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[TrainingArtifactsOut]:
    tj = await session.get(TrainingJob, training_job_id)
    if tj is None:
        raise HTTPException(404, detail={"code": "TRAINING_JOB_NOT_FOUND",
                                         "message": "Training job not found.",
                                         "details": {}})
    await project_svc.get_project(session, tj.project_id, user_id=uuid.UUID(user.id))
    rows = await training_runner.list_artifacts(session, training_job_id)
    return ok(TrainingArtifactsOut(
        items=[TrainingArtifactOut.model_validate(a) for a in rows],
    ))


@router.get("/training-jobs/{training_job_id}/artifacts/{artifact_id}/download")
async def download_artifact(
    training_job_id: uuid.UUID,
    artifact_id: uuid.UUID,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    tj = await session.get(TrainingJob, training_job_id)
    if tj is None:
        raise HTTPException(404, detail={"code": "TRAINING_JOB_NOT_FOUND",
                                         "message": "Training job not found.",
                                         "details": {}})
    await project_svc.get_project(session, tj.project_id, user_id=uuid.UUID(user.id))
    art = await session.get(TrainingArtifact, artifact_id)
    if art is None or art.training_job_id != training_job_id:
        raise HTTPException(404, detail={"code": "ARTIFACT_NOT_FOUND",
                                         "message": "Artifact not found.",
                                         "details": {}})
    # Resolve file:// URI to a path.
    p = urlparse(art.storage_uri)
    if p.scheme != "file":
        raise HTTPException(501, detail={"code": "REMOTE_STORAGE_NOT_SUPPORTED",
                                         "message": "Only local storage downloads supported in v1.",
                                         "details": {}})
    return FileResponse(p.path, filename=art.name)


# ---------- stop ----------
@router.post(
    "/training-jobs/{training_job_id}/stop",
    response_model=Envelope[TrainingJobOut],
)
async def stop_training(
    training_job_id: uuid.UUID,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[TrainingJobOut]:
    tj = await session.get(TrainingJob, training_job_id)
    if tj is None:
        raise HTTPException(404, detail={"code": "TRAINING_JOB_NOT_FOUND",
                                         "message": "Training job not found.",
                                         "details": {}})
    await project_svc.get_project(session, tj.project_id, user_id=uuid.UUID(user.id))
    if tj.status not in (JobStatus.PENDING, JobStatus.RUNNING):
        raise HTTPException(409, detail={"code": "TRAINING_NOT_RUNNING",
                                         "message": f"Job is {tj.status}.",
                                         "details": {}})
    stop_svc.request_stop(training_job_id)
    tj.message = "Stop requested — will halt after current epoch."
    await session.commit()
    return ok(TrainingJobOut.model_validate(tj))


# ---------- SSE ----------
@router.get("/sse/training/{training_job_id}")
async def sse_training(
    training_job_id: uuid.UUID,
    # Browsers can't send custom headers on EventSource; allow a token query
    # param. v1 still validates via the standard Authorization header when
    # called from curl / smoke tests; the UI passes ?token=… instead.
    token: str | None = None,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    tj = await session.get(TrainingJob, training_job_id)
    if tj is None:
        raise HTTPException(404, detail={"code": "TRAINING_JOB_NOT_FOUND",
                                         "message": "Training job not found.",
                                         "details": {}})
    await project_svc.get_project(session, tj.project_id, user_id=uuid.UUID(user.id))

    async def _gen():
        async for chunk in event_stream(f"training:{training_job_id}"):
            yield chunk

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # tell nginx not to buffer
        },
    )
