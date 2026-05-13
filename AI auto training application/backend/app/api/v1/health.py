"""Liveness + readiness endpoints. Public (no auth)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.envelope import Envelope, ok

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=Envelope[dict])
async def liveness() -> Envelope[dict]:
    return ok({"status": "ok"})


@router.get("/readyz", response_model=Envelope[dict])
async def readiness(session: AsyncSession = Depends(get_session)) -> Envelope[dict]:
    await session.execute(text("select 1"))
    return ok({"status": "ready", "db": "ok"})
