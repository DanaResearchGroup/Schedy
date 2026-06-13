# Schedy

[![CI](https://github.com/DanaResearchGroup/Schedy/actions/workflows/ci.yml/badge.svg)](https://github.com/DanaResearchGroup/Schedy/actions/workflows/ci.yml)
[![CodeQL](https://github.com/DanaResearchGroup/Schedy/actions/workflows/codeql.yml/badge.svg)](https://github.com/DanaResearchGroup/Schedy/actions/workflows/codeql.yml)
[![docs](https://github.com/DanaResearchGroup/Schedy/actions/workflows/docs.yml/badge.svg)](https://github.com/DanaResearchGroup/Schedy/actions/workflows/docs.yml)
![python](https://img.shields.io/badge/python-3.14-3776AB?logo=python&logoColor=white)
![license](https://img.shields.io/badge/license-MIT-green)

Auto-solver for the Chemical Engineering department's weekly teaching schedule.
It places the department's own lectures, exercises, and labs into a Sun–Thu
academic-hour grid — around fixed external courses and blackout windows —
enforcing hard constraints and minimising a weighted ladder of soft preferences,
then hands the planner an **editable, live-validated** result.

**Stack:** Python 3.14 · OR-Tools CP-SAT · FastAPI · SQLite · React/TypeScript · MkDocs.

## Features

- **Auto-solve** the department's schedule with OR-Tools CP-SAT (best-effort +
  explanation of every soft-constraint compromise).
- **Interactive grid** — drag-and-drop editing with live re-validation; readable
  blocks colored by role; per-cohort / per-room / per-lecturer views.
- **Persistent catalog** of courses with a full editor (programs, year, role,
  session structure, room needs, externals, staff).
- **Skeleton import** — upload the Technion XLSX; it's parsed, filtered to your
  catalog, and its actual offered groups drive the solve.
- **Bilingual** Hebrew (RTL) / English UI.
- **Exports** — printable PDF timetables + flat CSV.

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
  tests/                 56 tests
frontend/       React + TS + Vite — tabs: Schedule / Catalog / Import
docs/           PRD + MkDocs documentation source (incl. windows.md)
raw/            constraints spec + example Technion skeleton
environment.yml conda env (Python 3.14)
mkdocs.yml      HTML docs config
```

## Setup

```bash
conda env create -f environment.yml
conda activate schedy
cd backend && pip install -e .
pytest                 # 56 passing
```

## Run

```bash
# API (from repo root)
uvicorn schedy.api:create_app --factory --app-dir backend --port 8000

# Frontend (Node 20+)
cd frontend && npm install && npm run dev      # http://localhost:5173

# Single-process (serve built UI from the API)
cd frontend && npm run build && cd ..
SCHEDY_STATIC=frontend/dist uvicorn schedy.api:create_app --factory --app-dir backend --port 8000

# Docs
mkdocs serve           # or: mkdocs build -> site/
```

Packaging a one-click Windows app: see [docs/windows.md](docs/windows.md).

## Status

Backend engine complete and tested (domain, calendar, evaluator, parser,
validator, CP-SAT solver, catalog, store, API, exporters). Frontend is functional
— tabbed app with the interactive editable grid, full catalog editor, and
skeleton import. Next: per-person availability grids, calendar/blocks/swaps UI,
multi-box block rendering, and a Hebrew-capable PDF font.

Documentation: [docs/index.md](docs/index.md) · full spec & status:
[docs/PRD.md](docs/PRD.md).
