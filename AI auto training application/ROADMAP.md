# Roadmap — AI Auto Training Platform

**State today:** Phases 0–5 are shipped end-to-end (project management, dataset
upload, format conversion, dataset analysis + rules engine, training with
live SSE charts), plus Docker compose and the frontend MVP. Architecture
[design doc](./AI_Auto_Training_Platform_Architecture_Design.docx).

**Ordering principle:** small effort → large effort. Earlier phases are
quick wins that unlock the larger ones. Most early items are 3–7 days; the
AI-agent and active-learning items at the end are multi-week.

**How to use this:** each phase below has *Motivation → Deliverables →
Schema/API changes → Gotchas → Estimated time → Depends on*. Pick the
next one you have appetite for and read just its section.

---

## Quick scoreboard

| # | Phase | Scale | Idea source | Est. |
|---|---|---|---|---|
| 7 | Tests + CI | S | foundations | 1w |
| 8 | Training history + params persistence | S–M | **you #1** | 1w |
| 9 | Augmentation preview | S | UX win | 3d |
| 10 | Inference endpoint + ONNX export | M | makes models usable | 1w |
| 11 | MLflow tracking | M | **you #4** | 4d |
| 12 | CVAT integration | M | **you #2** | 1w |
| 13 | Storage backend: MinIO/S3 | M | scale | 3d |
| 14 | Observability stack | M–L | production-readiness | 1w |
| 15 | Multi-user + RBAC | L | growth | 2w |
| 16 | AI agent — dataset analysis | L | **you #3** | 2w |
| 17 | AI agent — performance review | L | **you #5** | 2w |
| 18 | Hyperparameter optimization (sweep) | L | quality | 3w |
| 19 | Active learning loop | XL | endgame | 4w |

---

## Phase 7 — Tests + CI  *(small, high leverage)*

### Motivation
Every phase below is dangerous without a green test suite. We've shipped
six phases worth of features verified by smoke scripts. Time to lock that in.

### Deliverables
- `backend/tests/` — pytest with async fixtures
  - Postgres via testcontainers OR in-memory + SQLAlchemy SQLite fallback
  - Per-service unit tests (split, detect, score, recommend)
  - One end-to-end test per phase reusing existing smoke flows
- `frontend/tests/` — Vitest + React Testing Library
  - Component tests for the hooks (`useUploadZip`, `useJob`, etc.)
  - Page tests with MSW mocking the API
- `.github/workflows/ci.yml` — runs both on PR
- `make test` target

### Gotchas
- Postgres ENUM types in tests: use the same `create_type=False` pattern so
  test sessions don't try to recreate them.
- The file-write sync issue we've hit during this build is a one-machine
  artifact and won't appear in CI.

### Est. 1 week  |  Depends on: nothing

---

## Phase 8 — Training history + params persistence *(your idea #1)*

### Motivation
You already have `training_jobs.params` and `training_metrics` in the DB,
but there's no UI to compare runs side-by-side. Without comparability,
none of the AI-agent phases later can reason about "what worked last time".

### Deliverables
- `GET /api/v1/projects/{id}/training-history` — paginated list with
  filters (status, model, date range)
- `GET /api/v1/training-jobs/{id}/clone-as-config` — returns a params dict
  ready to POST to start a new run
- Optional: `summary` JSONB column on `training_jobs` for cheap aggregate
  queries (best_map5095, total_time_s, peak_gpu_mem, etc.)
- Frontend `TrainingHistoryPage`:
  - Sortable table of runs (date, model, epochs, best mAP, status)
  - Click row → side-by-side params diff vs another selected run
  - "Re-run with these params" button → pre-fills TrainingStartPage
  - Per-project trend chart (best mAP over time) via Recharts

### Schema/API
```sql
-- Optional migration 0005:
alter table training_jobs add column summary jsonb default '{}'::jsonb;
-- After each completed run, the runner writes the summary block
-- (best_metric, total_time_s, n_epochs_completed, hardware_info).
```

### Gotchas
- "Re-run with these params" must NOT re-use the same `dataset_version_id`
  if it no longer exists — fall back to "latest converted" in the UI.
- The diff view needs careful float rounding (0.937 ≈ 0.937000001) — reuse
  the `equalParam` tolerance pattern from TrainingStartPage.

### Est. 1 week  |  Depends on: Phase 7

---

## Phase 9 — Augmentation preview *(small, immediate UX win)*

### Motivation
Right now the user sees `mosaic=1.0, mixup=0.1` and has to take it on faith.
A visual preview makes the tuning loop 10× faster.

