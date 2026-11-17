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
- `week_anchor(cal)` → weekday the first teaching day runs; the week's start for
  every ordering rule (`Problem.week_anchor`, applied via `domain.day_rank`).
- `meeting_counts` / `lost_sessions` → per-session realised counts + deficits.
- `order_inversions` → exercises meeting before their lecture, each tagged
  `template_order` (recurs every week; one entry carrying `weeks`) or
  `substitution` (one flipped week; one entry per week).

### `evaluator` (pure) — the correctness core
`evaluate(problem, schedule) → EvaluationResult` returns every hard and soft
`Violation`. Reused by the solver explanation **and** the live editor. Covers
room/cohort/person double-booking, blackout, capacity, computer-farm,
availability, same-course TA coincidence, lab cross-day satisfiability, and the
weighted soft ladder.

### `parser` + `validator` (pure)
- `parser.parse_rows` locates columns by **Hebrew header text** (robust to
  reordering) and yields `OfferedSession`s, filtered to relevant course numbers.
  Columns the scheduler reasons about become fields; a fixed allowlist of further
  named columns is carried verbatim in `details`, so the review screen shows a
  course's record without a field per column. Unknown columns, and the employee
  number and national ID, are dropped. `parse_skeleton` is the thin file shell.
- `validator.find_missing` checks the parsed skeleton against a user-defined
  `ChecklistItem` list (matches dedicated groups like *HEDVA 13* by substring).

### `coi_io` (pure)
Reads the hand-maintained **courses-of-interest** file — the list of course
numbers that filters the skeleton on import. Deliberately tolerant: CSV or Excel,
headed (`number,name`, either order, Hebrew or English) or a bare list of numbers,
and `normalize_number` restores the leading zeros Excel strips off `00540315`.
Format and examples: [`examples/README.md`](https://github.com/DanaResearchGroup/Schedy/blob/main/examples/README.md).

## Engine

### `model_builder`
Translates a `Problem` into a CP-SAT model (hard no-overlap / forbidden regions;
soft reified-overlap objective). The base model omits lab cross-day
satisfiability; the evaluator flags it and the solver's guided-repair loop
rebuilds the model with native lab constraints for the offending groups.

### `solver`
`solve(problem, time_limit_s)` runs CP-SAT, extracts a `Schedule`, and attaches the
evaluator's report (`SolveResult`) whenever a schedule exists; an infeasible or
unknown result carries none.

### `catalog`
`Course` aggregate + `expand(courses)` → `Problem`.

### `catalog_io` (pure)
Catalog ⇄ CSV/Excel, one row per course; list-valued fields use `;` inside the
cell. The column header is the format spec.

## I/O & delivery

### `store`
SQLite persistence: `courses` table + JSON `settings`. Single-planner local app.

### `archive`
Saved schedules: one self-contained `.schedy.json` file per save (placements plus
a copy of the catalog, skeleton rows, availability and calendar), in a folder
confined under the saves root. Filesystem-only, no web concerns.

### `uploads` (pure)
Filename rules shared by the three spreadsheet-upload endpoints, including the
refusal of legacy `.xls` with a message saying what to do.

### `exporters`
`to_csv` (deterministic, golden-tested) and `to_pdf` (reportlab) — per the PRD,
**no** university XLSX writeback.

### `api`
FastAPI: catalog CRUD, courses-of-interest file import/export, availability,
skeleton parse/validate, solve, CSV/PDF export. Thin — all logic lives in the
engine modules.

## Test coverage

| Module | Tests |
| --- | --- |
| calendar_engine | realize, substitutions, counts, deficits, inversions |
| evaluator | one scenario per hard & soft rule (incl. Thermo lab) |
| parser / validator | column mapping, pass-through details, group codes, missing items, real XLSX smoke |
| catalog_io / uploads | CSV round trips (catalog_io); Excel/legacy `.xls` handling (uploads) |
| archive | save / load / list, id sanitising, folder confinement |
| terms / publish / phase 2 | term scoping, freeze, graduate append, rollover, levels, clash rules |
| coi_io | headed / bare / Excel shapes, leading-zero repair, round trips |
| model_builder / solver | cohort separation, capacity/farm routing, blackout, soft min, availability |
| exporters | CSV golden, PDF smoke |
| api | full catalog → solve → export pipeline |
