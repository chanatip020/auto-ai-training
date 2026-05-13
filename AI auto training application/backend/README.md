# AI Auto Training Platform — Backend

FastAPI service for the AI Auto Training Platform. Phase 0 + 1: foundations and project management.

## Quick start (local)

```bash
# 1. Create venv and install
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e .[dev]

# 2. Configure
cp .env.example .env
# Edit .env — set DATABASE_URL to your Supabase Postgres connection string
# and API_TOKEN to a strong random value.

# 3. Run migrations
alembic upgrade head

# 4. Run the API
uvicorn app.main:app --reload --port 8000

# 5. Open OpenAPI docs
# http://localhost:8000/docs
```

## Quick start (Docker)

From the repo root:

```bash
docker-compose up --build
```

The API will be available at `http://localhost:8000`. Migrations run automatically on container start (see `docker-compose.yml`).

## Auth (v1)

Single-user mode uses a static bearer token. Send every request with:

```
Authorization: Bearer <API_TOKEN>
```

The auth dependency is already abstracted (`app/core/security.py`) so JWT/RBAC can be dropped in later without touching routers.

## Project status state machine

`created` → `dataset_uploaded` → `dataset_analyzed` → `ready_for_training` → `training` → `completed` / `failed`

`ProjectService.compute_status` reduces the latest dataset/training rows into the enum value above. v1 only has projects + audit log, so transitions are driven by manual API calls; later phases (datasets, training) will move them automatically.

## Layout

```
app/
├── main.py            FastAPI app factory
├── config.py          Pydantic Settings
├── db.py              Async SQLAlchemy engine + session
├── deps.py            FastAPI dependencies (auth, db)
├── core/              Cross-cutting: logging, errors, security
├── api/v1/            REST routers (health, projects)
├── models/            SQLAlchemy ORM
├── schemas/           Pydantic request/response models
└── services/          Business logic (Projects, Audit)
alembic/               DB migrations
```
