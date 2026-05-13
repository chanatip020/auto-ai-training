"""Background-job runner.

v1: wraps FastAPI's BackgroundTasks so a coroutine runs after the response is
sent, while persisting status/progress to the jobs table. Each task gets a
fresh DB session (the request-scoped one is closed by the time the task runs).

Later phase: swap the body of ``schedule()`` for a Celery .delay() — no
caller changes needed.
"""
from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.models.enums import JobKind, JobStatus
from app.models.job import Job


# A job handler receives (session, job, **payload) and runs until done.
JobHandler = Callable[[AsyncSession, Job], Awaitable[None]]


async def create_job(
    session: AsyncSession,
    *,
    kind: JobKind,
    project_id: uuid.UUID | None = None,
    dataset_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
) -> Job:
    job = Job(
        kind=kind,
        project_id=project_id,
        dataset_id=dataset_id,
        payload=payload or {},
        status=JobStatus.PENDING,
    )
    session.add(job)
    await session.flush()
    return job


class JobContext:
    """Thin helper passed to handlers for reporting progress + errors."""

    def __init__(self, job_id: uuid.UUID):
        self.job_id = job_id

    async def update(
        self,
        session: AsyncSession,
        *,
        progress: int | None = None,
        message: str | None = None,
    ) -> None:
        job = await session.get(Job, self.job_id)
        if not job:
            return
        if progress is not None:
            job.progress = max(0, min(100, progress))
        if message is not None:
            job.message = message
        await session.flush()


async def _run(job_id: uuid.UUID, handler: JobHandler) -> None:
    """Invoked from BackgroundTasks. Opens its own session."""
    async with SessionLocal() as session:
        job = await session.get(Job, job_id)
        if job is None:
            logger.error("Job {} disappeared before run", job_id)
            return

        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        await session.commit()

        try:
            await handler(session, job)
            # handler may have mutated job; reload to get final state
            await session.refresh(job)
            if job.status not in (JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED):
                job.status = JobStatus.SUCCEEDED
                job.progress = 100
            job.finished_at = datetime.now(timezone.utc)
            await session.commit()
            logger.info("Job {} ({}) finished status={}", job.id, job.kind, job.status)
        except asyncio.CancelledError:
            job.status = JobStatus.CANCELLED
            job.finished_at = datetime.now(timezone.utc)
            await session.commit()
            raise
        except Exception as exc:
            logger.exception("Job {} failed", job_id)
            job.status = JobStatus.FAILED
            job.error = f"{type(exc).__name__}: {exc}"
            job.finished_at = datetime.now(timezone.utc)
            await session.commit()


def schedule(background_tasks, job: Job, handler: JobHandler) -> uuid.UUID:
    """Register a background task to run the handler against the given job.

    ``background_tasks`` is the FastAPI BackgroundTasks dependency. We hand it
    a coroutine factory so the handler runs after the response is sent.
    """
    job_id = job.id

    async def _entrypoint() -> None:
        await _run(job_id, handler)

    background_tasks.add_task(_entrypoint)
    return job_id


async def get_job(session: AsyncSession, job_id: uuid.UUID) -> Job | None:
    stmt = select(Job).where(Job.id == job_id)
    return (await session.execute(stmt)).scalar_one_or_none()
