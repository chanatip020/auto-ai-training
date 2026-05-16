# Contributing — patterns that recur

This file is the **how-to manual** for adding features to the platform. Every
section below is a template that has been used at least twice in the existing
code, so the patterns are battle-tested. Copy, adapt, ship.

For *what* to build next, see [ROADMAP.md](./ROADMAP.md). For *why* it's
built this way, see [the design doc](./AI_Auto_Training_Platform_Architecture_Design.docx).

---

## 1. Add a new background job kind

**Use when:** you have work that takes >2 seconds and shouldn't block the
HTTP response (uploads, conversions, analyses, training).

### Steps
1. Add the kind to the enum + Postgres ENUM:
   ```python
   # backend/app/models/enums.py
   class JobKind(_StrEnum):
       ...
       MY_NEW_KIND = "my_new_kind"
   ```
   ```python
   # backend/alembic/versions/XXXX_my_new_kind.py
   op.execute("alter type job_kind add value if not exists 'my_new_kind'")
   ```

2. Write the handler. It owns its own session:
   ```python
   # backend/app/services/myarea/runner.py
   async def run_my_new_thing(session: AsyncSession, job: Job) -> None:
       payload = job.payload or {}
       job.status = JobStatus.RUNNING
       job.message = "Starting"
       job.progress = 5
       await session.commit()

       # …do the work in chunks, updating job.progress between each…
       await asyncio.to_thread(blocking_func, ...)

       job.progress = 100
       job.status = JobStatus.SUCCEEDED
       await session.commit()
   ```

3. Schedule from a router:
   ```python
   # backend/app/api/v1/myarea.py
   from app.jobs.runner import create_job, schedule
   from app.services.myarea import runner

   @router.post("/some-resource/{id}/do-the-thing")
   async def start(id: UUID, background_tasks: BackgroundTasks, ...):
       job = await create_job(session, kind=JobKind.MY_NEW_KIND,
                              project_id=..., payload={...})
       await session.commit()                # IMPORTANT: commit before scheduling
       schedule(background_tasks, job, runner.run_my_new_thing)
       return ok(JobAcceptedOut(job_id=job.id))
   ```

4. The frontend polls `/jobs/{job_id}` via the existing `useJob` hook. No
   new endpoint needed.

### Gotchas
- **Always `session.commit()` before `schedule()`** — the background task
  opens its own session and won't see uncommitted writes.
- **Don't raise** from inside the handler unless you want `status=failed`.
- **Don't keep the job row "running" forever** — emit a final state.

---

## 2. Add a new dataset analysis check

**Use when:** you want a new column on the health-score gauge or a new
"warning" in the recommendations list.

### Steps
1. Write a pure function in `backend/app/services/analysis/checks.py`:
   ```python
   @dataclass
   class MyCheckReport:
       offenders: int = 0

   def my_check(version_root: Path) -> MyCheckReport:
       rep = MyCheckReport()
       # …walk the directory tree…
       return rep
   ```

2. Plug it into the aggregator:
   ```python
   def run_all_checks(version_root: Path) -> dict[str, dict]:
       return {
           ...,
           "my_check": my_check(version_root).__dict__,
       }
   ```

3. If it should affect the health score, add a weighted component in
   `analysis/score.py`:
   ```python
   components["my_check"] = 5.0 * _clamp(1 - findings["my_check"]["offenders"] / n)
   ```
   Reduce another component's weight so they still sum to 100.

4. If it should produce a user-visible recommendation, add a rule in
   `recommend/dataset.py`:
   ```python
   if findings.get("my_check", {}).get("offenders", 0) > 0:
       recs.append(_rec("MY_CHECK_FAILED", "warning",
                        "X offenders found", "do this fix", {...}))
   ```

### Gotchas
- **Pure functions only** — checks must not write to disk or hit network.
- **Bound the work** — `sample_limit` parameter for anything that walks
  every image.
- **Add tests** in `tests/services/analysis/` before merging.

---

## 3. Add a new dataset format converter

**Use when:** you support a new model family or annotation format.

### Steps
1. Subclass `BaseConverter`:
   ```python
   # backend/app/services/datasets/converters/my_format.py
   class MyFormatConverter(BaseConverter):
       format_id = "my-format"

       def convert(self, *, input_dir, output_dir, ratios,
                   classes_override, seed) -> ConversionResult:
           # …read input_dir, write output_dir, return result…
   ```

2. Register it:
   ```python
   # backend/app/services/datasets/converters/__init__.py
   FORMAT_TO_CONVERTER["my-format"] = MyFormatConverter
   ```

3. Add the format option in the frontend dropdown:
   ```tsx
   // frontend/src/features/datasets/DatasetUploadPage.tsx
   // The target format is currently derived from project.task_type.
   // For an opt-in alternate, add an explicit Select in ConvertSection.
   ```

4. Reuse `split_items` from `services/datasets/split.py` so your converter
   is also deterministic.

### Gotchas
- **Write `data.yaml` if your format is YOLO-compatible.**
- **Never mutate the input directory** — only read from it.

---

## 4. Add a new SSE event channel

**Use when:** you have a long-running process and want to push progress
to the UI instead of polling.

### Steps
1. Pick a stable channel key (e.g. `f"myjob:{job_id}"`).

2. From your handler / callback, publish events:
   ```python
   from app.realtime.sse import bus
   bus.publish(f"myjob:{job_id}", {
       "type": "progress", "step": "extracting", "percent": 30,
   })
   ```

