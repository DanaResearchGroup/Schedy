# Schedy

Auto-solver for the Chemical Engineering department's weekly teaching schedule.
It places the department's own lectures, exercises, and labs into a Sun–Thu
academic-hour grid — around fixed external courses and blackout windows —
enforcing hard constraints and minimising a weighted ladder of soft preferences,
then hands the planner an editable, live-validated result.

**Stack:** Python 3.14 · OR-Tools CP-SAT · FastAPI · SQLite · React/TypeScript.

## Layout

```
backend/        Python engine + FastAPI API
  schedy/
    domain.py            value objects + time grid
    calendar_engine.py   dated-calendar overlay (pure)
    evaluator.py         hard/soft violations — the correctness core (pure)
    parser.py            Technion skeleton XLSX -> sessions (pure core)
    validator.py         must-exist checklist -> missing items (pure)
    model_builder.py     Problem -> CP-SAT model
    solver.py            run + best-effort + evaluator report
    catalog.py           Course aggregate + expand() -> Problem
    store.py             SQLite persistence
    exporters.py         CSV + PDF
    api.py               FastAPI orchestration
  tests/                 47 tests
frontend/       React + TS + Vite (bilingual, RTL)
docs/           PRD + MkDocs documentation source
raw/            constraints spec + example Technion skeleton
environment.yml conda env (Python 3.14)
mkdocs.yml      HTML docs config
```

## Setup

```bash
conda env create -f environment.yml
conda activate schedy
cd backend && pip install -e .
pytest                 # 47 passing
```

## Run

```bash
# API (from repo root)
uvicorn schedy.api:create_app --factory --app-dir backend --port 8000

# Frontend (needs Node 20+)
cd frontend && npm install && npm run dev      # http://localhost:5173

# Docs
mkdocs serve           # http://localhost:8000  (or: mkdocs build -> site/)
```

## Status

The backend engine is complete and tested (domain, calendar, evaluator, parser,
validator, CP-SAT solver, catalog, store, API, exporters). The frontend is a
runnable scaffold (weekly grid, catalog, solve, export); drag-and-drop editing,
per-cohort/room/lecturer views, availability grids, and the import-review and
calendar UIs are the next build steps (see [docs/PRD.md](docs/PRD.md)).

Documentation: [docs/index.md](docs/index.md) · full spec: [docs/PRD.md](docs/PRD.md).
