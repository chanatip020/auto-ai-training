"""Dataset ingestion: ZIP upload and manual file upload.

Two stages:
  1. Synchronous (in the request handler): write incoming bytes to
     {STORAGE_ROOT}/raw/{project_id}/{dataset_id}/{upload_id}/ — fast, no
     parsing yet. Returns a job_id.
  2. Background task: extract the ZIP, detect layout, count files, write a
     dataset_versions row, transition the project status. Updates job
     progress along the way.
"""
from __future__ import annotations

import asyncio
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.dataset import Dataset, DatasetVersion
from app.models.enums import DatasetSource, JobKind, JobStatus, ProjectStatus
from app.models.job import Job
from app.models.project import Project
from app.services import audit
from app.services.datasets.detect import detect
from app.storage import get_storage


# --- key helpers ---
def _raw_dir(project_id: uuid.UUID, dataset_id: uuid.UUID, upload_id: uuid.UUID) -> str:
    return f"raw/{project_id}/{dataset_id}/{upload_id}"


def _zip_key(project_id: uuid.UUID, dataset_id: uuid.UUID, upload_id: uuid.UUID) -> str:
    return f"{_raw_dir(project_id, dataset_id, upload_id)}/upload.zip"


def _extracted_dir(project_id: uuid.UUID, dataset_id: uuid.UUID, upload_id: uuid.UUID) -> str:
    return f"{_raw_dir(project_id, dataset_id, upload_id)}/extracted"


# --- dataset CRUD ---
async def create_dataset(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    name: str,
    source: DatasetSource = DatasetSource.UPLOAD,
    actor: str | None = None,
) -> Dataset:
    ds = Dataset(project_id=project_id, name=name, source=source)
    session.add(ds)
    await session.flush()
    await audit.record(
        session,
        project_id=project_id,
        event="dataset.created",
        payload={"dataset_id": str(ds.id), "name": name, "source": source.value},
        actor=actor,
    )
    return ds


async def get_dataset(session: AsyncSession, dataset_id: uuid.UUID) -> Dataset:
    stmt = select(Dataset).where(Dataset.id == dataset_id, Dataset.deleted_at.is_(None))
    ds = (await session.execute(stmt)).scalar_one_or_none()
    if ds is None:
        raise AppError("DATASET_NOT_FOUND", "Dataset not found.", status_code=404)
    return ds


async def list_versions(session: AsyncSession, dataset_id: uuid.UUID) -> list[DatasetVersion]:
    stmt = (
        select(DatasetVersion)
        .where(DatasetVersion.dataset_id == dataset_id)
        .order_by(DatasetVersion.version.desc())
    )
    return list((await session.execute(stmt)).scalars())


# --- upload (sync part) ---
async def stage_uploaded_zip(
    *,
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    upload: UploadFile,
) -> tuple[uuid.UUID, str]:
    """Stream the incoming ZIP to storage; return (upload_id, storage_key)."""
    if upload.filename and not upload.filename.lower().endswith(".zip"):
        raise AppError(
            "INVALID_UPLOAD",
            "Only .zip files are accepted by this endpoint.",
            status_code=400,
            details={"filename": upload.filename},
        )

    upload_id = uuid.uuid4()
    key = _zip_key(project_id, dataset_id, upload_id)
    storage = get_storage()

    # Stream to a local temp file (avoids loading entire ZIP into memory),
    # then hand off to storage.put_file. For LocalStorage this is a single
    # copy; for S3 it'd be a streaming multipart upload.
    import tempfile
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    try:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            tmp.write(chunk)
        tmp.flush()
        tmp.close()
        await storage.put_file(key, tmp.name)
    finally:
        try:
            Path(tmp.name).unlink(missing_ok=True)
        except Exception:
            pass

    return upload_id, key


async def stage_uploaded_files(
    *,
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    uploads: list[UploadFile],
) -> tuple[uuid.UUID, str]:
    """Write loose files into raw/.../extracted/ — skips the zip step."""
    upload_id = uuid.uuid4()
    base_key = _extracted_dir(project_id, dataset_id, upload_id)
    storage = get_storage()

    for up in uploads:
        if not up.filename:
            continue
        # Normalize the relative path so it cannot escape the upload dir
        rel = Path(up.filename).as_posix().lstrip("/").replace("..", "_")
        data = await up.read()
        await storage.put_bytes(f"{base_key}/{rel}", data)

    # We don't have a zip file in this path; mark it by returning the
    # extracted dir as the 'key'. The background task will detect this.
    return upload_id, base_key


