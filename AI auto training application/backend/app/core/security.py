"""Auth dependencies.

v1: a single static API token is compared in constant time. The dependency is
abstracted so JWT/RBAC can be added later without changing routers.
"""
from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models.user import User


@dataclass
class CurrentUser:
    id: str
    email: str


SINGLE_USER_EMAIL = "owner@local"


async def _ensure_default_user(session: AsyncSession) -> User:
    """Get-or-create the single owner user in v1 single-user mode."""
    res = await session.execute(select(User).where(User.email == SINGLE_USER_EMAIL))
    user = res.scalar_one_or_none()
    if user is None:
        user = User(email=SINGLE_USER_EMAIL, display_name="Owner")
        session.add(user)
        await session.flush()
    return user


def _check_token(authorization: str | None) -> None:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Bearer token required.", "details": {}},
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split(" ", 1)[1].strip()
    if not hmac.compare_digest(token, settings.API_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Invalid token.", "details": {}},
            headers={"WWW-Authenticate": "Bearer"},
        )


async def require_auth(authorization: Annotated[str | None, Header()] = None) -> None:
    """FastAPI dependency that just enforces auth, no user object."""
    _check_token(authorization)


async def current_user(
    authorization: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(get_session),
) -> CurrentUser:
    """FastAPI dependency that enforces auth and returns the owner user."""
    _check_token(authorization)
    user = await _ensure_default_user(session)
    return CurrentUser(id=str(user.id), email=user.email)
