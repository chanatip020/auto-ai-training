# Decision log

Append one paragraph per PR-sized change. Newest at the top. See the
"DECISIONS.md habit" section of [CONTRIBUTING.md](./CONTRIBUTING.md).

---

## 2026-05-26 — TryItPanel cleanup + one-command docker compose

Closed the last two open items from the original CLAUDE.md roadmap. The
Phase 7 `TryItPanel.tsx` had 8 TypeScript errors because `usePredict`,
`useExportModel`, `PredictionResult`, and `ExportResult` were referenced
but never written into `features/training/api.ts` — the backend endpoints
(`POST /training-jobs/{id}/predict`, `POST /training-jobs/{id}/export`)
and `app/services/inference/predictor.py` were already in place, so this
was purely a frontend wiring gap. Added the missing types in `lib/types.ts`,
the missing hooks in `features/training/api.ts`, and re-exported the types
from the training api module so the panel imports work. Full frontend
`tsc --noEmit` is now clean. For the Docker side, `docker compose up` no
longer requires a Supabase config — added a `db` service (Postgres 16
alpine) with a `pg_isready` healthcheck, made the api `depends_on:
db: service_healthy`, and defaulted `DATABASE_URL` to the local docker
network address (`postgresql+asyncpg://aiat:aiat@db:5432/aiat`) with shell
interpolation so an external DATABASE_URL still wins. Postgres data lives
on a named `db-data` volume; the host port is 5433 to avoid colliding with
local Postgres installs. Makefile gained a `make up` alias and updated
help text explaining the self-contained mode. All 77 backend tests still
pass. The original 11-feature roadmap is now closed; remaining work is
the VisionOps Phase 1 items (remarks, golden val set, model registry).

---

## 2026-05-26 — Export dataset version as ZIP + dashboard as a table

Added `GET /api/v1/datasets/versions/{id}/export` so users can pull a
converted dataset version off the platform without poking the filesystem.
The endpoint streams the on-disk converted folder (`images/`, `labels/`,
`data.yaml`) into a ZIP via a small write-buffer drained between files,
which keeps memory bounded by the largest single file rather than the whole
dataset — important for multi-GB exports. Raw versions return 400
(`EXPORT_RAW_NOT_SUPPORTED`) since the YOLO folder shape only exists after
conversion. The archive matches the converter output 1:1, so it's
drop-in usable by Ultralytics. The dashboard's card grid was swapped for a
table (Name, Model, Task, Status, Created, Updated, Open) — the user wanted
to scan many projects at a glance, which a table does better than cards.
The version row in the dataset detail page now exposes an "Export ↓" button
next to "Analyze →"; the frontend downloads via an authenticated fetch +
Blob URL so the Bearer token stays out of the URL. Five new backend unit
tests cover the streaming zip, chunked output, missing-data error,
filename sanitization, and the all-unsafe-name fallback; full suite is now
77 passing (was 72).

---

## 2026-05-16 — Phase 8: training provenance + history

Audited what we persist across the lifecycle and found 8 gaps on
`training_jobs` + 1 on `training_metrics`. Migration 0005 added six
columns to `training_jobs` (`summary`, `dataset_snapshot`,
`recommendation_snapshot`, `preset_source`, `override_blockers`,
`app_version`) and a `per_class` jsonb on `training_metrics`. A new
`services/training/provenance.py` captures hardware fingerprint
(Python/torch/CUDA/GPU/RAM), git short SHA, dataset-version snapshot at
start time, and a params-vs-recommendation diff. The runner writes a
completion summary (`best_epoch`, `total_time_s`, `n_epochs_completed`,
`exit_reason`) before returning. Two new endpoints — `GET
/projects/{id}/training-history` and `GET
/training-jobs/{id}/clone-as-config` — feed the new
`TrainingHistoryPage` with sortable + filterable past runs and a
side-by-side compare view (pick 2 rows → diff their params, with the
changed keys highlighted blue). The frontend `TrainingStartPage` now
auto-computes `preset_source` ('recommended' | 'default' | 'manual')
from the current params vs the baselines and sends it + `override` +
`recommendation_snapshot` on POST. Reason: every later AI-agent phase
needs this data to reason "what worked / didn't last time"; capturing
it now is far cheaper than backfilling. Trade-off: `dataset_snapshot`
stores a full copy of the version row per run — a few KB each, fine for
v1, would dedup if we ever have >1M runs.

## 2026-05-15 — Phase 7: tests + CI

Added pytest unit tests for the pure-function backend (`split`, `detect`,
`score`, both recommendation engines, `yaml_writer`, the YOLO converters) —
63 tests covering deterministic split behaviour, format heuristics, the
weighted health-score components, and the rules-engine severity ordering.
On the frontend, set up vitest + jsdom + React Testing Library with 34
tests across `format` helpers, `auth` token storage, and the
`StatusPill` / `HealthGauge` / `Button` components. Added a GitHub Actions
CI workflow that runs ruff, pytest, tsc, vitest, and verifies that both
Docker images build. Makefile gained `make test`, `make lint`, `make ci`.
Reason: every later roadmap phase is dangerous without a green test
suite — the smoke scripts are useful but not gateable. Trade-off: no
integration tests against a real Postgres yet (deferred to a follow-up
when we need to test the routers/services that touch the DB) — Phase 8
will introduce testcontainers since the new history endpoints will need
DB round-trips.

## 2026-05-14 — Hyperparameter diff highlight

Adopted a "Recommended / YOLO defaults" preset toggle on the training form.
Inputs whose current value differs from Ultralytics' canonical defaults get
a blue ring + "tuned" badge. Reason: users couldn't tell which knobs the
rec engine had moved. Trade-off: hardcoded defaults map in the frontend
will drift from Ultralytics' upstream over time — accepted because the
diff is informational and Ultralytics versions ~yearly.

## 2026-05-21 — Background images aren't defects

Added a per-dataset `treat_unlabeled_as_background` flag (migration 0007) so
that images shipped without a label file can be marked as intentional
zero-object frames — the Ultralytics-recommended 0–10% background mix that
reduces false positives — instead of being flagged as missing annotations.
When the flag is on, the YOLO converter materializes empty `.txt` sidecars
for every label-free image (the standard YOLO convention for "this frame
has no objects"), the analyzer reclassifies them under a separate
`background` bucket, the health-score stops penalising the missing-label
component, and the recommender emits one of three `BACKGROUND_RATIO_*`
hints (high/low/ok) instead of `MISSING_LABELS`. When the flag is off the
old `MISSING_LABELS` rule becomes tiered: ≤10% is info (likely
background), 10–30% warning, >30% blocker. Frontend gets a checkbox at
dataset-creation time and a per-convert override on the convert form.
Trade-off: introduces a user decision that didn't exist before, but it's
unavoidable — there's no automatic way to tell unlabeled images from
intentional backgrounds without asking. Picked dataset-level (not
per-version) because the intent doesn't change between conversions.