# --- background extraction + summary ---
async def run_ingest_zip(session: AsyncSession, job: Job) -> None:
    """Background handler — extract ZIP, detect, write dataset_version."""
    payload = job.payload or {}
    project_id = uuid.UUID(payload["project_id"])
    dataset_id = uuid.UUID(payload["dataset_id"])
    upload_id = uuid.UUID(payload["upload_id"])
    zip_key = payload["zip_key"]

    storage = get_storage()
    zip_path = storage.local_path(zip_key)
    if zip_path is None or not zip_path.exists():
        raise AppError("ZIP_MISSING", "Uploaded ZIP could not be located in storage.", 500)

    job.status = JobStatus.RUNNING
    job.message = "Extracting ZIP"
    job.progress = 10
    await session.commit()

    extracted_key = _extracted_dir(project_id, dataset_id, upload_id)
    extracted_dir = storage.local_path(extracted_key)
    if extracted_dir is None:
        raise AppError("STORAGE_NOT_LOCAL", "Background ingest requires a local storage path.", 500)
    extracted_dir.mkdir(parents=True, exist_ok=True)

    def _extract() -> None:
        with zipfile.ZipFile(zip_path) as z:
            # Guard against zip-slip: reject any entry that resolves outside.
            for member in z.infolist():
                target = (extracted_dir / member.filename).resolve()
                if not str(target).startswith(str(extracted_dir.resolve())):
                    raise AppError(
                        "ZIP_SLIP",
                        f"ZIP entry escapes target dir: {member.filename!r}",
                        status_code=400,
                    )
            z.extractall(extracted_dir)

    await asyncio.to_thread(_extract)

    job.message = "Scanning files"
    job.progress = 60
    await session.commit()

    report = await asyncio.to_thread(detect, extracted_dir)

    job.message = "Recording dataset version"
    job.progress = 85
    await session.commit()

    # Next monotonic version number for this dataset
    next_version_stmt = select(func.coalesce(func.max(DatasetVersion.version), 0) + 1).where(
        DatasetVersion.dataset_id == dataset_id
    )
    next_version = (await session.execute(next_version_stmt)).scalar_one()

    version = DatasetVersion(
        dataset_id=dataset_id,
        version=next_version,
        format="raw",
        storage_uri=storage.to_uri(extracted_key),
        num_images=report.image_count,
        num_labels=report.label_count,
        num_classes=len(report.classes_hint) or None,
        classes=report.classes_hint or None,
        summary={
            "detected_format": report.detected_format,
            "notes": report.notes,
        },
    )
    session.add(version)
    await session.flush()

    # Audit + project status auto-transition (created -> dataset_uploaded)
    await audit.record(
        session,
        project_id=project_id,
        event="dataset.uploaded",
        payload={
            "dataset_id": str(dataset_id),
            "version_id": str(version.id),
            "version": next_version,
            "detected_format": report.detected_format,
            "image_count": report.image_count,
            "label_count": report.label_count,
        },
        actor="system",
    )

    project = await session.get(Project, project_id)
    if project and ProjectStatus(str(project.status)) == ProjectStatus.CREATED:
        project.status = ProjectStatus.DATASET_UPLOADED
        project.updated_at = datetime.now(timezone.utc)
        await audit.record(
            session,
            project_id=project_id,
            event="project.status_changed",
            payload={"from": "created", "to": "dataset_uploaded"},
            actor="system",
        )

    job.message = f"Done — detected {report.detected_format}, {report.image_count} images"
    job.progress = 100
    job.status = JobStatus.SUCCEEDED
    await session.commit()
    logger.info(
        "Ingest done: dataset={} version={} format={} images={} labels={}",
        dataset_id, next_version, report.detected_format,
        report.image_count, report.label_count,
    )


async def run_ingest_files(session: AsyncSession, job: Job) -> None:
    """Same as run_ingest_zip, but skips the extract step."""
    payload = job.payload or {}
    project_id = uuid.UUID(payload["project_id"])
    dataset_id = uuid.UUID(payload["dataset_id"])
    base_key = payload["base_key"]

    storage = get_storage()
    extracted_dir = storage.local_path(base_key)
    if extracted_dir is None:
        raise AppError("STORAGE_NOT_LOCAL", "Background ingest requires a local storage path.", 500)

    job.status = JobStatus.RUNNING
    job.message = "Scanning files"
    job.progress = 60
    await session.commit()

    report = await asyncio.to_thread(detect, extracted_dir)

    next_version_stmt = select(func.coalesce(func.max(DatasetVersion.version), 0) + 1).where(
        DatasetVersion.dataset_id == dataset_id
    )
    next_version = (await session.execute(next_version_stmt)).scalar_one()

    version = DatasetVersion(
        dataset_id=dataset_id,
        version=next_version,
        format="raw",
        storage_uri=storage.to_uri(base_key),
        num_images=report.image_count,
        num_labels=report.label_count,
        num_classes=len(report.classes_hint) or None,
        classes=report.classes_hint or None,
        summary={
            "detected_format": report.detected_format,
            "notes": report.notes,
        },
    )
    session.add(version)
    await session.flush()

    await audit.record(
        session,
        project_id=project_id,
        event="dataset.uploaded",
        payload={
            "dataset_id": str(dataset_id),
            "version_id": str(version.id),
            "version": next_version,
            "detected_format": report.detected_format,
            "image_count": report.image_count,
            "label_count": report.label_count,
        },
        actor="system",
    )

    project = await session.get(Project, project_id)
    if project and ProjectStatus(str(project.status)) == ProjectStatus.CREATED:
        project.status = ProjectStatus.DATASET_UPLOADED
        project.updated_at = datetime.now(timezone.utc)
        await audit.record(
            session,
            project_id=project_id,
            event="project.status_changed",
            payload={"from": "created", "to": "dataset_uploaded"},
            actor="system",
        )

    job.message = f"Done — detected {report.detected_format}, {report.image_count} images"
    job.progress = 100
    job.status = JobStatus.SUCCEEDED
    await session.commit()
