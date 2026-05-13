"""End-to-end smoke test for the v1 Projects API.

Spin up the API in one terminal:
    uvicorn app.main:app --reload --port 8000

Then run this in another:
    python scripts/smoke_api.py
"""
from __future__ import annotations

import os
import sys

import httpx

from app.config import settings

BASE = os.environ.get("API_BASE", "http://localhost:8000")
HEADERS = {"Authorization": f"Bearer {settings.API_TOKEN}"}


def step(name: str, response: httpx.Response) -> dict:
    body = response.json() if response.content else {}
    ok = response.is_success
    icon = "OK" if ok else "FAIL"
    print(f"[{icon}] {response.request.method:6s} {response.request.url.path}  -> {response.status_code}  ({name})")
    if not ok:
        print(f"       body: {body}")
        sys.exit(1)
    return body


def main() -> None:
    print(f"API: {BASE}")
    print(f"Token: {settings.API_TOKEN[:8]}…")
    print()

    with httpx.Client(base_url=BASE, headers=HEADERS, timeout=15) as c:
        # Health
        step("liveness", c.get("/api/v1/healthz"))
        step("readiness", c.get("/api/v1/readyz"))

        # Create
        body = step("create project", c.post("/api/v1/projects", json={
            "name": "Smoke test project",
            "description": "Created by scripts/smoke_api.py",
            "model_family": "yolo",
            "task_type": "detection",
        }))
        pid = body["data"]["id"]
        print(f"       project_id = {pid}")

        # List
        body = step("list projects", c.get("/api/v1/projects?limit=5"))
        print(f"       total visible: {body['data']['total']}")

        # Get
        step("get project", c.get(f"/api/v1/projects/{pid}"))

        # Patch
        step("rename project", c.patch(f"/api/v1/projects/{pid}", json={
            "name": "Smoke test project (renamed)",
        }))

        # Transition
        step("transition status", c.post(f"/api/v1/projects/{pid}/status", json={
            "status": "dataset_uploaded",
        }))

        # Timeline
        body = step("timeline", c.get(f"/api/v1/projects/{pid}/timeline"))
        events = [e["event"] for e in body["data"]["items"]]
        print(f"       events: {events}")

        # Cleanup
        step("delete project", c.delete(f"/api/v1/projects/{pid}"))

    print()
    print("All endpoints work end-to-end.")


if __name__ == "__main__":
    sys.path.insert(0, ".")
    main()
