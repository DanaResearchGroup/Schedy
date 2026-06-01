# Architecture

Schedy is a local web app with a thin API over a pure-Python engine. The engine
is split into deep, independently-testable modules; correctness risk is
concentrated in four pure modules with no I/O.

## Data flow

```
                ┌──────────────────────── Frontend (React/TS) ───────────────────────┐
                │  weekly grid · catalog · solve button · violations · export links   │
                └───────────────────────────────┬────────────────────────────────────┘
                                                 │ HTTP /api
                ┌────────────────────────────────▼────────────────────────────────────┐
                │                          FastAPI (api.py)                            │
                └───┬───────────────┬───────────────┬───────────────┬──────────────────┘
                    │               │               │               │
              ┌─────▼─────┐   ┌─────▼─────┐   ┌──────▼──────┐  ┌─────▼──────┐
              │  Store    │   │  Parser   │   │   Solver    │  │  Exporters │
              │ (SQLite)  │   │ Validator │   │   Runner    │  │  PDF / CSV │
              └─────┬─────┘   └───────────┘   └──────┬──────┘  └────────────┘
                    │ Course[]                       │ Problem
              ┌─────▼─────┐                   ┌──────▼──────┐
              │  catalog  │ ── expand() ────▶ │ ModelBuilder│ ── CP-SAT ──▶ Schedule
              │  .expand  │      Problem      └──────┬──────┘
              └───────────┘                          │ Schedule + Problem
                                              ┌──────▼──────┐
                                              │  Evaluator  │ ── violations (hard+soft)
                                              └─────────────┘
```

## The solver pipeline

1. **Catalog → Problem.** `catalog.expand` turns durable `Course` records into a
   `Problem`: department courses become `Session`s; external courses become
   immovable `FixedEvent` walls; standing blackouts are added.
2. **Problem → CP-SAT model.** `ModelBuilder` lays sessions on a single absolute
   box timeline (`NUM_DAYS × BOXES_PER_DAY`) so interval no-overlap works in one
   dimension. Hard rules become no-overlap / forbidden-region constraints; soft
   rules become reified overlap booleans summed into the objective.
3. **Solve → Schedule.** `solver.solve` runs CP-SAT under a time limit and
   extracts a `Schedule` (session → day/box/room).
4. **Evaluate.** The `Evaluator` re-checks the schedule and attaches every
   violation. It is the **single source of truth** for all rules — the same
   function powers the solver's explanation and the frontend's live validator —
   so both always agree.

## Why "best-effort + editable"

Many of the department's rules are soft ("avoid", "as much as possible"). The
solver therefore never refuses to answer: it returns the least-bad schedule plus
a structured violation report, and the planner finishes on the grid. The
evaluator runs on every edit, so manual changes are validated the same way the
solver's output was.

## The calendar overlay

The solver optimises the **abstract weekly template**. The `CalendarEngine`
overlays a dated semester (start date, blocked dates, day-substitutions) to:

- report each session's realised meeting count and flag deficits, and
- flag realised weeks where a day-substitution inverts lecture-before-exercise
  order (flagged, never prevented — preventing it across every realised week
  would blow up the model).
