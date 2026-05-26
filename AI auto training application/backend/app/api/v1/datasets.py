"""Datasets REST endpoints (Phase 2 + Phase 3 + Phase 3.5 export)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import CurrentUser, current_user
from app.db import get_session
from app.jobs.runner import create_job, schedule
from app.models.dataset import Dataset, DatasetVersion
from app.models.enums import JobKind
from app.schemas.dataset import (
    DatasetConvertRequest,
    DatasetCreate,
    DatasetDetailOut,
    DatasetListOut,
    DatasetOut,
    DatasetUpdate,
    DatasetVersionOut,
)
from app.schemas.envelope import Envelope, ok
from app.schemas.job import JobAcceptedOut
from app.services import projects as project_svc
from app.services.datasets import convert as convert_svc
from app.services.datasets import export as export_svc
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
        treat_unlabeled_as_background=payload.treat_unlabeled_as_background,
        actor=user.email,
    )
    return ok(DatasetOut.model_validate(ds))


@router.patch(
    "/datasets/{dataset_id}",
    response_model=Envelope[DatasetOut],
)
async def patch_dataset(
    dataset_id: uuid.UUID,
    payload: DatasetUpdate,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[DatasetOut]:
    ds = await ingest_svc.get_dataset(session, dataset_id)
    await project_svc.get_project(session, ds.project_id, user_id=uuid.UUID(user.id))
    updated = await ingest_svc.update_dataset(
        session,
        dataset_id=dataset_id,
        treat_unlabeled_as_background=payload.treat_unlabeled_as_background,
        actor=user.email,
    )
    await session.commit()
    return ok(DatasetOut.model_validate(updated))


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
            # When omitted (None), the convert runner falls back to the
            # dataset row's stored treat_unlabeled_as_background preference.
            "treat_unlabeled_as_background": payload.treat_unlabeled_as_background,
        },
    )
    await session.commit()
    schedule(background_tasks, job, convert_svc.run_convert)
    return ok(JobAcceptedOut(job_id=job.id))


# ---- export (zip of converted version) ----
@router.get(
    "/datasets/versions/{version_id}/export",
    # Streams a binary zip. We bypass the JSON envelope here so the response
    # is directly downloadable from the browser.
    response_model=None,
)
async def export_dataset_version(
    version_id: uuid.UUID,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Download a converted dataset version as a ZIP.

    The archive mirrors the on-disk converted folder exactly:
        images/{train,val,test}/<name>.<ext>
        labels/{train,val,test}/<name>.txt
        data.yaml
    so the download is drop-in usable by Ultralytics YOLO.

    Raw (uningested) versions cannot be exported -- convert first.
    """
    version = await session.get(DatasetVersion, version_id)
    if version is None:
        raise AppError("DATASET_VERSION_NOT_FOUND", "Dataset version not found.", 404)

    ds = await ingest_svc.get_dataset(session, version.dataset_id)
    await project_svc.get_project(session, ds.project_id, user_id=uuid.UUID(user.id))

    if version.format == "raw":
        raise AppError(
            "EXPORT_RAW_NOT_SUPPORTED",
            "Raw versions can't be exported. Convert to a YOLO format first.",
            status_code=400,
            details={"format": version.format},
        )

    root = export_svc._uri_to_local(version.storage_uri)
    filename = export_svc.suggested_filename(ds, version)

    return StreamingResponse(
        export_svc.stream_directory_as_zip(root),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Dataset-Version": str(version.id),
            "X-Dataset-Format": version.format,
        },
    )
