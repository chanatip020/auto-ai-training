"""Generic background-job status endpoint (Phase 2)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser, current_user
from app.db import get_session
from app.jobs.runner import get_job
from app.schemas.envelope import Envelope, ok
from app.schemas.job import JobOut
from app.services import projects as project_svc

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=Envelope[JobOut])
async def get_job_status(
    job_id: uuid.UUID,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[JobOut]:
    job = await get_job(session, job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "JOB_NOT_FOUND", "message": "Job not found.", "details": {}},
        )
    # Authorization: every job is tied to a project (in our phases so far).
    if job.project_id is not None:
        await project_svc.get_project(session, job.project_id, user_id=uuid.UUID(user.id))
    return ok(JobOut.model_validate(job))
