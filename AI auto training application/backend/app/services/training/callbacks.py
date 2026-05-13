"""Ultralytics callbacks: record metrics + check stop sentinel.

These run *inside* a worker thread, not the asyncio event loop, so all DB
writes go through a fresh synchronous SQLAlchemy session and SSE publishes
use `call_soon_threadsafe` indirectly via the bus.
"""
from __future__ import annotations

import asyncio
import uuid

from loguru import logger
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.models.training import TrainingJob, TrainingMetric
from app.realtime.sse import bus
from app.services.training import stop as stop_svc


def _channel(training_job_id: uuid.UUID) -> str:
    return f"training:{training_job_id}"


def attach_callbacks(model, *, training_job_id: uuid.UUID) -> None:
    """Wire Ultralytics callbacks for this training run.

    Ultralytics docs list available hooks: on_train_epoch_end, on_fit_epoch_end,
    on_train_end, on_train_batch_end, etc. We use on_fit_epoch_end which has
    val metrics merged in.
    """

    async def _persist_async(epoch: int, m: dict) -> None:
        async with SessionLocal() as session:
            row = TrainingMetric(
                training_job_id=training_job_id,
                epoch=epoch,
                loss=m.get("train/box_loss"),
                val_loss=m.get("val/box_loss"),
                precision=m.get("metrics/precision(B)"),
                recall=m.get("metrics/recall(B)"),
                map50=m.get("metrics/mAP50(B)"),
                map5095=m.get("metrics/mAP50-95(B)"),
                extra={k: float(v) for k, v in m.items() if isinstance(v, (int, float))},
            )
            session.add(row)
            # Bump current_epoch + best_metric atomically
            map5095 = m.get("metrics/mAP50-95(B)")
            stmt = update(TrainingJob).where(TrainingJob.id == training_job_id).values(
                current_epoch=epoch,
                message=f"Epoch {epoch}",
            )
            await session.execute(stmt)
            tj = await session.get(TrainingJob, training_job_id)
            if tj is not None:
                if tj.total_epochs:
                    tj.progress = min(99, int(epoch * 100 / int(tj.total_epochs)))
                if map5095 is not None and (tj.best_metric is None or map5095 > float(tj.best_metric)):
                    tj.best_metric = map5095
            await session.commit()

    def on_fit_epoch_end(trainer):  # noqa: ANN001
        try:
            metrics = {k: (float(v) if v is not None else None)
                       for k, v in (trainer.metrics or {}).items()}
            epoch = int(getattr(trainer, "epoch", 0)) + 1

            # Schedule the async persist + SSE on the main loop.
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = None
            if loop and loop.is_running():
                asyncio.run_coroutine_threadsafe(_persist_async(epoch, metrics), loop)

            bus.publish(_channel(training_job_id), {
                "type": "metric", "epoch": epoch, **metrics,
            })

            # Honour stop request between epochs
            if stop_svc.is_stop_requested(training_job_id):
                logger.info("Stop requested for {} — asking trainer to halt", training_job_id)
                # Ultralytics check; if available, this forces an early exit.
                if hasattr(trainer, "stop"):
                    trainer.stop = True
        except Exception:
            logger.exception("Training callback raised")

    model.add_callback("on_fit_epoch_end", on_fit_epoch_end)
