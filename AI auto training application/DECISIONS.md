# Decision log

Append one paragraph per PR-sized change. Newest at the top. See the
"DECISIONS.md habit" section of [CONTRIBUTING.md](./CONTRIBUTING.md).

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