### Deliverables
- `POST /api/v1/dataset-versions/{id}/preview-augmentation`
  - Body: same param shape as training start
  - Server picks 9 random training images, applies Ultralytics' augmentation
    pipeline once, returns a 3×3 grid PNG (or JSON of 9 data URIs)
- Frontend: when the "Augmentation" Collapsible is expanded, a small
  "Preview augmentation" button below the params shows the grid

### Schema/API
No DB changes. The preview is ephemeral.

### Gotchas
- Caching: don't regenerate on every keystroke. Debounce 1s.
- Augmentation is random — preview shows ONE realization. Add a
  "Reshuffle" button.

### Est. 3 days  |  Depends on: existing dataset versions

---

## Phase 10 — Inference endpoint + ONNX export *(medium)*

### Motivation
Trained models live in `data/runs/{id}/weights/best.pt` and never get used.
Without inference, the platform is a graveyard. With it, it's a product.

### Deliverables
- `POST /api/v1/training-jobs/{id}/predict` — upload 1–N images, return
  bboxes/polygons/labels JSON
- `POST /api/v1/training-jobs/{id}/export?format=onnx|torchscript|engine|coreml`
  - Ultralytics has built-in `model.export(format=…)`; thin wrapper
  - Async — returns a job_id, exported file shows in artifacts list
- Frontend: a "Try it" tab on the TrainingMonitorPage (Phase 5 already has
  the artifacts table — add a drag-zone for one-off inference)

### Gotchas
- The inference container needs `[training]` extras installed (torch). If
  you only baked them in the training-time image, split into two services
  or always include them.
- Lazy-load the model into memory on first request; keep an LRU cache so
  repeat predictions don't reload from disk.

### Est. 1 week  |  Depends on: Phase 5 (already shipped)

---

## Phase 11 — MLflow tracking *(your idea #4)*

### Motivation
We already have `training_metrics` in our DB. MLflow adds: side-by-side run
comparison UI, artifact lineage, plugin ecosystem (S3, Azure ML, etc.),
and credibility with ML teams who already use it.

### Deliverables
- Add `mlflow` service to docker-compose (UI on :5000)
- Extend `services/training/callbacks.py`:
  - On run start: `mlflow.start_run(run_name=tj.id)`
  - On each epoch: `mlflow.log_metric("map5095", v, step=epoch)` (in addition
    to our DB row)
  - On finish: `mlflow.log_artifact("best.pt")`, `mlflow.log_dict(params)`
- DB: add `mlflow_run_id` column on `training_jobs` so we can link out
- Frontend: "Open in MLflow ↗" link on the TrainingMonitorPage

### Gotchas
- MLflow tracking server needs persistent storage. Mount a volume.
- Network: if MLflow runs in compose, log to `http://mlflow:5000`. If it's
  cloud-hosted, use `MLFLOW_TRACKING_URI` env.

### Est. 4 days  |  Depends on: Phase 5

---

## Phase 12 — CVAT integration *(your idea #2)*

### Motivation
We already designed for it: types, placeholder pages, planned endpoints, DB
tables in the design doc. This is the cleanest large-feature addition.

