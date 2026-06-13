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
  blocks colored by role and sized to their length; blackout windows and
  external-course walls overlaid; per-cohort / per-room / per-lecturer views.
- **Persistent catalog** of courses with a full editor (programs, year, role,
  session structure, room needs, externals, staff), plus a **one-click sample
  catalog** so a fresh install reaches a full solved schedule in seconds.
- **Per-person availability** — a click grid to mark when a lecturer/TA can't
  teach; blocks become hard constraints on re-solve.
- **Semester calendar** — semester dates, blocked days, and day-substitutions;
  Analyze reports teaching-day counts, uneven sessions, and order inversions.
- **Skeleton import** — upload the Technion XLSX; it's parsed and filtered to your
  catalog in an **editable** table; offered groups drive the solve and any
  grid-aligned day/time is **pinned** as a hard fixed placement (🔒).
- **Bilingual** Hebrew (RTL) / English UI.
- **Exports** — printable PDF timetables: one weekly grid page **per cohort**
  (Hebrew course names, spanning blocks) or a flat assignments list, plus CSV.

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
    sample_data.py       illustrative demo catalog
  tests/                 73 tests
frontend/       React + TS + Vite — tabs: Schedule / Catalog / Availability / Calendar / Import
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
pytest                 # 73 passing
```

## Run

```bash
# API (from repo root)
uvicorn schedy.api:create_app --factory --app-dir backend --port 8000

# Frontend (Node 20+)
cd frontend && npm install && npm run dev      # http://localhost:5173

# Single-process — one command (build the UI once, then launch + open browser)
cd frontend && npm install && npm run build && cd ..
python backend/launcher.py                      # serves UI + API on :8000, opens browser

# …or run the server directly in single-process mode
SCHEDY_STATIC=frontend/dist uvicorn schedy.api:create_app --factory --app-dir backend --port 8000

# Docs
mkdocs serve           # or: mkdocs build -> site/
```

**First run:** open the app, go to **Catalog → Load sample catalog** (or click
the prompt on the empty Schedule tab), then **Solve** to see a full timetable.

Packaging a one-click Windows app: see [docs/windows.md](docs/windows.md).

## Status

Backend engine complete and tested (domain, calendar, evaluator, parser,
validator, CP-SAT solver with a lab cross-day repair loop, catalog, store, API,
exporters). Frontend is a functional MVP — tabbed app with the interactive
editable grid (multi-box blocks + blackout/external overlay), full catalog editor
with sample data across all three programs, per-person availability, semester
calendar analysis, an editable skeleton import that pins fixed times, and
per-cohort PDF grid export with Hebrew names. The PRD's design questions are
resolved; the app is ready to populate with a real catalog.

Documentation: [docs/index.md](docs/index.md) · full spec & status:
[docs/PRD.md](docs/PRD.md).