3. Expose an SSE endpoint:
   ```python
   # backend/app/api/v1/myarea.py
   from fastapi.responses import StreamingResponse
   from app.realtime.sse import event_stream

   @router.get("/sse/myjob/{job_id}")
   async def sse_myjob(job_id: UUID, ...):
       return StreamingResponse(
           event_stream(f"myjob:{job_id}"),
           media_type="text/event-stream",
           headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
       )
   ```

4. Subscribe in the frontend:
   ```tsx
   import { useSSE } from '../../lib/sse';
   useSSE(`/api/v1/sse/myjob/${jobId}`, (ev) => {
       if (ev.type === 'progress') setStep(ev.step as string);
   });
   ```

### Gotchas
- **Always send a final `done`/`failed`/`cancelled` event** — the client
  uses it to close the stream cleanly.
- **Don't block** — `bus.publish` is sync and fire-and-forget. If you're
  in a worker thread, use `bus.publish_threadsafe`.

---

## 5. Add a new API endpoint

**Use when:** you want a new HTTP route.

### Steps
1. Pick the router file: `backend/app/api/v1/{area}.py`. Add a function:
   ```python
   @router.get("/my-thing/{id}", response_model=Envelope[MyOut])
   async def get_my_thing(
       id: UUID,
       user: CurrentUser = Depends(current_user),
       session: AsyncSession = Depends(get_session),
   ) -> Envelope[MyOut]:
       # auth check + business logic in a service
       result = await my_service.do_thing(session, id, user_id=UUID(user.id))
       return ok(MyOut.model_validate(result))
   ```

2. Define the Pydantic schema in `app/schemas/{area}.py`:
   ```python
   class MyOut(BaseModel):
       model_config = ConfigDict(from_attributes=True)
       id: UUID
       name: str
   ```

3. **Routers stay thin.** All real logic lives in `services/`.

4. Frontend: hook in `features/{area}/api.ts`:
   ```typescript
   export function useMyThing(id: string | undefined) {
       return useQuery({
           queryKey: ['my-thing', id],
           queryFn: () => api.get<MyOut>(`/api/v1/my-thing/${id}`),
           enabled: !!id,
       });
   }
   ```

### Gotchas
- **Always go through a service** — never put a `select()` in a router.
- **Always use the envelope** — `ok(...)` wraps the response. Errors raise
  `AppError` and get formatted by the middleware.

---

## 6. Add a new DB migration

```bash
# from inside the api container, or with the venv active
docker compose exec api alembic revision -m "describe the change"

# edit the generated file in alembic/versions/, run upgrade(), downgrade()
# both are required — downgrade must be tested!

docker compose exec api alembic upgrade head
docker compose exec api alembic downgrade -1   # verify it reverses cleanly
docker compose exec api alembic upgrade head   # apply again
```

### Gotchas
- **Test downgrade.** The day you need it is the worst day not to test it.
- **Enum changes can't be done in a transaction in older Postgres.** Use
  `alter type ... add value if not exists '...'` in its own migration.
- **Never edit a migration that's already deployed.** Add a new one.

---

## 7. The DECISIONS.md habit

For every PR-sized change, append a paragraph at the top of
`DECISIONS.md` (create it if you haven't):

```markdown
## 2026-05-15 — Hyperparameter diff highlight

Added a "Recommended / YOLO defaults" preset toggle on the training form.
Inputs whose current value differs from Ultralytics' canonical defaults
get a blue ring + "tuned" badge.

**Why:** users couldn't tell which knobs the rec engine had moved.

**Trade-off:** the hardcoded `YOLO_DEFAULTS` map in the frontend will drift
from Ultralytics upstream over time. Accepted because the diff is
informational and Ultralytics versions ~yearly.

**Alternatives considered:** fetching defaults from the backend on each
mount (rejected — adds a round-trip for an essentially-static value).
```

In a year, this is your most valuable document.

---

## 8. Local development checklist

Before pushing:
- [ ] `make test` passes (after Phase 7)
- [ ] `docker compose exec api alembic upgrade head` succeeds and
      `alembic downgrade -1 && alembic upgrade head` reverses cleanly
- [ ] `cd frontend && npm run lint` passes (tsc --noEmit)
- [ ] New endpoints show up at `/docs` with correct schemas
- [ ] A new entry exists in `DECISIONS.md`
- [ ] `ROADMAP.md` updated if scope changed

---

## 9. When you get stuck

The system has been built in 19 layered phases. Almost every problem you
hit will look like one of these:

| Symptom | Likely culprit |
|---|---|
| Backend 500 with no detail | Check `docker compose logs api` for the actual traceback. Dev mode includes `details.exception` in the response — open DevTools network tab. |
| Migration won't apply | `alembic current` to see where you are. If stuck, `alembic stamp head` after manually fixing the schema. |
| Frontend says "Method Not Allowed" (405) | Empty path segment from an undefined variable. Check the DevTools Request URL for `//` or `undefined`. |
| SSE stream doesn't update | Check the backend logs for `bus.publish` calls. Check the browser network tab — the SSE response should be `event-stream` with frames. |
| Auto-refresh not happening | Make sure the `useEffect` watching job status calls `qc.invalidateQueries(...)` with the right query key. |
| Training fails immediately | Convert dataset format first. Raw versions can't train. Check `dataset_version.format`. |

---

This file should grow over time. Whenever you write the same code twice,
extract a template here.