### Deliverables
- Migration 0005 (or whatever number we're on): `cvat_connections`,
  `cvat_imports`
- `backend/app/services/cvat/`
  - `client.py` — httpx async client with `tenacity` retries
  - `importer.py` — async import job that calls
    `POST /api/projects/{id}/dataset/export?format=YOLO 1.1`, polls
    `/api/requests/{rq_id}` until done, downloads the ZIP, hands off to
    `services/datasets/ingest.py:run_ingest_zip`
- Endpoints:
  - `POST /api/v1/cvat/connections`
  - `GET /api/v1/cvat/connections/{id}/projects` (proxied + cached)
  - `GET /api/v1/cvat/connections/{id}/tasks`
  - `POST /api/v1/projects/{pid}/cvat-imports`
  - `GET /api/v1/cvat-imports/{id}`
- Frontend: enable the disabled tab on `DatasetUploadPage`, wire the planned
  forms in `SettingsPage`

### Gotchas
- Encrypt CVAT tokens at rest — use Fernet with a key in `backend/.env`.
- CVAT versions differ wildly. Test against your target CVAT version first;
  support whatever export format that version emits cleanly.
- Resumable imports: store the last successful step in `cvat_imports.payload`
  so retry can pick up where it left off.

### Est. 1 week  |  Depends on: nothing critical

---

## Phase 13 — Storage backend: MinIO / S3 *(medium)*

### Motivation
`data/` will fill local disk fast once you have a few large datasets +
training artifacts. The `StorageBackend` Protocol already exists — we just
need real implementations.

### Deliverables
- `backend/app/storage/s3.py` — `S3Storage(StorageBackend)` using `boto3`.
  Same code works for AWS S3, MinIO, Cloudflare R2, etc.
- `backend/app/storage/minio.py` — thin wrapper that just points S3Storage
  at the MinIO endpoint
- `backend/app/scripts/storage_migrate.py` — streams files from one backend
  to another, updates `storage_uri` rows in a single transaction per
  dataset_version
- Add MinIO to docker-compose (optional service)
- Settings: `STORAGE_BACKEND=s3 S3_BUCKET=… S3_ENDPOINT_URL=…`

### Gotchas
- Presigned URLs for downloads — replace `FileResponse` paths with
  presigned redirects. Frontend stays the same (it just follows the link).
- The migration script must be **idempotent** — interrupted runs should resume.

### Est. 3 days  |  Depends on: nothing

---

## Phase 14 — Observability stack *(medium-large)*

### Motivation
Once external users hit the platform, "it broke" with no traceback is the
default failure mode. Triage time matters more than feature velocity here.

### Deliverables
- OpenTelemetry tracing (FastAPI + SQLAlchemy + httpx auto-instrumentation)
  → Jaeger or Grafana Tempo
- Prometheus metrics — request rate, p50/p95/p99 latency, error rate, job
  durations broken down by `JobKind`. Use `prometheus-fastapi-instrumentator`.
- Sentry for backend exceptions (covers the unhandled-exception handler we
  built) and frontend errors
- Audit log review: ensure every blocker has actionable context (the
  `details` dict on `ApiError` is your friend)

### Est. 1 week  |  Depends on: production deployment

---

## Phase 15 — Multi-user + RBAC *(large)*

### Motivation
v1 was deliberately single-user (one static API_TOKEN). Anything you'd want
to share with a team needs real auth.

### Deliverables
- Swap `core/security.py:current_user` for JWT (FastAPI-Users or
  Supabase Auth — the latter integrates with your existing Supabase project)
- Roles: `admin` (all projects), `member` (own projects only). Add `role`
  column on `users`.
- Frontend: signup/login pages replacing the token-paste screen
- `/settings/users` admin page

### Gotchas
- We already have `user_id` on `projects`. The list/get filters already
  enforce ownership. So the schema change is small — the *new* work is
  auth UX + role-gated routes.

### Est. 2 weeks  |  Depends on: Phase 7 (don't ship auth without tests)

---

## Phase 16 — AI agent: dataset analysis *(your idea #3)*

### Motivation
The rules engine in `services/recommend/dataset.py` catches the *known*
failure modes. An LLM agent can spot patterns the rules don't — "your
'car' class images are all dashcam, but the val set has aerial shots —
your test mAP will look great until production".

### Architecture
```
┌── POST /api/v1/dataset-versions/{id}/agent-analyze ──┐
│                                                       │
│  → spawn agent runner (background job)                │
│  → LLM (Claude/GPT-4) with these TOOLS:               │
│       - get_findings()       → run_all_checks output  │
│       - get_recommendations()→ rules engine output    │
│       - sample_images(class, n) → returns N image     │
│         data URIs from a class                        │
│       - get_db_stats()       → COUNT(*), histograms   │
│       - search_past_runs(project_id)                  │
│         → results from Phase 8 history                │
│  → agent streams its reasoning + final report         │
│  → persisted to `agent_runs` table (full transcript   │
│    so we can audit / retrain later)                   │
└──────────────────────────────────────────────────────┘
```

### Deliverables
- `services/agents/dataset_analyst.py` — agent loop with tool registry
- `agent_runs` table: id, dataset_version_id, model_name, transcript jsonb,
  recommendations jsonb, created_at
- SSE stream of the agent's thinking so the UI feels responsive
- Frontend `AnalysisPage` gets an "Ask AI" panel below recommendations

### Gotchas
- **Cost**: each agent invocation could be 50K+ tokens with images.
  Cache previous runs by content hash of `findings`.
- **Trust calibration**: the LLM will hallucinate causes. Show its outputs
  in a "suggestions" frame distinct from the deterministic rules.
- **Sampling**: don't let it look at every image in a million-image dataset.
  Cap samples per call to 16 and let it choose strategically.

### Est. 2 weeks  |  Depends on: Phase 8 (history), Phase 11 (MLflow optional)

---

## Phase 17 — AI agent: performance review *(your idea #5)*

### Motivation
After Phase 16, you have agent tooling. After Phase 8, you have training
history. Combine them: after each training completes, an agent compares the
result to the project's history and tells the user what to try next.

### Architecture
Same agent framework as Phase 16, but with a different toolset:
- `get_training_job(id)`, `list_past_jobs(project_id)`
- `get_metrics(job_id)`, `get_confusion_matrix(job_id)` (returns image)
- `get_dataset_findings(version_id)` — to correlate
- `propose_params(deltas)` — outputs a params dict the user can one-click apply

### Deliverables
- `services/agents/performance_reviewer.py`
- `POST /api/v1/training-jobs/{id}/agent-review`
- Frontend: `TrainingMonitorPage/results` tab adds an "AI review" card
  with the agent's diagnosis + a "Apply these params and re-train" button

### Gotchas
- Don't run the agent automatically on every training — cost. Trigger on
  user click, OR only on `succeeded` runs (skip failures).

### Est. 2 weeks  |  Depends on: Phase 8, Phase 16

---

## Phase 18 — Hyperparameter optimization (sweep) *(large)*

### Motivation
Manual tuning hits a ceiling. Optuna or Ray Tune can search a space of
{lr, batch, optimizer, augmentation} and find configs no human would try.

### Deliverables
- `services/training/sweep.py` — Optuna study runner
  - User defines a search space in the UI (or a JSON config)
  - Spawns N trial training jobs sequentially (or in parallel if GPU
    available)
  - Each trial uses pruning so bad runs get killed early
- `sweep_jobs` table: parent record; each trial is a normal `training_jobs`
  row with `sweep_id` foreign key
- Frontend "Sweep" tab on the training page — parallel coordinate plot of
  trials (Recharts can't do this; consider Plotly via dynamic import)

### Gotchas
- Heaviest compute requirement in the whole roadmap. Don't try this on CPU.
- Define the search space *carefully* — `lr ∈ [1e-5, 10]` will waste
  trials. `lr ∈ [1e-4, 1e-2]` log-scale is usually right.

### Est. 3 weeks  |  Depends on: Phase 8, ideally a GPU

---

## Phase 19 — Active learning loop *(extra-large; the endgame)*

### Motivation
Most labels in real datasets are wasted: the model already knows them. The
high-value labels are at the decision boundary. Active learning surfaces
exactly those.

### Workflow
```
1. User runs inference on a pool of UNLABELED images
2. Backend records prediction + uncertainty (e.g. entropy of softmax)
3. Top-K uncertain images get pushed to CVAT for human review (uses Phase 12)
4. Once labeled, they merge back into the training set
5. New training run picks them up automatically
6. Loop until model plateaus
```

### Deliverables
- Inference enhancements (Phase 10): also return uncertainty per prediction
- Background job: `services/active/uncertainty_sampler.py`
- Push-to-CVAT integration (reverse of Phase 12 import — we now PUSH images
  to CVAT for labeling)
- `active_rounds` table tracking loop iterations + metrics improvements

### Est. 4 weeks  |  Depends on: Phases 10, 12

---

## Cross-cutting habits

### `DECISIONS.md` log
For every PR-sized change, append one paragraph: *what changed, why,
trade-off, alternatives considered.* In a year, this is your most valuable
document. Already required by your `CLAUDE.md`.

### "How-to" templates in `CONTRIBUTING.md`
Write these once, save hours forever:
1. **How to add a new background job kind**
   - Add to `JobKind` enum, alembic noop migration, new handler in
     `services/{area}/runner.py`, route that calls `schedule()`
2. **How to add a new dataset analysis check**
   - Pure function in `analysis/checks.py`, add to `run_all_checks()`,
     extend `score.py` weights if it should affect health, add a rule in
     `recommend/dataset.py`
3. **How to add a new converter format**
   - Class in `services/datasets/converters/`, register in
     `FORMAT_TO_CONVERTER`, add UI option in `DatasetUploadPage`
4. **How to add a new SSE event channel**
   - Pick a `channel_key`, `bus.publish(channel_key, event)` from anywhere,
     subscribe via `useSSE(path)` on the frontend

### Don't-build list (premature optimizations)
- ❌ Microservices — current monolith handles thousands of users
- ❌ Kafka / event store — Postgres handles your throughput for years
- ❌ K8s before you outgrow docker-compose — it's overhead, not insurance
- ❌ React Native / mobile — desktop is the right form factor for this UI
- ❌ Custom training engine — Ultralytics covers 95% of CV cases

### What to NEVER skip in a phase
1. A migration if you change the schema (`alembic revision -m "..."`)
2. A test that fails before the change and passes after
3. A one-paragraph entry in `DECISIONS.md`
4. An update to this roadmap when scope changes

---

## Suggested cadence

If you ship one phase per week, the full roadmap is ~6–7 months. That's
realistic for a single contributor working part-time. For a team of 2–3,
Phases 7–14 can run in parallel and you're at the AI-agent work in
2 months.

The "small" phases (7, 8, 9) genuinely should be first — they make every
later phase faster and safer. The temptation to skip to Phase 16 (AI agent)
is real; resist it.
