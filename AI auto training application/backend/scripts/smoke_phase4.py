"""End-to-end smoke test for Phase 4 (analysis + recommendations).

Prereqs:
    alembic upgrade head     # applies 0001..0003
    pip install -e .         # picks up new pillow / pyyaml deps
    uvicorn app.main:app --reload --port 8000   (other terminal)
    python scripts/make_fake_dataset.py --out fake.zip --n 10
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

    with httpx.Client(base_url=BASE, headers=HEADERS, timeout=60) as c:
        project_id = step("create project", c.post("/api/v1/projects", json={
            "name": "Phase 4 smoke", "description": "", "model_family": "yolo", "task_type": "detection",
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

        # Find the converted version
        body = step("get dataset", c.get(f"/api/v1/datasets/{dataset_id}"))
        version = next(v for v in body["data"]["versions"] if v["format"] == "yolo-det")
        version_id = version["id"]
        print(f"       converted version: {version_id} (v{version['version']})")

        # Run analysis
        jid = step("start analysis", c.post(
            f"/api/v1/dataset-versions/{version_id}/analyze",
        ))["data"]["job_id"]
        j = poll(c, jid, "analyze")
        assert j["status"] == "succeeded", j.get("error")

        # Inspect analysis
        body = step("get analysis", c.get(f"/api/v1/dataset-versions/{version_id}/analysis"))
        a = body["data"]
        print(f"       health_score   : {a['health_score']}")
        print(f"       ready_training : {a['ready_for_training']}")
        print(f"       recommendations:")
        for r in a["recommendations"]:
            print(f"         [{r['severity']:7s}] {r['code']:25s} {r['message']}")

        # Recommendations endpoint
        body = step("recommendations", c.get(f"/api/v1/dataset-versions/{version_id}/recommendations"))
        print(f"       total recs: {len(body['data']['items'])}, ready={body['data']['ready_for_training']}")

        # Training-param recommendation
        body = step("training rec", c.post(
            f"/api/v1/dataset-versions/{version_id}/training-recommendation",
            json={"gpu_mem_gb": 0},
        ))
        tr = body["data"]
        print(f"       suggested params: model={tr['params']['model']} epochs={tr['params']['epochs']} "
              f"imgsz={tr['params']['imgsz']} batch={tr['params']['batch']}")

        # Verify project status auto-transitioned
        body = step("project status", c.get(f"/api/v1/projects/{project_id}"))
        ps = body["data"]["status"]
        print(f"       project status: {ps}")
        assert ps in ("dataset_analyzed", "ready_for_training"), ps

        step("cleanup", c.delete(f"/api/v1/projects/{project_id}"))

    print("\nPhase 4 end-to-end smoke test passed.")


if __name__ == "__main__":
    main()
