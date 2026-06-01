# Modules

Each module has a small, stable interface and is tested in isolation. The four
**pure** modules carry the correctness risk and have no I/O.

## Pure core

### `domain`
Value objects and the time grid. `Cohort = (program, year)`, `Room`, `Session`,
`FixedEvent`, `Problem`, `Schedule`, `SoftWeights`. Time is ten 60-minute boxes
per day, Sun–Thu, with `box_interval` / overlap helpers. No behaviour beyond
small total functions.

### `calendar_engine` (pure)
Overlays a dated `SemesterCalendar` on the weekly template.

- `realize(cal)` → dated teaching/non-teaching sequence (applies substitutions).
- `meeting_counts` / `lost_sessions` → per-session realised counts + deficits.
- `order_inversions` → realised weeks where a swap flips lecture-before-exercise.

### `evaluator` (pure) — the correctness core
`evaluate(problem, schedule) → EvaluationResult` returns every hard and soft
`Violation`. Reused by the solver explanation **and** the live editor. Covers
room/cohort/person double-booking, blackout, capacity, computer-farm,
availability, same-course TA coincidence, lab cross-day satisfiability, and the
weighted soft ladder.

### `parser` + `validator` (pure)
- `parser.parse_rows` locates columns by **Hebrew header text** (robust to
  reordering) and yields `OfferedSession`s, filtered to relevant course numbers.
  `parse_skeleton` is the thin file shell.
- `validator.find_missing` checks the parsed skeleton against a user-defined
  `ChecklistItem` list (matches dedicated groups like *HEDVA 13* by substring).

## Engine

### `model_builder`
Translates a `Problem` into a CP-SAT model (hard no-overlap / forbidden regions;
soft reified-overlap objective). Lab cross-day satisfiability is deliberately left
to the evaluator as a post-hoc check.

### `solver`
`solve(problem, time_limit_s)` runs CP-SAT, extracts a `Schedule`, and always
attaches the evaluator's report (`SolveResult`).

### `catalog`
`Course` aggregate + `expand(courses)` → `Problem`.

## I/O & delivery

### `store`
SQLite persistence: `courses` table + JSON `settings`. Single-planner local app.

### `exporters`
`to_csv` (deterministic, golden-tested) and `to_pdf` (reportlab) — per the PRD,
**no** university XLSX writeback.

### `api`
FastAPI: catalog CRUD, availability, skeleton parse/validate, solve, CSV/PDF
export. Thin — all logic lives in the engine modules.

## Test coverage

| Module | Tests |
| --- | --- |
| calendar_engine | realize, substitutions, counts, deficits, inversions |
| evaluator | one scenario per hard & soft rule (incl. Thermo lab) |
| parser / validator | column mapping, group codes, missing items, real XLSX smoke |
| model_builder / solver | cohort separation, capacity/farm routing, blackout, soft min, availability |
| exporters | CSV golden, PDF smoke |
| api | full catalog → solve → export pipeline |
