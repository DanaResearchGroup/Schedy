# Schedy frontend

React + TypeScript + Vite. Bilingual Hebrew (RTL) / English. Talks to the FastAPI
backend via the `/api` dev proxy (see `vite.config.ts`).

> Node is **not** installed in the original build environment, so this is a
> scaffold validated by inspection. Install Node 20+ to run it.

## Run

```bash
# 1. Start the backend (from repo root, schedy conda env)
uvicorn schedy.api:create_app --factory --app-dir backend --port 8000

# 2. Start the frontend
cd frontend
npm install
npm run dev      # http://localhost:5173, proxies /api -> :8000
```

## Structure

- `src/App.tsx` — shell: language toggle, solve button, export links, layout.
- `src/components/WeeklyGrid.tsx` — the centerpiece Sun–Thu × academic-hour grid;
  placed sessions render as blocks, hard-conflicted sessions glow red.
- `src/components/CatalogPanel.tsx` — add/list/delete courses (scaffold form).
- `src/api.ts` — typed client for the backend endpoints.
- `src/i18n.ts` — bilingual strings, day names, RTL switching, box-time labels.
- `src/types.ts` — TypeScript mirrors of the backend JSON shapes.

## Next (per PRD, not yet built)

- Drag-and-drop editing of placements with live re-validation.
- Per-cohort / per-room / per-lecturer grid views (currently one combined grid).
- Per-person availability grids; the import-review screen; calendar/blocks/swaps UI.
