"""Uniform error envelope + handlers."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """Domain error with a stable code so the UI can branch on it."""

    def __init__(self, code: str, message: str,
                 status_code: int = 400, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def _envelope(error: dict[str, Any] | None, data: Any = None,
              request_id: str | None = None) -> dict[str, Any]:
    return {
        "data": data,
        "error": error,
        "meta": {"request_id": request_id, "timestamp": _now_iso()},
    }


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(
                error={"code": exc.code, "message": exc.message, "details": exc.details},
                request_id=request.headers.get("x-request-id"),
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exc(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if isinstance(exc, HTTPException) and isinstance(exc.detail, dict) and "code" in exc.detail:
            payload = exc.detail
        else:
            payload = {"code": "HTTP_ERROR", "message": str(exc.detail), "details": {}}
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(error=payload, request_id=request.headers.get("x-request-id")),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_exc(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope(
                error={
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid request payload.",
                    "details": {"errors": exc.errors()},
                },
                request_id=request.headers.get("x-request-id"),
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        from app.config import settings  # local import to avoid cycles
        logger.exception("Unhandled exception")
        details: dict[str, Any] = {}
        # Surface the real error in dev so smoke tests can debug from response.
        # Production keeps the response opaque.
        if settings.APP_ENV == "dev":
            details = {"exception": type(exc).__name__, "message": str(exc)}
        return JSONResponse(
            status_code=500,
            content=_envelope(
                error={
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred.",
                    "details": details,
                },
                request_id=request.headers.get("x-request-id"),
            ),
        )
