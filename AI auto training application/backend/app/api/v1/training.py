"""Training endpoints (Phases 5 + 8 + 10)."""
from __future__ import annotations

import shutil
import uuid
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser, current_user
from app.db import get_session
from app.models.dataset import Dataset, DatasetVersion
from app.models.enums import ArtifactKind, JobStatus
from app.models.training import TrainingArtifact, TrainingJob
from app.realtime.sse import event_stream
from app.schemas.envelope import Envelope, ok
from app.schemas.inference import ExportRequest, ExportResult, PredictionResult
from app.schemas.training import (
    CloneConfigOut,
    TrainingArtifactOut,
    TrainingArtifactsOut,
    TrainingHistoryItem,
    TrainingHistoryOut,
    TrainingJobListOut,
    TrainingJobOut,
    TrainingMetricOut,
    TrainingMetricsOut,
    TrainingStartRequest,
)
from app.services import projects as project_svc
from app.services.inference import predictor as inference
from app.services.training import runner as training_runner
from app.services.training import stop as stop_svc
from app.storage import get_storage

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
        session,
        project=project,
        dataset_version=version,
        params=payload.params,
        preset_source=payload.preset_source,
        override_blockers=payload.override_blockers,
        recommendation_snapshot=payload.recommendation_snapshot,
    )
    await session.commit()

    job_id = tj.id

    async def _entry() -> None:
        await training_runner.run_training_job(job_id)

    background_tasks.add_task(_entry)
    return ok(TrainingJobOut.model_validate(tj))


# ---------- list / get ----------
@router.get("/projects/{project_id}/training-jobs",
            response_model=Envelope[TrainingJobListOut])
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


@router.get("/training-jobs/{training_job_id}",
            response_model=Envelope[TrainingJobOut])
async def get_training_job(
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
    return ok(TrainingJobOut.model_validate(tj))


# ---------- metrics ----------
@router.get("/training-jobs/{training_job_id}/metrics",
            response_model=Envelope[TrainingMetricsOut])
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
@router.get("/training-jobs/{training_job_id}/artifacts",
            response_model=Envelope[TrainingArtifactsOut])
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
    return ok(TrainingArtifactsOut(items=[TrainingArtifactOut.model_validate(a) for a in rows]))


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
    p = urlparse(art.storage_uri)
    if p.scheme != "file":
        raise HTTPException(501, detail={"code": "REMOTE_STORAGE_NOT_SUPPORTED",
                                         "message": "Only local storage downloads supported in v1.",
                                         "details": {}})
    return FileResponse(p.path, filename=art.name)


# ---------- stop ----------
@router.post("/training-jobs/{training_job_id}/stop",
             response_model=Envelope[TrainingJobOut])
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
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------- Phase 8: history + clone-as-config ----------
@router.get("/projects/{project_id}/training-history",
            response_model=Envelope[TrainingHistoryOut])
async def training_history(
    project_id: uuid.UUID,
    status_filter: JobStatus | None = None,
    limit: int = 50,
    offset: int = 0,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[TrainingHistoryOut]:
    await project_svc.get_project(session, project_id, user_id=uuid.UUID(user.id))
    base = select(TrainingJob).where(TrainingJob.project_id == project_id)
    if status_filter is not None:
        base = base.where(TrainingJob.status == status_filter)
    total = (await session.execute(
        select(func.count()).select_from(base.subquery())
    )).scalar_one()
    rows = list((await session.execute(
        base.order_by(desc(TrainingJob.created_at)).limit(limit).offset(offset)
    )).scalars())
    return ok(TrainingHistoryOut(
        items=[TrainingHistoryItem.model_validate(r) for r in rows],
        total=total,
    ))


@router.get("/training-jobs/{training_job_id}/clone-as-config",
            response_model=Envelope[CloneConfigOut])
async def clone_as_config(
    training_job_id: uuid.UUID,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[CloneConfigOut]:
    tj = await session.get(TrainingJob, training_job_id)
    if tj is None:
        raise HTTPException(404, detail={"code": "TRAINING_JOB_NOT_FOUND",
                                         "message": "Training job not found.",
                                         "details": {}})
    await project_svc.get_project(session, tj.project_id, user_id=uuid.UUID(user.id))
    return ok(CloneConfigOut(
        dataset_version_id=tj.dataset_version_id,
        params=dict(tj.params),
        preset_source="manual",
        override_blockers=tj.override_blockers,
    ))


# ---------- Phase 10: inference + export ----------
@router.post("/training-jobs/{training_job_id}/predict",
             response_model=Envelope[PredictionResult])
async def predict(
    training_job_id: uuid.UUID,
    file: UploadFile = File(...),
    conf: float = 0.25,
    iou: float = 0.7,
    imgsz: int | None = None,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[PredictionResult]:
    tj = await session.get(TrainingJob, training_job_id)
    if tj is None:
        raise HTTPException(404, detail={"code": "TRAINING_JOB_NOT_FOUND",
                                         "message": "Training job not found.",
                                         "details": {}})
    await project_svc.get_project(session, tj.project_id, user_id=uuid.UUID(user.id))
    artifacts = list((await session.execute(
        select(TrainingArtifact)
        .where(TrainingArtifact.training_job_id == training_job_id)
        .order_by(asc(TrainingArtifact.created_at))
    )).scalars())
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(400, detail={"code": "EMPTY_FILE",
                                         "message": "Empty upload.",
                                         "details": {}})
    import asyncio as _asyncio
    result = await _asyncio.to_thread(
        inference.predict_image, tj, artifacts, image_bytes,
        conf=conf, iou=iou, imgsz=imgsz,
    )
    return ok(PredictionResult.model_validate(result))


@router.post("/training-jobs/{training_job_id}/export",
             response_model=Envelope[ExportResult])
async def export_model_endpoint(
    training_job_id: uuid.UUID,
    payload: ExportRequest,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[ExportResult]:
    tj = await session.get(TrainingJob, training_job_id)
    if tj is None:
        raise HTTPException(404, detail={"code": "TRAINING_JOB_NOT_FOUND",
                                         "message": "Training job not found.",
                                         "details": {}})
    await project_svc.get_project(session, tj.project_id, user_id=uuid.UUID(user.id))
    artifacts = list((await session.execute(
        select(TrainingArtifact)
        .where(TrainingArtifact.training_job_id == training_job_id)
        .order_by(asc(TrainingArtifact.created_at))
    )).scalars())
    import asyncio as _asyncio
    exported_path = await _asyncio.to_thread(
        inference.export_model, tj, artifacts, format=payload.format,
    )
    storage = get_storage()
    target_key = f"runs/{training_job_id}/exports/{exported_path.name}"
    target = storage.local_path(target_key)
    if target is None:
        raise HTTPException(500, detail={"code": "STORAGE_NOT_LOCAL",
                                         "message": "Export currently requires local storage.",
                                         "details": {}})
    target.parent.mkdir(parents=True, exist_ok=True)
    if exported_path.resolve() != target.resolve():
        shutil.copyfile(exported_path, target)
    art = TrainingArtifact(
        training_job_id=tj.id,
        name=exported_path.name,
        kind=ArtifactKind.EXPORT,
        storage_uri=storage.to_uri(target_key),
        size_bytes=target.stat().st_size if target.exists() else None,
    )
    session.add(art)
    await session.flush()
    return ok(ExportResult(
        artifact_id=art.id,
        name=art.name,
        storage_uri=art.storage_uri,
        size_bytes=art.size_bytes,
    ))
