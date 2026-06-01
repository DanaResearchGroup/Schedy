# Schedy

**Schedy** auto-generates a conflict-free weekly teaching schedule for the
Chemical Engineering department, then lets a planner review and hand-edit it on an
interactive grid with a live validator as a backstop. It runs as a local web app:
a **Python / OR-Tools CP-SAT** engine behind a **FastAPI** service, with a
**React / TypeScript** frontend.

## What it does

- Places the department's **own** lectures, exercises, and labs into a Sun–Thu,
  60-minute academic-hour grid, scheduling **around** fixed external courses and
  blackout windows.
- Enforces hard constraints (room/cohort/person clashes, capacity, blackouts,
  lab cross-day satisfiability) and minimises a weighted ladder of soft
  preferences (electives, Zoom timing, lecture-before-exercise).
- Returns a **best-effort** schedule with an explanation of every compromise, so
  the planner can finish by hand.
- Imports the Technion "skeleton" XLSX, validates it against a must-exist
  checklist, and overlays a dated semester calendar (holidays, day-substitutions).
- Exports printable PDF timetables and a flat CSV.

## Design at a glance

| Decision | Choice |
| --- | --- |
| Mode | Auto-solver with editable, live-validated result |
| Engine | Google OR-Tools CP-SAT |
| Time grid | Sun–Thu, 08:30–18:30, ten 60-min `:30`-aligned boxes |
| Cohort model | `(program, year)`, set-valued per course |
| Catalog | Persistent SQLite; externals are fixed walls |
| Stack | React/TS · FastAPI · SQLite · OR-Tools · Python 3.14 |
| Out of scope | University XLSX writeback; TA load-balancing; multi-user |

See the [Architecture](architecture.md), [Modules](modules.md), and the full
[PRD](PRD.md) for detail.

## Quick start

```bash
# backend (schedy conda env, Python 3.14)
conda env create -f environment.yml
conda activate schedy
cd backend && pip install -e . && pytest

# run the API
uvicorn schedy.api:create_app --factory --app-dir backend --port 8000

# frontend
cd frontend && npm install && npm run dev
```
