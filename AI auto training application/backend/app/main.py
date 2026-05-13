"""FastAPI app factory."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.v1 import api_v1_router
from app.config import settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    configure_logging()
    logger.info("Starting AI Auto Training API ({} mode)", settings.APP_ENV)
    yield
    logger.info("Shutting down AI Auto Training API")


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Auto Training Platform — API",
        version="0.1.0",
        description="Phase 0 + 1: foundations and project management.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)
    app.include_router(api_v1_router)
    return app


app = create_app()
