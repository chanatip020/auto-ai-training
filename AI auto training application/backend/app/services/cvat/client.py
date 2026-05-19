"""Async CVAT REST client.

Targets CVAT 2.x API. The methods we need:
  - POST   /api/auth/login                            obtain token from username + password
  - GET    /api/server/about                          connection probe
  - GET    /api/projects                              list projects
  - GET    /api/tasks?project_id=…                    list tasks
  - POST   /api/projects/{id}/dataset/export?format=… kick off async export
  - GET    /api/requests/{rq_id}                      poll export status
  - GET    {result_url} or                            download finished ZIP
           /api/projects/{id}/dataset?action=download
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import httpx
from loguru import logger
from tenacity import (
    AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential,
)

from app.core.errors import AppError


DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
RETRY_ON_STATUSES = {429, 500, 502, 503, 504}


class CvatClient:
    """One CVAT client per active connection. Use as an async context manager."""

    def __init__(self, *, base_url: str, username: str, secret: str):
        self.base_url = base_url.rstrip("/")
        self._username = username
        self._secret = secret  # token or password
        self._token: str | None = None
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            base_url=self.base_url, timeout=DEFAULT_TIMEOUT, follow_redirects=True,
        )
        # If the secret looks like a CVAT API token (length 40+, alphanumeric),
        # use it directly. Otherwise treat it as a password and login.
        if len(self._secret) >= 40 and self._secret.isalnum():
            self._token = self._secret
        else:
            await self._login()
        return self

    async def __aexit__(self, *_):
        if self._client:
            await self._client.aclose()

    @property
    def auth_header(self) -> dict[str, str]:
        if not self._token:
            return {}
        return {"Authorization": f"Token {self._token}"}

    async def _login(self) -> None:
        """POST /api/auth/login → store Token <key>."""
        assert self._client
        resp = await self._client.post(
            "/api/auth/login",
            json={"username": self._username, "password": self._secret},
        )
        if resp.status_code != 200:
            raise AppError(
                "CVAT_AUTH_FAILED",
                f"CVAT login failed ({resp.status_code}): {resp.text[:200]}",
                status_code=401,
            )
        data = resp.json()
        self._token = data.get("key") or data.get("token") or ""
        if not self._token:
            raise AppError("CVAT_AUTH_NO_TOKEN", "CVAT login returned no token.", 502)

    async def _retry_get(self, path: str, **kwargs) -> httpx.Response:
        """GET with exponential-backoff retries on 5xx / 429."""
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=1, min=1, max=30),
            retry=retry_if_exception_type(
                (httpx.TransportError, httpx.RemoteProtocolError, RetryableStatus),
            ),
            reraise=True,
        ):
            with attempt:
                assert self._client
                r = await self._client.get(path, headers=self.auth_header, **kwargs)
                if r.status_code in RETRY_ON_STATUSES:
                    raise RetryableStatus(f"{path}: HTTP {r.status_code}")
                return r
        raise AppError("CVAT_RETRIES_EXHAUSTED", f"Could not reach {path}", 502)

    # ---- probes ----
    async def about(self) -> dict[str, Any]:
        r = await self._retry_get("/api/server/about")
        if r.status_code != 200:
            raise AppError("CVAT_ABOUT_FAILED",
                           f"GET /api/server/about → {r.status_code}", 502)
        return r.json()

    # ---- lists ----
    async def list_projects(self, *, page_size: int = 100) -> list[dict[str, Any]]:
        r = await self._retry_get(f"/api/projects?page_size={page_size}")
        if r.status_code != 200:
            raise AppError("CVAT_LIST_PROJECTS_FAILED",
                           f"HTTP {r.status_code}", 502)
        body = r.json()
        return body.get("results", body if isinstance(body, list) else [])

    async def list_tasks(self, *, project_id: int | None = None,
                         page_size: int = 100) -> list[dict[str, Any]]:
        params = f"?page_size={page_size}"
        if project_id is not None:
            params += f"&project_id={project_id}"
        r = await self._retry_get(f"/api/tasks{params}")
        if r.status_code != 200:
            raise AppError("CVAT_LIST_TASKS_FAILED",
                           f"HTTP {r.status_code}", 502)
        body = r.json()
        return body.get("results", body if isinstance(body, list) else [])

    # ---- export ----
    async def request_export(self, *, source: str, source_id: int,
                             format: str = "YOLO 1.1") -> str:
        """Start an async dataset export. Returns the rq_id to poll.

        `source` is 'project' or 'task' (matches CVAT URL plural form).
        """
        plural = "projects" if source == "project" else "tasks"
        assert self._client
        r = await self._client.post(
            f"/api/{plural}/{source_id}/dataset/export",
            headers=self.auth_header,
            params={"format": format, "save_images": "true"},
        )
        if r.status_code not in (200, 202):
            raise AppError(
                "CVAT_EXPORT_REQUEST_FAILED",
                f"POST /api/{plural}/{source_id}/dataset/export → {r.status_code}: {r.text[:200]}",
                502,
            )
        body = r.json()
        rq_id = body.get("rq_id") or body.get("id")
        if not rq_id:
            raise AppError("CVAT_NO_RQ_ID", "Export response missing rq_id.", 502)
        return rq_id

    async def poll_request(self, rq_id: str) -> dict[str, Any]:
        """Poll an async request. Caller is responsible for loop + backoff."""
        r = await self._retry_get(f"/api/requests/{rq_id}")
        if r.status_code != 200:
            raise AppError("CVAT_POLL_FAILED",
                           f"GET /api/requests/{rq_id} → {r.status_code}", 502)
        return r.json()

    async def stream_download(self, url: str) -> AsyncIterator[bytes]:
        """Stream a finished export download."""
        assert self._client
        async with self._client.stream("GET", url, headers=self.auth_header) as resp:
            if resp.status_code != 200:
                raise AppError("CVAT_DOWNLOAD_FAILED",
                               f"GET {url} → {resp.status_code}", 502)
            async for chunk in resp.aiter_bytes():
                yield chunk


class RetryableStatus(Exception):
    """Used internally to trigger tenacity retries on 5xx / 429."""


@asynccontextmanager
async def client_from(connection) -> AsyncIterator[CvatClient]:
    """Build a CvatClient from a CvatConnection ORM row."""
    from app.core.crypto import decrypt
    secret = decrypt(connection.encrypted_secret)
    async with CvatClient(
        base_url=connection.base_url,
        username=connection.username,
        secret=secret,
    ) as c:
        yield c
