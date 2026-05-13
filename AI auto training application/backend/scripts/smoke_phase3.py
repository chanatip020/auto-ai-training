"""End-to-end smoke test for Phase 3 (format conversion).

Prereqs:
    alembic upgrade head
    python scripts/make_fake_dataset.py --out fake.zip --n 10
    uvicorn app.main:app --reload --port 8000   (other terminal)

Then:
    python scripts/smoke_phase3.py
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


def poll(c, job_id, label):
    print(f"       polling job {job_id} ({label})...")
    for _ in range(60):
        time.sleep(1)
        j = step("poll", c.get(f"/api/v1/jobs/{job_id}"))["data"]
        print(f"       status={j['status']:10s}  progress={j['progress']:>3d}%  msg={j['message']}")
        if j["status"] in ("succeeded", "failed", "cancelled"):
            return j
    sys.exit(f"Job {job_id} did not finish in 60s")


def main() -> None:
    if not ZIP_PATH.exists():
        print(f"Missing {ZIP_PATH}. Run: python scripts/make_fake_dataset.py --out {ZIP_PATH} --n 10")
        sys.exit(2)

    print(f"API: {BASE}\nZIP: {ZIP_PATH}\n")

    with httpx.Client(base_url=BASE, headers=HEADERS, timeout=60) as c:
        # 1. Project + dataset
        project_id = step("create project", c.post("/api/v1/projects", json={
            "name": "Phase 3 smoke", "description": "", "model_family": "yolo", "task_type": "detection",
        }))["data"]["id"]
        dataset_id = step("create dataset", c.post(f"/api/v1/projects/{project_id}/datasets", json={
            "name": "fake-yolo", "source": "upload",
        }))["data"]["id"]

        # 2. Upload + ingest
        with open(ZIP_PATH, "rb") as f:
            job_id = step("upload zip", c.post(
                f"/api/v1/datasets/{dataset_id}/upload-zip",
                files={"file": (ZIP_PATH.name, f, "application/zip")},
            ))["data"]["job_id"]
        j = poll(c, job_id, "ingest")
        assert j["status"] == "succeeded"

        # 3. Convert to yolo-det
        job_id = step("start conversion", c.post(
            f"/api/v1/datasets/{dataset_id}/convert",
            json={"format": "yolo-det"},   # default 70/20/10, classes from classes.txt
        ))["data"]["job_id"]
        j = poll(c, job_id, "convert")
        assert j["status"] == "succeeded", j.get("error")

        # 4. Inspect: two versions now (v1 raw, v2 yolo-det)
        body = step("get dataset", c.get(f"/api/v1/datasets/{dataset_id}"))
        versions = body["data"]["versions"]
        assert len(versions) == 2, versions
        latest = versions[0]
        print(f"       latest v{latest['version']} format={latest['format']}")
        print(f"       classes={latest['classes']}  images={latest['num_images']}  labels={latest['num_labels']}")
        print(f"       summary={latest['summary']}")
        assert latest["format"] == "yolo-det"
        assert latest["summary"]["counts"]["train"] > 0

        # 5. Cleanup
        step("delete project", c.delete(f"/api/v1/projects/{project_id}"))

    print("\nPhase 3 end-to-end smoke test passed.")


if __name__ == "__main__":
    main()
