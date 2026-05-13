"""Conversion orchestration.

Picks a converter based on the requested `format`, finds the latest raw
dataset_version for the dataset, runs the converter, and writes a new
dataset_version row with the conversion result.
"""
from __future__ import annotations

import uuid
from urllib.parse import urlparse

from loguru import logger
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.dataset import Dataset, DatasetVersion
from app.models.enums import JobStatus
from app.models.job import Job
from app.services import audit
from app.services.datasets.converters import FORMAT_TO_CONVERTER
from app.services.datasets.split import DEFAULT_RATIOS, validate_ratios
from app.storage import get_storage


def _normalized_key(project_id: uuid.UUID, dataset_id: uuid.UUID, version: int) -> str:
    return f"normalized/{project_id}/{dataset_id}/v{version}"


def _uri_to_local(uri: str):
    """Translate a file:// storage_uri back to a local Path.

    For non-local backends this would download to a temp dir; v1 is local-only.
    """
    p = urlparse(uri)
    if p.scheme != "file":
        raise AppError(
            "CONVERT_NEEDS_LOCAL_STORAGE",
            f"Conversion requires a local storage backend; got {p.scheme!r}.",
            500,
        )
    from pathlib import Path
    return Path(p.path)


async def _latest_raw_version(session: AsyncSession, dataset_id: uuid.UUID) -> DatasetVersion:
    """Return the most-recent raw (uningested) version for this dataset."""
    stmt = (
        select(DatasetVersion)
        .where(DatasetVersion.dataset_id == dataset_id, DatasetVersion.format == "raw")
        .order_by(desc(DatasetVersion.version))
        .limit(1)
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise AppError(
            "CONVERT_NO_RAW_VERSION",
            "No raw dataset version available. Upload a dataset first.",
            status_code=400,
        )
    return row


async def run_convert(session: AsyncSession, job: Job) -> None:
    """Background handler — entry from the job runner."""
    payload = job.payload or {}
    project_id = uuid.UUID(payload["project_id"])
    dataset_id = uuid.UUID(payload["dataset_id"])
    fmt: str = payload["format"]
    ratios: dict[str, float] = payload.get("ratios") or DEFAULT_RATIOS
    classes_override = payload.get("classes_override")

    validate_ratios(ratios)
    converter_cls = FORMAT_TO_CONVERTER.get(fmt)
    if converter_cls is None:
        raise AppError("CONVERT_BAD_FORMAT", f"Unknown format {fmt!r}", 400,
                       details={"supported": sorted(FORMAT_TO_CONVERTER)})

    # Load dataset + locate the raw version
    ds = await session.get(Dataset, dataset_id)
    if ds is None or ds.deleted_at is not None:
        raise AppError("DATASET_NOT_FOUND", "Dataset not found.", 404)

    raw = await _latest_raw_version(session, dataset_id)

    job.status = JobStatus.RUNNING
    job.message = f"Converting (source v{raw.version})"
    job.progress = 5
    await session.commit()

    storage = get_storage()
    input_dir = _uri_to_local(raw.storage_uri)

    # Allocate next version number
    next_v = (await session.execute(
        select(func.coalesce(func.max(DatasetVersion.version), 0) + 1).where(
            DatasetVersion.dataset_id == dataset_id
        )
    )).scalar_one()

    output_key = _normalized_key(project_id, dataset_id, next_v)
    output_dir = storage.local_path(output_key)
    if output_dir is None:
        raise AppError("STORAGE_NOT_LOCAL", "Conversion requires local storage.", 500)
    output_dir.parent.mkdir(parents=True, exist_ok=True)

    job.message = "Pairing images with labels"
    job.progress = 20
    await session.commit()

    converter = converter_cls()
    result = await _run_in_thread(
        converter.convert,
        input_dir=input_dir,
        output_dir=output_dir,
        ratios=ratios,
        classes_override=classes_override,
        seed=dataset_id,
    )

    job.message = "Recording dataset version"
    job.progress = 90
    await session.commit()

    version = DatasetVersion(
        dataset_id=dataset_id,
        version=next_v,
        format=result.format,
        storage_uri=storage.to_uri(output_key),
        num_images=result.num_images,
        num_labels=result.num_labels,
        num_classes=len(result.classes),
        classes=result.classes,
        summary={
            "counts": result.counts,
            "ratios": ratios,
            "notes": result.notes,
            "source_version": raw.version,
            **result.extra,
        },
    )
    session.add(version)
    await session.flush()

    await audit.record(
        session,
        project_id=project_id,
        event="dataset.converted",
        payload={
            "dataset_id": str(dataset_id),
            "version_id": str(version.id),
            "version": next_v,
            "format": result.format,
            "counts": result.counts,
            "num_classes": len(result.classes),
        },
        actor="system",
    )

    job.message = (
        f"Done — v{next_v} {result.format}: "
        f"train={result.counts.get('train', 0)} "
        f"val={result.counts.get('val', 0)} "
        f"test={result.counts.get('test', 0)}"
    )
    job.progress = 100
    job.status = JobStatus.SUCCEEDED
    await session.commit()
    logger.info("Conversion done: dataset={} v={} format={}", dataset_id, next_v, result.format)


async def _run_in_thread(fn, **kwargs):
    """Run a sync converter in a worker thread."""
    import asyncio
    return await asyncio.to_thread(lambda: fn(**kwargs))
