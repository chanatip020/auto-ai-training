"""Projects REST endpoints (Phase 1)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser, current_user
from app.db import get_session
from app.models.enums import ProjectStatus
from app.schemas.audit_log import AuditLogOut, TimelineOut
from app.schemas.envelope import Envelope, ok
from app.schemas.project import (
    ProjectCreate,
    ProjectListOut,
    ProjectOut,
    ProjectStatusUpdate,
    ProjectUpdate,
)
from app.services import audit, projects as project_svc

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post(
    "",
    response_model=Envelope[ProjectOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    payload: ProjectCreate,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[ProjectOut]:
    project = await project_svc.create_project(
        session,
        user_id=uuid.UUID(user.id),
        payload=payload,
        actor=user.email,
    )
    return ok(ProjectOut.model_validate(project))


@router.get("", response_model=Envelope[ProjectListOut])
async def list_projects(
    status_filter: ProjectStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[ProjectListOut]:
    items, total = await project_svc.list_projects(
        session,
        user_id=uuid.UUID(user.id),
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return ok(ProjectListOut(
        items=[ProjectOut.model_validate(p) for p in items],
        total=total,
    ))


@router.get("/{project_id}", response_model=Envelope[ProjectOut])
async def get_project(
    project_id: uuid.UUID,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[ProjectOut]:
    project = await project_svc.get_project(session, project_id, user_id=uuid.UUID(user.id))
    return ok(ProjectOut.model_validate(project))


@router.patch("/{project_id}", response_model=Envelope[ProjectOut])
async def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[ProjectOut]:
    project = await project_svc.update_project(
        session, project_id,
        user_id=uuid.UUID(user.id),
        payload=payload,
        actor=user.email,
    )
    return ok(ProjectOut.model_validate(project))


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    await project_svc.soft_delete_project(
        session, project_id,
        user_id=uuid.UUID(user.id),
        actor=user.email,
    )


@router.post("/{project_id}/status", response_model=Envelope[ProjectOut])
async def transition_status(
    project_id: uuid.UUID,
    payload: ProjectStatusUpdate,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[ProjectOut]:
    """Manual status transition endpoint.

    Later phases (datasets, training) drive transitions automatically; this
    endpoint stays for admin overrides and tests.
    """
    project = await project_svc.transition_status(
        session, project_id,
        user_id=uuid.UUID(user.id),
        target=payload.status,
        actor=user.email,
    )
    return ok(ProjectOut.model_validate(project))


@router.get("/{project_id}/timeline", response_model=Envelope[TimelineOut])
async def project_timeline(
    project_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500),
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[TimelineOut]:
    # Auth check + ownership: load the project first.
    await project_svc.get_project(session, project_id, user_id=uuid.UUID(user.id))
    rows = await audit.list_for_project(session, project_id, limit=limit)
    return ok(TimelineOut(items=[AuditLogOut.model_validate(r) for r in rows]))
