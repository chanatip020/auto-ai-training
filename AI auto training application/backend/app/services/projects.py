"""Business logic for the Projects domain."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.enums import ProjectStatus
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services import audit


# Allowed transitions. Kept narrow so accidental moves can't happen.
# v1 only supports create + soft-delete; later phases (datasets, training) extend
# this dict and call _check_transition before mutating Project.status.
_ALLOWED_TRANSITIONS: dict[ProjectStatus, set[ProjectStatus]] = {
    ProjectStatus.CREATED: {ProjectStatus.DATASET_UPLOADED, ProjectStatus.FAILED},
    ProjectStatus.DATASET_UPLOADED: {ProjectStatus.DATASET_ANALYZED, ProjectStatus.FAILED},
    ProjectStatus.DATASET_ANALYZED: {ProjectStatus.READY_FOR_TRAINING, ProjectStatus.FAILED},
    ProjectStatus.READY_FOR_TRAINING: {ProjectStatus.TRAINING, ProjectStatus.FAILED},
    ProjectStatus.TRAINING: {ProjectStatus.COMPLETED, ProjectStatus.FAILED},
    ProjectStatus.COMPLETED: set(),
    ProjectStatus.FAILED: {ProjectStatus.CREATED},  # allow re-start after failure
}


def _check_transition(current: ProjectStatus, target: ProjectStatus) -> None:
    if current == target:
        return
    if target not in _ALLOWED_TRANSITIONS.get(current, set()):
        raise AppError(
            code="INVALID_STATUS_TRANSITION",
            message=f"Cannot move project from {current} to {target}.",
            status_code=409,
            details={"from": current, "to": target},
        )


async def create_project(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    payload: ProjectCreate,
    actor: str | None = None,
) -> Project:
    project = Project(
        user_id=user_id,
        name=payload.name,
        description=payload.description,
        model_family=payload.model_family,
        task_type=payload.task_type,
        status=ProjectStatus.CREATED,
    )
    session.add(project)
    await session.flush()  # populate project.id

    await audit.record(
        session,
        project_id=project.id,
        event="project.created",
        payload={
            "name": project.name,
            "model_family": project.model_family.value,
            "task_type": project.task_type.value,
        },
        actor=actor,
    )
    return project


async def get_project(
    session: AsyncSession, project_id: uuid.UUID, *, user_id: uuid.UUID
) -> Project:
    stmt = select(Project).where(
        Project.id == project_id,
        Project.user_id == user_id,
        Project.deleted_at.is_(None),
    )
    res = await session.execute(stmt)
    project = res.scalar_one_or_none()
    if project is None:
        raise AppError(
            code="PROJECT_NOT_FOUND",
            message="Project not found.",
            status_code=404,
        )
    return project


async def list_projects(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    status: ProjectStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[Sequence[Project], int]:
    base = select(Project).where(
        Project.user_id == user_id, Project.deleted_at.is_(None)
    )
    if status is not None:
        base = base.where(Project.status == status)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    items_stmt = base.order_by(Project.created_at.desc()).limit(limit).offset(offset)
    items = (await session.execute(items_stmt)).scalars().all()
    return items, total


async def update_project(
    session: AsyncSession,
    project_id: uuid.UUID,
    *,
    user_id: uuid.UUID,
    payload: ProjectUpdate,
    actor: str | None = None,
) -> Project:
    project = await get_project(session, project_id, user_id=user_id)
    changed: dict[str, object] = {}
    if payload.name is not None and payload.name != project.name:
        changed["name"] = {"from": project.name, "to": payload.name}
        project.name = payload.name
    if payload.description is not None and payload.description != project.description:
        changed["description"] = "updated"
        project.description = payload.description

    if changed:
        project.updated_at = datetime.now(timezone.utc)
        await audit.record(
            session,
            project_id=project.id,
            event="project.updated",
            payload=changed,
            actor=actor,
        )
    return project


async def soft_delete_project(
    session: AsyncSession,
    project_id: uuid.UUID,
    *,
    user_id: uuid.UUID,
    actor: str | None = None,
) -> None:
    project = await get_project(session, project_id, user_id=user_id)
    project.deleted_at = datetime.now(timezone.utc)
    await audit.record(
        session,
        project_id=project.id,
        event="project.deleted",
        payload={},
        actor=actor,
    )


async def transition_status(
    session: AsyncSession,
    project_id: uuid.UUID,
    *,
    user_id: uuid.UUID,
    target: ProjectStatus,
    actor: str | None = None,
) -> Project:
    project = await get_project(session, project_id, user_id=user_id)
    # Coerce to enum so comparisons and .value lookups are reliable,
    # regardless of whether SQLAlchemy returned an enum or a string.
    current = ProjectStatus(str(project.status))
    _check_transition(current, target)
    if current != target:
        project.status = target
        project.updated_at = datetime.now(timezone.utc)
        await audit.record(
            session,
            project_id=project.id,
            event="project.status_changed",
            payload={"from": current.value, "to": target.value},
            actor=actor,
        )
    return project
