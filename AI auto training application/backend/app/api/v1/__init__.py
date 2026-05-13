from fastapi import APIRouter

from app.api.v1 import analysis, datasets, health, jobs, projects, training

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health.router)
api_v1_router.include_router(projects.router)
api_v1_router.include_router(datasets.router)
api_v1_router.include_router(analysis.router)
api_v1_router.include_router(training.router)
api_v1_router.include_router(jobs.router)
