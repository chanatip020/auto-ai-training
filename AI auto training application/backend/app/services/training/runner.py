"""Training orchestrator.

Entry point: ``start_training`` (called by the API router). It creates a
``training_jobs`` row, returns the id, and schedules a background task that
invokes Ultralytics YOLO via ``asyncio.to_thread``. Per-epoch metrics are
written by ``callbacks.on_train_epoch_end`` and pushed to the SSE bus.

Mock mode: setting environment variable ``TRAINING_MOCK=1`` makes the
runner simulate training without importing Ultralytics — fakes metrics for
each epoch with a 1s sleep. Used in CI / smoke tests.
"""
from __future__ import annotations

import asyncio
import os
import random
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from loguru import logger
from sqlalchemy import asc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db import SessionLocal
from app.models.dataset import DatasetVersion
from app.models.enums import ArtifactKind, JobStatus, ProjectStatus
from app.models.project import Project
from app.models.training import TrainingArtifact, TrainingJob, TrainingMetric
from app.realtime.sse import bus
from app.services import audit
from app.services.training import stop as stop_svc
from app.storage import get_storage


def _is_mock() -> bool:
    return os.environ.get("TRAINING_MOCK", "0") == "1"


def _uri_to_local(uri: str) -> Path:
    p = urlparse(uri)
    if p.scheme != "file":
        raise AppError(
            "TRAIN_NEEDS_LOCAL_STORAGE",
            f"Training requires a local storage backend; got {p.scheme!r}.",
            500,
        )
    return Path(p.path)


def _channel(training_job_id: uuid.UUID) -> str:
    return f"training:{training_job_id}"


async def start_training(
    session: AsyncSession,
    *,
    project: Project,
    dataset_version: DatasetVersion,
    params: dict,
) -> TrainingJob:
    if dataset_version.format == "raw":
        raise AppError(
            "TRAIN_NEEDS_CONVERTED",
            "Training requires a converted dataset (yolo-det/seg/cls), not raw.",
            status_code=400,
        )

    # Fill in missing params from a baseline default.
    defaults = {
        "model": "yolov8n",
        "epochs": 50,
        "imgsz": 640,
        "batch": 16,
        "lr0": 0.01,
        "optimizer": "auto",
        "augment": True,
        "device": "cpu",
    }
    final_params = {**defaults, **params}

    tj = TrainingJob(
        project_id=project.id,
        dataset_version_id=dataset_version.id,
        status=JobStatus.PENDING,
        progress=0,
        total_epochs=int(final_params.get("epochs", 50)),
        params=final_params,
    )
    session.add(tj)
    await session.flush()

    await audit.record(
        session,
        project_id=project.id,
        event="training.started",
        payload={"training_job_id": str(tj.id), "params": final_params},
    )

    # Advance project status -> training
    cur = ProjectStatus(str(project.status))
    if cur in (ProjectStatus.READY_FOR_TRAINING, ProjectStatus.DATASET_ANALYZED):
        project.status = ProjectStatus.TRAINING
        project.updated_at = datetime.now(timezone.utc)
        await audit.record(
            session, project_id=project.id, event="project.status_changed",
            payload={"from": cur.value, "to": "training"},
        )

    return tj


