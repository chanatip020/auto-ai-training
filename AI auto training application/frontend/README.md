# AI Auto Training Platform — Frontend

React 18 + Vite + TypeScript + Tailwind + TanStack Query + Recharts.

## Quick start

```bash
cd frontend
npm install

# Run dev server (proxies /api → http://localhost:8000)
npm run dev
# open http://localhost:5173

# Type-check
npm run lint

# Production build
npm run build
```

The backend must be running on `http://localhost:8000` for the dev proxy to work.

## First-time login

There is no signup screen — v1 is single-user. On the login screen, paste the
backend's `API_TOKEN` (the value from `backend/.env`). The token is stored in
`localStorage` and sent as `Authorization: Bearer …` on every request.

## Routes

| Path | Page |
|---|---|
| `/login` | Paste API token |
| `/` | Dashboard (project list) |
| `/projects/new` | Create project |
| `/projects/:id` | Project overview + timeline |
| `/projects/:id/dataset` | Upload ZIP, list versions, convert |
| `/projects/:id/cvat` | CVAT import (placeholder, Phase 6) |
| `/projects/:id/analyze/:versionId` | Health score, recommendations |
| `/projects/:id/train` | Configure + start training |
| `/projects/:id/train/:jobId` | Live training monitor (SSE charts) |
| `/settings` | API token + CVAT connections (placeholder) |

## CVAT integration (future)

The architecture is ready for CVAT:

- `src/lib/types.ts` defines `CvatConnection` and `CvatImport` types.
- `src/features/cvat/` holds the placeholder routes.
- `src/features/datasets/DatasetUploadPage.tsx` includes a disabled
  "Import from CVAT" tab marked **Coming in Phase 6**.
- `src/features/settings/SettingsPage.tsx` shows the planned CVAT
  connections UI in a disabled state.

When the backend ships Phase 6, the frontend changes are: enable the
disabled tab and wire it to the new endpoints — no architectural rework.
