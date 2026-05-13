"""Datasets REST endpoints (Phase 2 + Phase 3)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser, current_user
from app.db import get_session
from app.jobs.runner import create_job, schedule
from app.models.dataset import Dataset
from app.models.enums import JobKind
from app.schemas.dataset import (
    DatasetConvertRequest,
    DatasetCreate,
    DatasetDetailOut,
    DatasetListOut,
    DatasetOut,
    DatasetVersionOut,
)
from app.schemas.envelope import Envelope, ok
from app.schemas.job import JobAcceptedOut
from app.services import projects as project_svc
from app.services.datasets import convert as convert_svc
from app.services.datasets import ingest as ingest_svc

router = APIRouter(tags=["datasets"])


# ---- create / list / get ----
@router.post(
    "/projects/{project_id}/datasets",
    response_model=Envelope[DatasetOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_dataset(
    project_id: uuid.UUID,
    payload: DatasetCreate,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[DatasetOut]:
    await project_svc.get_project(session, project_id, user_id=uuid.UUID(user.id))
    ds = await ingest_svc.create_dataset(
        session,
        project_id=project_id,
        name=payload.name,
        source=payload.source,
        actor=user.email,
    )
    return ok(DatasetOut.model_validate(ds))


@router.get(
    "/projects/{project_id}/datasets",
    response_model=Envelope[DatasetListOut],
)
async def list_datasets(
    project_id: uuid.UUID,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[DatasetListOut]:
    await project_svc.get_project(session, project_id, user_id=uuid.UUID(user.id))
    stmt = (
        select(Dataset)
        .where(Dataset.project_id == project_id, Dataset.deleted_at.is_(None))
        .order_by(Dataset.created_at.desc())
    )
    items = list((await session.execute(stmt)).scalars())
    return ok(DatasetListOut(
        items=[DatasetOut.model_validate(d) for d in items],
        total=len(items),
    ))


@router.get(
    "/datasets/{dataset_id}",
    response_model=Envelope[DatasetDetailOut],
)
async def get_dataset_detail(
    dataset_id: uuid.UUID,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[DatasetDetailOut]:
    ds = await ingest_svc.get_dataset(session, dataset_id)
    await project_svc.get_project(session, ds.project_id, user_id=uuid.UUID(user.id))
    versions = await ingest_svc.list_versions(session, dataset_id)
    return ok(DatasetDetailOut(
        dataset=DatasetOut.model_validate(ds),
        versions=[DatasetVersionOut.model_validate(v) for v in versions],
    ))


# ---- upload (zip) ----
@router.post(
    "/datasets/{dataset_id}/upload-zip",
    response_model=Envelope[JobAcceptedOut],
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_zip(
    dataset_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[JobAcceptedOut]:
    ds = await ingest_svc.get_dataset(session, dataset_id)
    await project_svc.get_project(session, ds.project_id, user_id=uuid.UUID(user.id))

    upload_id, zip_key = await ingest_svc.stage_uploaded_zip(
        project_id=ds.project_id, dataset_id=dataset_id, upload=file,
    )

    job = await create_job(
        session,
        kind=JobKind.INGEST_ZIP,
        project_id=ds.project_id,
        dataset_id=dataset_id,
        payload={
            "project_id": str(ds.project_id),
            "dataset_id": str(dataset_id),
            "upload_id": str(upload_id),
            "zip_key": zip_key,
        },
    )
    await session.commit()
    schedule(background_tasks, job, ingest_svc.run_ingest_zip)
    return ok(JobAcceptedOut(job_id=job.id))


# ---- upload (loose files) ----
@router.post(
    "/datasets/{dataset_id}/upload-files",
    response_model=Envelope[JobAcceptedOut],
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_files(
    dataset_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[JobAcceptedOut]:
    ds = await ingest_svc.get_dataset(session, dataset_id)
    await project_svc.get_project(session, ds.project_id, user_id=uuid.UUID(user.id))

    _, base_key = await ingest_svc.stage_uploaded_files(
        project_id=ds.project_id, dataset_id=dataset_id, uploads=files,
    )

    job = await create_job(
        session,
        kind=JobKind.INGEST_FILES,
        project_id=ds.project_id,
        dataset_id=dataset_id,
        payload={
            "project_id": str(ds.project_id),
            "dataset_id": str(dataset_id),
            "base_key": base_key,
        },
    )
    await session.commit()
    schedule(background_tasks, job, ingest_svc.run_ingest_files)
    return ok(JobAcceptedOut(job_id=job.id))


# ---- convert (raw -> yolo-det/seg/cls) ----
@router.post(
    "/datasets/{dataset_id}/convert",
    response_model=Envelope[JobAcceptedOut],
    status_code=status.HTTP_202_ACCEPTED,
)
async def convert_dataset(
    dataset_id: uuid.UUID,
    payload: DatasetConvertRequest,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[JobAcceptedOut]:
    ds = await ingest_svc.get_dataset(session, dataset_id)
    await project_svc.get_project(session, ds.project_id, user_id=uuid.UUID(user.id))

    ratios = payload.ratios.model_dump() if payload.ratios else None

    job = await create_job(
        session,
        kind=JobKind.CONVERT,
        project_id=ds.project_id,
        dataset_id=dataset_id,
        payload={
            "project_id": str(ds.project_id),
            "dataset_id": str(dataset_id),
            "format": payload.format,
            "ratios": ratios,
            "classes_override": payload.classes_override,
        },
    )
    await session.commit()
    schedule(background_tasks, job, convert_svc.run_convert)
    return ok(JobAcceptedOut(job_id=job.id))
