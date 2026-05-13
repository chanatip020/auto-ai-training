"""Stop-sentinel mechanism.

Stopping a running training is request-driven from a different async task
than the one running Ultralytics. We use a tiny file as the rendezvous:
the API handler writes it, the training callback polls for it after every
epoch and asks Ultralytics to halt.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from app.storage import get_storage


def _key(training_job_id: uuid.UUID) -> str:
    return f"runs/{training_job_id}/STOP"


def request_stop(training_job_id: uuid.UUID) -> None:
    storage = get_storage()
    path = storage.local_path(_key(training_job_id))
    if path is None:
        raise RuntimeError("Stop sentinel requires local storage in v1.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("stop")


def is_stop_requested(training_job_id: uuid.UUID) -> bool:
    storage = get_storage()
    path = storage.local_path(_key(training_job_id))
    return path is not None and path.exists()


def clear_stop(training_job_id: uuid.UUID) -> None:
    storage = get_storage()
    path = storage.local_path(_key(training_job_id))
    if path is not None and path.exists():
        try:
            path.unlink()
        except Exception:
            pass


def runs_dir(training_job_id: uuid.UUID) -> Path:
    storage = get_storage()
    p = storage.local_path(f"runs/{training_job_id}")
    if p is None:
        raise RuntimeError("Training requires local storage in v1.")
    p.mkdir(parents=True, exist_ok=True)
    return p
