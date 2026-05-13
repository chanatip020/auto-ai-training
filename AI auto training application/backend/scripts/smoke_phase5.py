"""End-to-end smoke test for Phase 5 (training).

Runs in **mock mode** by default so you don't need to install Ultralytics
just to test the wiring. Real training uses ``ultralytics`` from the
``[training]`` extra:  pip install -e ".[training]"

Prereqs:
    alembic upgrade head                       # applies 0001..0004
    set TRAINING_MOCK=1                        # PowerShell: $env:TRAINING_MOCK="1"
    uvicorn app.main:app --reload --port 8000  # Terminal A
    python scripts/make_fake_dataset.py --out fake.zip --n 10

Then in Terminal B:
    python scripts/smoke_phase5.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, ".")
from app.config import settings  # noqa: E402

BASE = os.environ.get("API_BASE", "http://localhost:8000")
HEADERS = {"Authorization": f"Bearer {settings.API_TOKEN}"}
ZIP_PATH = Path(os.environ.get("ZIP_PATH", "fake.zip"))


def step(name, response):
    body = response.json() if response.content else {}
    ok = response.is_success
    icon = "OK  " if ok else "FAIL"
    print(f"[{icon}] {response.request.method:6s} {response.request.url.path}  -> {response.status_code}  ({name})")
    if not ok:
        print(f"       body: {body}")
        sys.exit(1)
    return body


def poll(c, job_id, label, path="/api/v1/jobs/"):
    print(f"       polling {label}: {job_id}")
    for _ in range(120):
        time.sleep(1)
        j = step("poll", c.get(f"{path}{job_id}"))["data"]
        sts = j.get('status')
        print(f"       status={sts:10s}  progress={j.get('progress','?'):>3}%  msg={j.get('message')}")
        if sts in ("succeeded", "failed", "cancelled"):
            return j
    sys.exit(f"{label} did not finish in 120s")


def main() -> None:
    if not ZIP_PATH.exists():
        print(f"Missing {ZIP_PATH}. Run: python scripts/make_fake_dataset.py --out {ZIP_PATH} --n 10")
        sys.exit(2)

    with httpx.Client(base_url=BASE, headers=HEADERS, timeout=60) as c:
        # Set up: project + dataset + upload + convert
        project_id = step("create project", c.post("/api/v1/projects", json={
            "name": "Phase 5 smoke", "description": "", "model_family": "yolo", "task_type": "detection",
        }))["data"]["id"]
        dataset_id = step("create dataset", c.post(f"/api/v1/projects/{project_id}/datasets", json={
            "name": "fake-yolo", "source": "upload",
        }))["data"]["id"]
        with open(ZIP_PATH, "rb") as f:
            jid = step("upload", c.post(
                f"/api/v1/datasets/{dataset_id}/upload-zip",
                files={"file": (ZIP_PATH.name, f, "application/zip")},
            ))["data"]["job_id"]
        poll(c, jid, "ingest")
        jid = step("convert", c.post(
            f"/api/v1/datasets/{dataset_id}/convert", json={"format": "yolo-det"},
        ))["data"]["job_id"]
        poll(c, jid, "convert")

        body = step("get dataset", c.get(f"/api/v1/datasets/{dataset_id}"))
        version = next(v for v in body["data"]["versions"] if v["format"] == "yolo-det")
        version_id = version["id"]

        # Start training with a short epoch count to keep mock smoke fast
        body = step("start training", c.post(
            f"/api/v1/projects/{project_id}/training-jobs",
            json={
                "dataset_version_id": version_id,
                "params": {"model": "yolov8n", "epochs": 5, "imgsz": 320, "batch": 4, "device": "cpu"},
            },
        ))
        tj_id = body["data"]["id"]
        print(f"       training_job_id = {tj_id}")

        # Poll training job until done
        j = poll(c, tj_id, "training", path="/api/v1/training-jobs/")
        assert j["status"] == "succeeded", j.get("error")
        assert j["best_metric"] is not None

        # Metrics
        body = step("metrics", c.get(f"/api/v1/training-jobs/{tj_id}/metrics"))
        items = body["data"]["items"]
        print(f"       metrics collected: {len(items)} epochs, last mAP50-95 = {items[-1]['map5095']}")
        assert len(items) >= 5

        # Artifacts
        body = step("artifacts", c.get(f"/api/v1/training-jobs/{tj_id}/artifacts"))
        arts = body["data"]["items"]
        print(f"       artifacts: {[a['name'] for a in arts]}")
        assert any(a["name"] == "best.pt" for a in arts), arts

        # Project status auto-advanced
        ps = step("project", c.get(f"/api/v1/projects/{project_id}"))["data"]["status"]
        print(f"       project status: {ps}")
        assert ps == "completed", ps

        # Cleanup
        step("cleanup", c.delete(f"/api/v1/projects/{project_id}"))

    print("\nPhase 5 end-to-end smoke test passed.")


if __name__ == "__main__":
    main()
