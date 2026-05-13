# AI Auto Training Platform

Single-user, self-hosted platform for end-to-end computer-vision training:
create projects, upload datasets (ZIP / loose files / CVAT — coming), analyze
dataset health, get parameter recommendations, train with Ultralytics YOLO
(detection / segmentation / classification), and watch live metrics in the
browser.

Architecture, schema, API contract, and roadmap live in
[`AI_Auto_Training_Platform_Architecture_Design.docx`](./AI_Auto_Training_Platform_Architecture_Design.docx).

## Stack

| Layer | Choice |
|---|---|
| Frontend | React 18 + Vite + TypeScript + Tailwind + TanStack Query + Recharts |
| Backend | FastAPI + Pydantic v2 + SQLAlchemy 2 (asyncpg) + Alembic |
| Database | Supabase Postgres (session pooler, port 5432) |
| Storage | Local FS (MinIO/S3-ready via `StorageBackend` interface) |
| Training | Ultralytics YOLO 8.3+, CPU-only by default |
| Jobs | FastAPI BackgroundTasks + jobs table (Celery-ready) |
| Realtime | Server-Sent Events |
| Deploy | Docker Compose |

## One-command bring-up

Requires Docker Desktop (or Docker Engine + Compose v2).

```bash
# 1. Configure
cp backend/.env.example backend/.env
# Edit backend/.env:
#   - DATABASE_URL : your Supabase session-pooler connection string
#   - API_TOKEN    : a random bearer token (python -c "import secrets; print(secrets.token_urlsafe(48))")

# 2. Build + run (dev mode with hot reload by default)
docker compose up --build

# Browse to:
#   http://localhost:5173    frontend
#   http://localhost:8000/docs   Swagger UI
```

Production-style (no source mounts, no hot reload):

```bash
docker compose -f docker-compose.yml up --build -d
```

Convenience targets in [`Makefile`](./Makefile):

```bash
make dev          # docker compose up --build
make prod         # production mode, detached
make logs         # tail both services
make migrate      # alembic upgrade head against the running api
make verify-db    # print schema status from inside the container
make down         # stop the stack
make clean        # remove containers + volumes + ./data (DESTRUCTIVE)
```

## First login

There is no signup screen. On the login page, paste the same `API_TOKEN`
you set in `backend/.env`. It's stored in `localStorage` and sent as
`Authorization: Bearer …` on every request.

## End-to-end flow

1. **Create project** → pick model family (`yolo`) and task type
   (`detection` / `segmentation` / `classification`).
2. **Upload dataset** → drag a `.zip` of images (+ optional `labels/*.txt`
   + `classes.txt`) into the dropzone. The background ingest detects the
   layout and creates a `v1 (raw)` version.
3. **Convert** → "Convert" button materializes a new
   `v2 (yolo-det / yolo-seg / yolo-cls)` version with a deterministic
   70/20/10 split and `data.yaml`.
4. **Analyze** → "Run analysis" computes counts, missing/empty labels,
   class distribution + Gini, duplicates (avg-hash), corrupt images,
   resolution stats, a 0–100 health score, and a ranked recommendation
   list. Project status auto-advances to `dataset_analyzed` (or
   `ready_for_training` if there are no blockers and score ≥ 60).
5. **Configure training** → form pre-filled from the recommendation
   engine (model size, epochs, imgsz, batch, lr0). Pick a converted
   version → Start.
6. **Watch live** → SSE-driven loss + mAP charts in the browser, log
   tail, progress bar, stop button. On success, `best.pt` shows up in
   the artifacts list with a one-click download.

## Repository layout

```
.
├── backend/                FastAPI app
│   ├── app/                code (api, services, models, schemas, storage, jobs, realtime)
│   ├── alembic/            migrations 0001..0004
│   ├── scripts/            smoke_phase{1..5}, verify_db, debug_env, make_fake_dataset
│   ├── Dockerfile
│   ├── .env.example
│   └── pyproject.toml
├── frontend/               React app
│   ├── src/                lib, components, layout, features (auth/projects/datasets/analysis/training/cvat/settings)
│   ├── Dockerfile          multi-stage node → nginx
│   ├── nginx.conf          serves SPA + proxies /api → api:8000 (SSE-safe)
│   └── package.json
├── docker-compose.yml
├── docker-compose.override.yml    dev mounts + hot reload
├── Makefile
└── AI_Auto_Training_Platform_Architecture_Design.docx
```

## Supabase setup recap

1. Project Settings → Database → Connection string → **Session** tab → copy.
2. Edit the scheme to `postgresql+asyncpg://...` and paste into
   `backend/.env` as `DATABASE_URL`.
3. Run `make migrate` to apply migrations 0001..0004.

## CVAT integration (Phase 6 — designed-in, not yet wired)

The architecture reserves space for CVAT today so the integration is
config-only later:

- **Types**: `src/lib/types.ts` already defines `CvatConnection` and
  `CvatImport`.
- **Routes**: `/projects/:id/cvat` and the placeholder tab in
  `/projects/:id/dataset`.
- **Settings page**: planned CVAT connections form is rendered and
  disabled with `Coming in Phase 6`.
- **DB**: `cvat_connections` and `cvat_imports` tables are documented in
  the design doc (migration 0005 will create them).
- **API**: the design doc spells out `POST /cvat/connections`, the
  project/task listing proxies, and the import job runner.

When Phase 6 ships, the frontend changes are: enable the disabled tab,
swap the placeholder forms for real hooks. No architectural rework.

## Real training (Ultralytics)

CPU-only training works out of the box once you install the optional dep:

```bash
docker compose exec api pip install -e ".[training]"
# Or bake into the image by uncommenting the line in backend/Dockerfile.
```

Or run with the **mock trainer** (no Ultralytics needed, fakes metrics) to
smoke-test the wiring:

```bash
docker compose exec -e TRAINING_MOCK=1 api uvicorn app.main:app --reload
```

## Useful endpoints (Swagger at `/docs`)

```
GET    /api/v1/healthz
GET    /api/v1/readyz
GET    /api/v1/projects
POST   /api/v1/projects
GET    /api/v1/projects/{id}/timeline
POST   /api/v1/projects/{id}/datasets
POST   /api/v1/datasets/{id}/upload-zip
POST   /api/v1/datasets/{id}/convert
GET    /api/v1/datasets/{id}
POST   /api/v1/dataset-versions/{id}/analyze
GET    /api/v1/dataset-versions/{id}/analysis
GET    /api/v1/dataset-versions/{id}/recommendations
POST   /api/v1/dataset-versions/{id}/training-recommendation
POST   /api/v1/projects/{id}/training-jobs
GET    /api/v1/training-jobs/{id}
GET    /api/v1/training-jobs/{id}/metrics
GET    /api/v1/training-jobs/{id}/artifacts
GET    /api/v1/training-jobs/{id}/artifacts/{aid}/download
POST   /api/v1/training-jobs/{id}/stop
GET    /api/v1/sse/training/{id}
GET    /api/v1/jobs/{id}
```