# ---- background runner ----
async def run_training_job(training_job_id: uuid.UUID) -> None:
    """Background task entrypoint. Opens its own session."""
    async with SessionLocal() as session:
        tj = await session.get(TrainingJob, training_job_id)
        if tj is None:
            logger.error("TrainingJob {} disappeared before run", training_job_id)
            return

        # Status -> running
        tj.status = JobStatus.RUNNING
        tj.started_at = datetime.now(timezone.utc)
        tj.message = "Preparing"
        tj.progress = 1
        await session.commit()
        bus.publish(_channel(training_job_id), {
            "type": "status", "status": "running",
            "message": "Preparing", "progress": 1,
        })

        # Resolve dataset and data.yaml path
        version = await session.get(DatasetVersion, tj.dataset_version_id)
        if version is None:
            await _mark_failed(session, tj, "Dataset version not found")
            return

        version_root = _uri_to_local(version.storage_uri)
        data_yaml = version_root / "data.yaml"

        if version.format != "yolo-cls" and not data_yaml.exists():
            await _mark_failed(session, tj, f"data.yaml missing at {data_yaml}")
            return

        stop_svc.clear_stop(training_job_id)
        runs_dir = stop_svc.runs_dir(training_job_id)

        # Total epochs already set; mock or real
        total = int(tj.total_epochs or tj.params.get("epochs", 50))

        try:
            if _is_mock():
                await _run_mock(session, tj, total)
            else:
                await asyncio.to_thread(
                    _run_ultralytics_sync,
                    training_job_id=training_job_id,
                    params=dict(tj.params),
                    data_yaml=str(data_yaml) if version.format != "yolo-cls" else str(version_root),
                    cls_layout=(version.format == "yolo-cls"),
                    runs_dir=str(runs_dir),
                )
                # Re-read tj after thread-side mutations via own sessions.
                await session.refresh(tj)
        except asyncio.CancelledError:
            await _mark_cancelled(session, tj)
            raise
        except Exception as exc:
            logger.exception("Training {} crashed", training_job_id)
            await _mark_failed(session, tj, f"{type(exc).__name__}: {exc}")
            return

        # If callback marked cancelled, leave it alone
        await session.refresh(tj)
        if tj.status == JobStatus.RUNNING:
            tj.status = JobStatus.SUCCEEDED
        tj.finished_at = datetime.now(timezone.utc)
        tj.progress = 100
        tj.message = (
            f"Done — best metric {float(tj.best_metric):.4f}" if tj.best_metric is not None
            else "Done"
        )
        await session.commit()

        # Record artifacts
        await _register_artifacts(session, tj, runs_dir)

        await audit.record(
            session, project_id=tj.project_id, event="training.completed",
            payload={
                "training_job_id": str(tj.id),
                "status": tj.status.value if hasattr(tj.status, "value") else str(tj.status),
                "best_metric": float(tj.best_metric) if tj.best_metric is not None else None,
            },
        )

        # Advance project status -> completed (only on real success)
        project = await session.get(Project, tj.project_id)
        if project is not None and tj.status == JobStatus.SUCCEEDED:
            project.status = ProjectStatus.COMPLETED
            project.updated_at = datetime.now(timezone.utc)
        await session.commit()

        bus.publish(_channel(training_job_id), {
            "type": "done",
            "status": str(tj.status),
            "best_metric": float(tj.best_metric) if tj.best_metric is not None else None,
        })


async def _mark_failed(session, tj, message: str) -> None:
    tj.status = JobStatus.FAILED
    tj.error = message
    tj.finished_at = datetime.now(timezone.utc)
    await session.commit()
    bus.publish(_channel(tj.id), {"type": "failed", "error": message})


async def _mark_cancelled(session, tj) -> None:
    tj.status = JobStatus.CANCELLED
    tj.finished_at = datetime.now(timezone.utc)
    await session.commit()
    bus.publish(_channel(tj.id), {"type": "cancelled"})


# ---- mock training (fake epochs for smoke testing) ----
async def _run_mock(session: AsyncSession, tj: TrainingJob, total_epochs: int) -> None:
    rng = random.Random(int(tj.id) & 0xFFFFFFFF)
    base_loss = 1.5
    for epoch in range(1, total_epochs + 1):
        if stop_svc.is_stop_requested(tj.id):
            await _mark_cancelled(session, tj)
            return
        await asyncio.sleep(0.4)
        loss = max(0.05, base_loss * (0.92 ** epoch) + rng.uniform(-0.02, 0.02))
        val_loss = loss + rng.uniform(0, 0.05)
        map50 = min(0.99, 0.10 + epoch * 0.04 + rng.uniform(-0.01, 0.01))
        map5095 = max(0.0, map50 - 0.18)
        precision = min(0.99, 0.30 + epoch * 0.03)
        recall = min(0.99, 0.25 + epoch * 0.035)

        m = TrainingMetric(
            training_job_id=tj.id, epoch=epoch,
            loss=loss, val_loss=val_loss,
            precision=precision, recall=recall,
            map50=map50, map5095=map5095,
        )
        session.add(m)
        tj.current_epoch = epoch
        tj.progress = int(epoch * 100 / total_epochs)
        tj.message = f"Epoch {epoch}/{total_epochs}"
        if tj.best_metric is None or map5095 > float(tj.best_metric):
            tj.best_metric = map5095
        await session.commit()

        bus.publish(_channel(tj.id), {
            "type": "metric", "epoch": epoch,
            "loss": loss, "val_loss": val_loss,
            "precision": precision, "recall": recall,
            "map50": map50, "map5095": map5095,
            "progress": tj.progress,
        })

    # Write a fake "best.pt" artifact so the artifact path is exercised
    runs = stop_svc.runs_dir(tj.id)
    (runs / "weights").mkdir(exist_ok=True)
    (runs / "weights" / "best.pt").write_bytes(b"MOCK_WEIGHTS")
    (runs / "weights" / "last.pt").write_bytes(b"MOCK_WEIGHTS")


