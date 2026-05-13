"""Audit log writer — append-only event stream feeding the project timeline."""
from __future__ import annotations

import uuid
from typing import Any, Sequence

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


async def record(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    event: str,
    payload: dict[str, Any] | None = None,
    actor: str | None = None,
) -> AuditLog:
    row = AuditLog(
        project_id=project_id,
        event=event,
        payload=payload or {},
        actor=actor,
    )
    session.add(row)
    await session.flush()
    return row


async def list_for_project(
    session: AsyncSession,
    project_id: uuid.UUID,
    *,
    limit: int = 100,
) -> Sequence[AuditLog]:
    stmt = (
        select(AuditLog)
        .where(AuditLog.project_id == project_id)
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
    )
    res = await session.execute(stmt)
    return res.scalars().all()
