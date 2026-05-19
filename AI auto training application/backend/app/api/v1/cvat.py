"""CVAT integration endpoints (Phase 12)."""
from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import encrypt
from app.core.errors import AppError
from app.core.security import CurrentUser, current_user
from app.db import get_session
from app.models.cvat import CvatConnection, CvatImport
from app.schemas.cvat import (
    CvatConnectionCreate,
    CvatConnectionListOut,
    CvatConnectionOut,
    CvatImportCreate,
    CvatImportOut,
    CvatProjectSummary,
    CvatTaskSummary,
)
from app.schemas.envelope import Envelope, ok
from app.services import audit
from app.services import projects as project_svc
from app.services.cvat import importer as cvat_importer
from app.services.cvat.client import client_from

router = APIRouter(tags=["cvat"])


# ---------- connections CRUD ----------

@router.post("/cvat/connections",
             response_model=Envelope[CvatConnectionOut],
             status_code=status.HTTP_201_CREATED)
async def create_connection(
    payload: CvatConnectionCreate,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[CvatConnectionOut]:
    conn = CvatConnection(
        user_id=uuid.UUID(user.id),
        name=payload.name.strip(),
        base_url=payload.base_url.strip().rstrip("/"),
        username=payload.username.strip(),
        encrypted_secret=encrypt(payload.secret),
    )
    session.add(conn)
    await session.flush()
    return ok(CvatConnectionOut.model_validate(conn))


@router.get("/cvat/connections", response_model=Envelope[CvatConnectionListOut])
async def list_connections(
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[CvatConnectionListOut]:
    stmt = (
        select(CvatConnection)
        .where(CvatConnection.user_id == uuid.UUID(user.id))
        .order_by(desc(CvatConnection.created_at))
    )
    items = list((await session.execute(stmt)).scalars())
    return ok(CvatConnectionListOut(
        items=[CvatConnectionOut.model_validate(c) for c in items],
        total=len(items),
    ))


@router.delete("/cvat/connections/{connection_id}",
               status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    connection_id: uuid.UUID,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    conn = await session.get(CvatConnection, connection_id)
    if conn is None or conn.user_id != uuid.UUID(user.id):
        raise HTTPException(404, detail={"code": "CVAT_CONNECTION_NOT_FOUND",
                                         "message": "Connection not found.", "details": {}})
    await session.delete(conn)


@router.post("/cvat/connections/{connection_id}/test",
             response_model=Envelope[dict])
async def test_connection(
    connection_id: uuid.UUID,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[dict]:
    conn = await _load_owned(session, connection_id, user)
    async with client_from(conn) as cvat:
        info = await cvat.about()
    return ok({"ok": True, "server": info.get("version") or info.get("name") or "ok"})


# ---------- list projects / tasks (5-min in-memory cache) ----------

_cache: dict[tuple[str, uuid.UUID], tuple[float, list[dict]]] = {}
_TTL = 300  # seconds


@router.get("/cvat/connections/{connection_id}/projects",
            response_model=Envelope[list[CvatProjectSummary]])
async def list_cvat_projects(
    connection_id: uuid.UUID,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[list[CvatProjectSummary]]:
    conn = await _load_owned(session, connection_id, user)
    key = ("projects", connection_id)
    now = time.time()
    cached = _cache.get(key)
    if cached and now - cached[0] < _TTL:
        rows = cached[1]
    else:
        async with client_from(conn) as cvat:
            rows = await cvat.list_projects()
        _cache[key] = (now, rows)
    return ok([CvatProjectSummary(**_normalize_project(r)) for r in rows])


@router.get("/cvat/connections/{connection_id}/tasks",
            response_model=Envelope[list[CvatTaskSummary]])
async def list_cvat_tasks(
    connection_id: uuid.UUID,
    project_id: int | None = None,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[list[CvatTaskSummary]]:
    conn = await _load_owned(session, connection_id, user)
    key = (f"tasks:{project_id}", connection_id)
    now = time.time()
    cached = _cache.get(key)
    if cached and now - cached[0] < _TTL:
        rows = cached[1]
    else:
        async with client_from(conn) as cvat:
            rows = await cvat.list_tasks(project_id=project_id)
        _cache[key] = (now, rows)
    return ok([CvatTaskSummary(**_normalize_task(r)) for r in rows])


# ---------- imports ----------

@router.post("/projects/{project_id}/cvat-imports",
             response_model=Envelope[CvatImportOut],
             status_code=status.HTTP_202_ACCEPTED)
async def start_cvat_import(
    project_id: uuid.UUID,
    payload: CvatImportCreate,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[CvatImportOut]:
    project = await project_svc.get_project(session, project_id, user_id=uuid.UUID(user.id))
    conn = await _load_owned(session, payload.connection_id, user)

    imp = CvatImport(
        project_id=project.id,
        connection_id=conn.id,
        source_type=payload.source_type,
        source_id=payload.source_id,
        source_name=payload.source_name,
    )
    session.add(imp)
    await session.flush()
    await audit.record(
        session, project_id=project.id, event="cvat.import.started",
        payload={"cvat_import_id": str(imp.id),
                 "source_type": payload.source_type.value,
                 "source_id": payload.source_id,
                 "source_name": payload.source_name},
    )
    await session.commit()

    import_id = imp.id

    async def _entry() -> None:
        await cvat_importer.run_import(import_id)

    background_tasks.add_task(_entry)
    return ok(CvatImportOut.model_validate(imp))


@router.get("/cvat-imports/{import_id}",
            response_model=Envelope[CvatImportOut])
async def get_cvat_import(
    import_id: uuid.UUID,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[CvatImportOut]:
    imp = await session.get(CvatImport, import_id)
    if imp is None:
        raise HTTPException(404, detail={"code": "CVAT_IMPORT_NOT_FOUND",
                                         "message": "Import not found.", "details": {}})
    await project_svc.get_project(session, imp.project_id, user_id=uuid.UUID(user.id))
    return ok(CvatImportOut.model_validate(imp))


# ---------- helpers ----------

async def _load_owned(session: AsyncSession,
                      connection_id: uuid.UUID, user: CurrentUser) -> CvatConnection:
    conn = await session.get(CvatConnection, connection_id)
    if conn is None or conn.user_id != uuid.UUID(user.id):
        raise HTTPException(404, detail={"code": "CVAT_CONNECTION_NOT_FOUND",
                                         "message": "Connection not found.", "details": {}})
    return conn


def _normalize_project(r: dict) -> dict:
    return {
        "id": r.get("id"),
        "name": r.get("name", ""),
        "status": r.get("status"),
        "tasks_count": r.get("tasks_count") or r.get("task_count"),
        "updated_date": r.get("updated_date"),
    }


def _normalize_task(r: dict) -> dict:
    return {
        "id": r.get("id"),
        "name": r.get("name", ""),
        "status": r.get("status"),
        "size": r.get("size"),
        "project_id": r.get("project_id"),
        "updated_date": r.get("updated_date"),
    }