# ---- real Ultralytics path ----
def _run_ultralytics_sync(
    *, training_job_id: uuid.UUID, params: dict, data_yaml: str,
    cls_layout: bool, runs_dir: str,
) -> None:
    """Invoked from a worker thread. Imports ultralytics lazily."""
    try:
        from ultralytics import YOLO  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise AppError(
            "ULTRALYTICS_NOT_INSTALLED",
            "Install the 'ultralytics' package to run real training, or set "
            "TRAINING_MOCK=1 to use the simulated trainer.",
            status_code=500,
        ) from e

    model_name = params.get("model", "yolov8n")
    model = YOLO(model_name)

    from app.services.training.callbacks import attach_callbacks
    attach_callbacks(model, training_job_id=training_job_id)

    target = data_yaml  # for cls, this is the dataset root; for det/seg, the .yaml
    model.train(
        data=target,
        epochs=int(params.get("epochs", 50)),
        imgsz=int(params.get("imgsz", 640)),
        batch=int(params.get("batch", 16)),
        lr0=float(params.get("lr0", 0.01)),
        optimizer=params.get("optimizer", "auto"),
        device=params.get("device", "cpu"),
        project=runs_dir,
        name="train",
        exist_ok=True,
        verbose=False,
    )


# ---- artifact registration ----
async def _register_artifacts(session: AsyncSession, tj: TrainingJob, runs_dir: Path) -> None:
    storage = get_storage()
    # Look for weights and any standard plots
    candidates: list[tuple[Path, ArtifactKind]] = []
    weights_dir = runs_dir / "weights"
    if weights_dir.exists():
        for w in weights_dir.iterdir():
            if w.is_file():
                candidates.append((w, ArtifactKind.WEIGHTS))
    # Plots commonly emitted by Ultralytics under runs_dir/train/
    train_dir = runs_dir / "train"
    if train_dir.exists():
        for p in train_dir.glob("*.png"):
            candidates.append((p, ArtifactKind.PLOT))
        for p in train_dir.glob("*.jpg"):
            candidates.append((p, ArtifactKind.PLOT))
    # Top-level plot files (mock writes here)
    for p in runs_dir.glob("*.png"):
        candidates.append((p, ArtifactKind.PLOT))

    for path, kind in candidates:
        key = f"runs/{tj.id}/artifacts/{path.name}"
        local = storage.local_path(key)
        if local is None:
            continue
        local.parent.mkdir(parents=True, exist_ok=True)
        # If the file is not already inside the storage tree, copy it in.
        if path.resolve() != local.resolve():
            try:
                shutil.copyfile(path, local)
            except Exception as e:
                logger.warning("Failed to copy artifact {}: {}", path, e)
                continue
        size = local.stat().st_size if local.exists() else None
        session.add(TrainingArtifact(
            training_job_id=tj.id,
            name=path.name,
            kind=kind,
            storage_uri=storage.to_uri(key),
            size_bytes=size,
        ))
    await session.commit()


# ---- queries ----
async def list_metrics(
    session: AsyncSession, training_job_id: uuid.UUID,
) -> list[TrainingMetric]:
    stmt = (
        select(TrainingMetric)
        .where(TrainingMetric.training_job_id == training_job_id)
        .order_by(asc(TrainingMetric.epoch))
    )
    return list((await session.execute(stmt)).scalars())


async def list_artifacts(
    session: AsyncSession, training_job_id: uuid.UUID,
) -> list[TrainingArtifact]:
    stmt = (
        select(TrainingArtifact)
        .where(TrainingArtifact.training_job_id == training_job_id)
        .order_by(asc(TrainingArtifact.created_at))
    )
    return list((await session.execute(stmt)).scalars())
