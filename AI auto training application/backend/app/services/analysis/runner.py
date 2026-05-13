"""Analysis orchestrator — runs all checks, persists an Analysis row,
emits audit events, and auto-transitions project status."""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse
from pathlib import Path

from loguru import logger
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.analysis import Analysis
from app.models.dataset import Dataset, DatasetVersion
from app.models.enums import JobStatus, ProjectStatus
from app.models.job import Job
from app.models.project import Project
from app.services import audit
from app.services.analysis import checks, score
from app.services.recommend import dataset as ds_recs


def _uri_to_local(uri: str) -> Path:
    p = urlparse(uri)
    if p.scheme != "file":
        raise AppError(
            "ANALYSIS_NEEDS_LOCAL_STORAGE",
            f"Analysis requires a local storage backend; got {p.scheme!r}.",
            500,
        )
    return Path(p.path)


async def get_latest_for_version(
    session: AsyncSession, dataset_version_id: uuid.UUID
) -> Analysis | None:
    stmt = (
        select(Analysis)
        .where(Analysis.dataset_version_id == dataset_version_id)
        .order_by(desc(Analysis.created_at))
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def run_analysis(session: AsyncSession, job: Job) -> None:
    payload = job.payload or {}
    project_id = uuid.UUID(payload["project_id"])
    dataset_version_id = uuid.UUID(payload["dataset_version_id"])

    version = await session.get(DatasetVersion, dataset_version_id)
    if version is None:
        raise AppError("DATASET_VERSION_NOT_FOUND", "Dataset version not found.", 404)

    if version.format == "raw":
        raise AppError(
            "ANALYSIS_RAW_NOT_SUPPORTED",
            "Analysis runs on converted versions (yolo-det/seg/cls), not raw uploads. "
            "Run conversion first.",
            status_code=400,
            details={"format": version.format},
        )

    job.status = JobStatus.RUNNING
    job.message = "Scanning files"
    job.progress = 10
    await session.commit()

    version_root = _uri_to_local(version.storage_uri)

    # Run sync checks in a worker thread to keep the event loop responsive.
    findings = await asyncio.to_thread(checks.run_all_checks, version_root)

    job.message = "Scoring"
    job.progress = 80
    await session.commit()

    total, components = score.compute(findings)
    recommendations, ready = ds_recs.evaluate(findings, health_score=total)

    analysis = Analysis(
        dataset_version_id=dataset_version_id,
        health_score=total,
        findings={"checks": findings, "components": components},
        recommendations=recommendations,
        ready_for_training=ready,
    )
    session.add(analysis)
    await session.flush()

    # Audit event
    await audit.record(
        session,
        project_id=project_id,
        event="dataset.analyzed",
        payload={
            "dataset_version_id": str(dataset_version_id),
            "analysis_id": str(analysis.id),
            "health_score": float(total),
            "ready_for_training": ready,
            "n_recommendations": len(recommendations),
        },
        actor="system",
    )

    # Auto-transition project status
    project = await session.get(Project, project_id)
    if project is not None:
        cur = ProjectStatus(str(project.status))
        target = ProjectStatus.READY_FOR_TRAINING if ready else ProjectStatus.DATASET_ANALYZED
        # Only advance forward, never regress
        order = [
            ProjectStatus.CREATED, ProjectStatus.DATASET_UPLOADED,
            ProjectStatus.DATASET_ANALYZED, ProjectStatus.READY_FOR_TRAINING,
        ]
        if cur in order and target in order and order.index(target) > order.index(cur):
            project.status = target
            project.updated_at = datetime.now(timezone.utc)
            await audit.record(
                session,
                project_id=project_id,
                event="project.status_changed",
                payload={"from": cur.value, "to": target.value},
                actor="system",
            )

    job.message = (
        f"Done — health={total:.1f}/100, "
        f"{len(recommendations)} recommendation(s), "
        f"ready={ready}"
    )
    job.progress = 100
    job.status = JobStatus.SUCCEEDED
    await session.commit()
    logger.info(
        "Analysis done: version={} score={} ready={}",
        dataset_version_id, total, ready,
    )
