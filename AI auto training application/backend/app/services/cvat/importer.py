"""Background CVAT-import job.

Pipeline:
  1. Mark import as running
  2. Connect to CVAT and request a dataset export (returns rq_id)
  3. Poll /api/requests/{rq_id} with exponential backoff (max ~5 min)
  4. Stream the resulting ZIP into our storage tree
  5. Create a Dataset + dataset_version row, kick off the existing zip-ingest
  6. If `auto_convert` flag set, also schedule the conversion job after ingest

Each step writes its progress to cvat_imports.payload so a retry can
pick up where it left off.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db import SessionLocal
from app.models.cvat import CvatConnection, CvatImport
from app.models.dataset import Dataset
from app.models.enums import CvatSourceType, DatasetSource, JobStatus
from app.services import audit
from app.services.cvat.client import client_from
from app.services.datasets import ingest as ingest_svc
from app.storage import get_storage


def _key(project_id: uuid.UUID, import_id: uuid.UUID) -> str:
    return f"raw/{project_id}/cvat-{import_id}/upload.zip"


async def run_import(import_id: uuid.UUID) -> None:
    """Background task entry point. Opens its own DB session."""
    async with SessionLocal() as session:
        imp = await session.get(CvatImport, import_id)
        if imp is None:
            logger.error("CvatImport {} disappeared before run", import_id)
            return

        imp.status = JobStatus.RUNNING
        imp.started_at = datetime.now(timezone.utc)
        imp.attempts = (imp.attempts or 0) + 1
        imp.message = "Connecting to CVAT"
        imp.progress = 5
        await session.commit()

        try:
            await _run(session, imp)
        except asyncio.CancelledError:
            imp.status = JobStatus.CANCELLED
            imp.finished_at = datetime.now(timezone.utc)
            await session.commit()
            raise
        except Exception as exc:
            logger.exception("CVAT import {} failed", import_id)
            imp.status = JobStatus.FAILED
            imp.error = f"{type(exc).__name__}: {exc}"
            imp.finished_at = datetime.now(timezone.utc)
            await session.commit()
            return

        imp.status = JobStatus.SUCCEEDED
        imp.progress = 100
        imp.finished_at = datetime.now(timezone.utc)
        await session.commit()
        await audit.record(
            session, project_id=imp.project_id,
            event="cvat.import.succeeded",
            payload={"cvat_import_id": str(imp.id), "source_type": imp.source_type.value,
                     "source_id": imp.source_id, "source_name": imp.source_name},
        )
        await session.commit()


async def _run(session: AsyncSession, imp: CvatImport) -> None:
    connection = (await session.get(CvatConnection, imp.connection_id)
                  if imp.connection_id else None)
    if connection is None:
        raise AppError("CVAT_CONNECTION_GONE",
                       "The CVAT connection was deleted before this import could run.", 400)

    plural_source = "project" if imp.source_type == CvatSourceType.PROJECT else "task"

    async with client_from(connection) as cvat:
        # 2. Request export
        payload = dict(imp.payload or {})
        rq_id = payload.get("rq_id")
        if not rq_id:
            imp.message = "Requesting CVAT export"
            imp.progress = 15
            await session.commit()
            rq_id = await cvat.request_export(
                source=plural_source, source_id=imp.source_id, format="YOLO 1.1",
            )
            payload["rq_id"] = rq_id
            imp.payload = payload
            await session.commit()

        # 3. Poll
        result_url: str | None = payload.get("result_url")
        if not result_url:
            imp.message = "Waiting for CVAT to prepare the export"
            imp.progress = 30
            await session.commit()

            backoff = 2
            max_seconds = 300
            elapsed = 0.0
            while elapsed < max_seconds:
                info = await cvat.poll_request(rq_id)
                status = (info.get("status") or "").lower()
                if status in ("finished", "succeeded", "successful"):
                    result_url = (info.get("result_url")
                                  or info.get("result", {}).get("url"))
                    if not result_url:
                        # CVAT returns the download URL via Location header in some versions;
                        # fall back to /api/{plural}/{id}/dataset?action=download
                        result_url = (
                            f"/api/{plural_source}s/{imp.source_id}/dataset"
                            f"?action=download&format=YOLO+1.1&rq_id={rq_id}"
                        )
                    payload["result_url"] = result_url
                    imp.payload = payload
                    await session.commit()
                    break
                if status in ("failed", "errored"):
                    raise AppError(
                        "CVAT_EXPORT_FAILED",
                        f"CVAT reports the export failed: {info.get('message', '?')}",
                        502,
                    )
                # still running
                imp.progress = 30 + min(50, int(elapsed / max_seconds * 50))
                imp.message = f"CVAT export: {status or 'queued'}"
                await session.commit()
                await asyncio.sleep(backoff)
                elapsed += backoff
                backoff = min(15, int(backoff * 1.6))
            else:
                raise AppError("CVAT_EXPORT_TIMEOUT",
                               f"CVAT export still not ready after {max_seconds}s", 504)

        # 4. Stream-download into storage
        storage = get_storage()
        zip_key = _key(imp.project_id, imp.id)
        zip_path = storage.local_path(zip_key)
        if zip_path is None:
            raise AppError("STORAGE_NOT_LOCAL",
                           "CVAT import currently requires local storage.", 500)
        zip_path.parent.mkdir(parents=True, exist_ok=True)

        imp.message = "Downloading export"
        imp.progress = 80
        await session.commit()

        with open(zip_path, "wb") as f:
            async for chunk in cvat.stream_download(result_url):
                f.write(chunk)

        # 5. Create dataset shell + delegate to the existing ingest pipeline
        imp.message = "Ingesting"
        imp.progress = 90
        await session.commit()

        ds_name = imp.source_name or f"cvat-{imp.source_type.value}-{imp.source_id}"
        dataset = await ingest_svc.create_dataset(
            session, project_id=imp.project_id, name=ds_name,
            source=DatasetSource.CVAT, actor=f"cvat:{connection.username}",
        )
        upload_id = uuid.uuid4()
        # Move/copy the downloaded zip to the dataset's raw/ location
        target_key = (f"raw/{imp.project_id}/{dataset.id}/{upload_id}/upload.zip")
        target_path = storage.local_path(target_key)
        assert target_path is not None
        target_path.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.move(str(zip_path), str(target_path))

        # Save dataset_id for resumability / audit + run the existing ingest task
        payload["dataset_id"] = str(dataset.id)
        payload["upload_id"] = str(upload_id)
        imp.payload = payload
        await session.commit()

        # Inline the ingest (synchronous in the import task — keeps progress in one row)
        from app.models.job import Job
        from app.models.enums import JobKind
        job = Job(
            kind=JobKind.INGEST_ZIP, project_id=imp.project_id, dataset_id=dataset.id,
            payload={
                "project_id": str(imp.project_id), "dataset_id": str(dataset.id),
                "upload_id": str(upload_id), "zip_key": target_key,
            },
        )
        session.add(job)
        await session.flush()
        await ingest_svc.run_ingest_zip(session, job)
        connection.last_used_at = datetime.now(timezone.utc)
        await session.commit()
