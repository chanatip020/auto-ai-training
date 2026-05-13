"""End-to-end smoke test for Phase 2 (dataset upload).

Prereqs:
    1. alembic upgrade head  — applies 0001 + 0002 to your Supabase DB
    2. uvicorn app.main:app --reload --port 8000  — running in another terminal
    3. python scripts/make_fake_dataset.py --out fake.zip  — to make a sample

Then:
    python scripts/smoke_phase2.py
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


def step(name: str, response: httpx.Response) -> dict:
    body = response.json() if response.content else {}
    ok = response.is_success
    icon = "OK  " if ok else "FAIL"
    print(f"[{icon}] {response.request.method:6s} {response.request.url.path}  -> {response.status_code}  ({name})")
    if not ok:
        print(f"       body: {body}")
        sys.exit(1)
    return body


def main() -> None:
    if not ZIP_PATH.exists():
        print(f"Missing {ZIP_PATH}. Run: python scripts/make_fake_dataset.py --out {ZIP_PATH}")
        sys.exit(2)

    print(f"API:      {BASE}")
    print(f"Token:    {settings.API_TOKEN[:8]}…")
    print(f"ZIP:      {ZIP_PATH}  ({ZIP_PATH.stat().st_size} bytes)")
    print()

    with httpx.Client(base_url=BASE, headers=HEADERS, timeout=60) as c:
        # 1. Create project
        body = step("create project", c.post("/api/v1/projects", json={
            "name": "Phase 2 smoke",
            "description": "Created by scripts/smoke_phase2.py",
            "model_family": "yolo",
            "task_type": "detection",
        }))
        project_id = body["data"]["id"]

        # 2. Create dataset shell
        body = step("create dataset", c.post(f"/api/v1/projects/{project_id}/datasets", json={
            "name": "fake-yolo",
            "source": "upload",
        }))
        dataset_id = body["data"]["id"]

        # 3. Upload ZIP
        with open(ZIP_PATH, "rb") as f:
            body = step(
                "upload zip",
                c.post(
                    f"/api/v1/datasets/{dataset_id}/upload-zip",
                    files={"file": (ZIP_PATH.name, f, "application/zip")},
                ),
            )
        job_id = body["data"]["job_id"]

        # 4. Poll job until done (max 30s)
        print(f"       polling job {job_id}...")
        for _ in range(30):
            time.sleep(1)
            body = step("poll job", c.get(f"/api/v1/jobs/{job_id}"))
            j = body["data"]
            print(f"       status={j['status']:10s}  progress={j['progress']:>3d}%  msg={j['message']}")
            if j["status"] in ("succeeded", "failed", "cancelled"):
                break
        if j["status"] != "succeeded":
            print(f"       error: {j.get('error')}")
            sys.exit(1)

        # 5. Verify dataset detail (should now have a version 1)
        body = step("get dataset", c.get(f"/api/v1/datasets/{dataset_id}"))
        versions = body["data"]["versions"]
        assert versions, "expected at least one dataset_version"
        v = versions[0]
        print(f"       version v{v['version']}  format={v['format']}")
        print(f"       images={v['num_images']}  labels={v['num_labels']}  classes={v['classes']}")
        print(f"       summary={v['summary']}")

        # 6. Project status should have auto-transitioned
        body = step("project status", c.get(f"/api/v1/projects/{project_id}"))
        ps = body["data"]["status"]
        print(f"       project status now: {ps}")
        assert ps == "dataset_uploaded", f"expected dataset_uploaded, got {ps}"

        # 7. Timeline contains the events
        body = step("timeline", c.get(f"/api/v1/projects/{project_id}/timeline"))
        events = [e["event"] for e in body["data"]["items"]]
        print(f"       events: {events}")
        for required in ("project.created", "dataset.created", "dataset.uploaded", "project.status_changed"):
            assert required in events, f"missing event: {required}"

        # 8. Cleanup
        step("delete project", c.delete(f"/api/v1/projects/{project_id}"))

    print()
    print("Phase 2 end-to-end smoke test passed.")


if __name__ == "__main__":
    main()
