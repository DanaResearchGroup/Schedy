# PRD — Schedy: Department Course-Scheduling Auto-Solver

> Status: ready-for-agent
> Scope: Chemical Engineering Department teaching-schedule planner (single semester at a time)
> Source material: `raw/Academic_Year_Schedule.md` (constraints), `raw/30.4.26.XLSX` (Technion "skeleton" example)

## Problem Statement

Each semester the department planner must produce a teaching schedule for the **entire** department — students in years 1–4, across multiple programs (Chemical Engineering, Biochemical Engineering, Chemical Engineering–Chemistry) — placing every lecture, exercise group, and lab into a weekly grid of rooms and hours.

The planner receives a bare "skeleton" schedule from the university (Technion) as a large, Hebrew-formatted XLSX containing hundreds of rows across many faculties. From it they must extract only the courses relevant to the department, then hand-place the department's own sessions around fixed external courses and university blackout windows, while juggling room capacities, lecturer/TA availability, lab cross-day satisfiability, and pedagogical preferences about electives and lecture/exercise ordering. Doing this by hand in Excel is slow, error-prone, and makes it nearly impossible to prove that no cohort is double-booked or that no expected session is missing.

## Solution

**Schedy** is a locally-run web application that **auto-generates** a conflict-free weekly schedule for the department's own courses using a constraint solver (Google OR-Tools CP-SAT), then lets the planner review and hand-edit the result on an interactive weekly grid with a live conflict validator as a backstop.

The system maintains a **persistent course catalog** (the durable spine), ingests the university skeleton each semester, validates that all expected sessions exist, overlays a dated semester calendar (start date, holidays, day-substitutions), and produces printable and machine-readable outputs. The solver places only the department's own lectures, exercises, and labs — treating external courses and blackout windows as fixed walls — and returns a best-effort schedule with a clear explanation of any soft-constraint compromises.

## User Stories

1. As the department planner, I want a persistent catalog of all department courses, so that I do not re-enter stable course metadata every semester.
2. As the planner, I want each `Course` to record its university course number, so that I can join it to the skeleton unambiguously.
3. As the planner, I want each course tagged with the program(s) it serves (ChemE, BioChemE, ChemE–Chemistry), so that the solver knows its audience.
4. As the planner, I want each course tagged with the student year (1–4) it serves, so that cohorts are identified correctly.
5. As the planner, I want a course to serve a *set* of cohorts (e.g. a shared course serving both `(ChemE, 2)` and `(BioChemE, 2)`), so that shared courses are modeled once, not duplicated.
6. As the planner, I want each course classified by role — core, elective, replacement, or lab-only, so that the right hard/soft rules apply.
7. As the planner, I want to define a course's session structure (lecture + N exercise groups + optional lab), so that the solver places every required session.
8. As the planner, I want to record a lab-only course (e.g. "ChemE Lab 2") with no lecture or exercises, so that pure labs are scheduled correctly.
9. As the planner, I want each course to carry an expected enrollment and room-type need, so that the solver assigns adequately sized and equipped rooms.
10. As the planner, I want to mark a course as **external** (`is_external = true`), with its own fixed day/time/room that never changes, so that the solver schedules around it.
11. As the planner, I want each cohort to reference which external courses its students take, so that external courses become hard walls for exactly the right cohorts.
12. As the planner, I want to import the Technion skeleton XLSX each semester, so that I can pull this semester's offered department sessions.
13. As the planner, I want the importer to filter the skeleton down to my department's courses by course number, so that I am not overwhelmed by hundreds of irrelevant rows.
14. As the planner, I want the importer to correctly read Hebrew columns, event types (הרצאה = lecture, תרגול = exercise), group codes (e.g. `SE011`), and per-day time ranges, so that parsed sessions are accurate.
15. As the planner, I want a **human-review screen** after parsing, so that I can eyeball and correct any mis-parsed courses or sessions before solving.
16. As the planner, I want to maintain a persistent, editable checklist of must-exist sessions (specific lectures of specific courses, and specific dedicated exercise groups such as "HEDVA 13"), so that I can verify the skeleton contains them.
17. As the planner, I want the system to flag any checklist item missing from the imported skeleton, so that I can chase it up with the university before scheduling.
18. As the planner, I want to define the semester's start date, so that the calendar reflects which arbitrary weekday the semester begins on.
19. As the planner, I want to enter blocked dates (holidays/occasions), so that no teaching is counted on those days.
20. As the planner, I want to enter day-substitutions (e.g. a real Tuesday running the Wednesday template), so that compensation days are accounted for.
21. As the planner, I want a per-course report of how many real meetings each session actually gets after blocks and swaps, so that I can spot under-met courses.
22. As the planner, I want the system to flag any realized week where a day-substitution inverts a course's lecture-before-exercise order, so that I can decide whether to intervene.
23. As the planner, I want to enter each lecturer's and TA's unavailability on a clickable weekly grid, so that the solver never schedules them when they cannot teach.
24. As the planner, I want the solver to guarantee no lecturer or TA is ever in two places at once (across all their courses), so that resource clashes are impossible.
25. As the planner, I want to press a single button to auto-generate the schedule, so that I do not place every session by hand.
26. As the planner, I want the solver to place only my department's courses (day, time, and room) around fixed externals and blackouts, so that the search stays focused and tractable.
27. As the planner, I want the solver to guarantee no two events share a room at the same time, so that rooms are never double-booked.
28. As the planner, I want the solver to guarantee a cohort is never double-booked — including against its fixed external courses, so that students can attend everything required.
29. As the planner, I want the solver to respect the standing blackout windows (Wed 12:30–14:30 "Wed Afternoon", Mon 13:30–14:30 seminar), so that those windows stay free.
30. As the planner, I want the solver to respect room capacity (≥ expected enrollment) and the computer-farm-only requirement for computer courses, so that placements are physically valid.
31. As the planner, I want the solver to guarantee a course's two TA sessions never coincide, so that a student can attend their group.
32. As the planner, I want the solver to guarantee lab **cross-day satisfiability** — every cohort needing a multi-day lab keeps at least one attainable day after its core courses are placed, so that every student can take the lab on some day.
33. As the planner, I want ChemE-only and BioChemE-only courses to be allowed to overlap each other (different audiences, different rooms), so that the solver can pack the week efficiently.
34. As the planner, I want electives to avoid clashing with core courses (highest-weight soft rule), so that students can actually take electives.
35. As the planner, I want electives to avoid clashing with each other, so that students can combine multiple electives in a semester.
36. As the planner, I want our own electives to avoid the Biology department's electives as much as possible, so that BioChemE students can take both.
37. As the planner, I want remote/Zoom-only sessions pushed to the morning or late afternoon, so that they do not break up the middle of a student's day.
38. As the planner, I want a general (low-weight) preference for each exercise group to fall after its course's lecture in the week, so that the teaching order makes pedagogical sense.
39. As the planner, when no schedule can satisfy everything, I want the solver to return the least-bad schedule with an explanation of exactly which soft constraints it compromised and why, so that I understand the trade-offs.
40. As the planner, I want to drop into an editable weekly grid after solving, so that I can hand-adjust the auto-generated result.
41. As the planner, I want the live validator to highlight any conflict (room, cohort, lecturer/TA, capacity, blackout, elective overlap) the moment I move a session, so that I never introduce a hidden clash.
42. As the planner, I want per-cohort grid views (e.g. "2nd-year ChemE"), so that I can see exactly what each group of students experiences.
43. As the planner, I want per-room and per-lecturer grid views, so that I can check room utilization and teaching loads.
44. As the planner, I want to export printable PDF timetables per cohort, per lecturer, and per room, so that students and staff can read the schedule.
45. As the planner, I want a flat CSV/Excel export of all assignments, so that I can reuse the data elsewhere.
46. As the planner, I want the application to run locally in my browser with a bilingual Hebrew (RTL) / English interface, so that it is convenient and needs no IT/hosting approval.
47. As the planner, I want my catalog and per-semester data persisted locally, so that my work survives between sessions.
48. As the planner, I want to tune the relative weights of the soft constraints, so that I can adapt the solver's priorities to a given semester.

## Implementation Decisions

### Core mode and architecture
- **Auto-solver first, with an editable backstop.** The system auto-generates a schedule, but the result is always editable on an interactive grid, with a live validator running continuously. Auto-solve "proposes," the planner disposes.
- **Bounded search space.** The solver places **only the department's own** lectures, exercises, and labs. External (other-faculty) courses and university blackout windows are immovable walls read from the catalog/skeleton.
- **Best-effort on infeasibility.** When no assignment satisfies all hard constraints (or only by badly violating soft ones), the solver returns the least-bad assignment plus a structured report of which soft constraints were violated and by how much.

### Solver technology
- **Google OR-Tools CP-SAT** (Python). Chosen over hand-rolled heuristics (which reinvent constraint handling and give no optimality signal) and commercial MILP/Gurobi (paid; CP-SAT is stronger at disjunctive scheduling).

### Data model
- **Persistent in-app catalog** is the durable spine (SQLite). Each semester only the fresh skeleton and lecturer/TA availability are re-imported; stable course metadata persists.
- **`Course`** carries: university course number; program(s); year; role (core / elective / replacement / lab); session structure (lecture + N exercise groups + optional lab); expected enrollment; room-type need; and an **`is_external`** flag (fixed forever). An external course additionally carries its own fixed day/time/room as permanent attributes — the catalog, not the skeleton, is the source of truth for external times.
- **Cohort = `(program, year)`.** A course is tagged with the *set* of cohorts it serves; shared courses span two cohorts. **Hard collision** = two courses sharing at least one cohort AND overlapping in time. Electives and replacements are handled by the soft layer, not the hard cohort graph (no per-student enrollment-intent data is modeled).
- Each cohort references the external course numbers its students take; those externals' fixed times become hard walls for that cohort.

### Time axis
- **60-minute "academic-hour" boxes** (50 min teaching + 10 min break), aligned to `:30` boundaries (08:30–09:30, 09:30–10:30, …).
- Teaching week **Sunday–Thursday**, day **08:30–18:30** (ten boxes/day). No Friday, no Saturday.
- A 2-hour lecture = 2 boxes; a lab = 4–5 consecutive boxes.
- Fixed external/blackout events are stored as arbitrary blocking intervals; they need not fit the box grid.

### Calendar layer (overlay on the weekly template)
- The solver optimizes the **abstract Sun–Thu weekly template**. A separate **dated semester calendar** overlays it.
- Calendar inputs (fed in advance): semester **start date**, **blocked dates** (holidays/occasions), **day-substitutions** (a real weekday running a different weekday's template, e.g. Tuesday-as-Wednesday).
- Calendar jobs: (a) feed the lecture-before-exercise ordering preference into the solver; (b) compute a **per-course realized-meeting-count / lost-sessions report**; (c) **flag** any realized week where a day-substitution inverts a course's lecture/exercise order. Inversions are flagged, **not prevented** by the solver (preventing them across every realized week would blow up the model).

### Constraints
**Hard (inviolable):**
- One room, one event at a time.
- A cohort is never double-booked, including against its fixed external courses.
- Blackout windows: Wed 12:30–14:30, Mon 13:30–14:30.
- Lecturer/TA availability (from the per-person grid).
- No person (lecturer or TA) in two places at once, across all their courses.
- Room capacity ≥ expected enrollment; computer courses only in the computer farm (Classroom 2).
- A course's two TA sessions never coincide.
- **Lab cross-day satisfiability**: every cohort needing a multi-day lab keeps ≥1 attainable day after its core courses are placed.

**Soft (weighted, minimized; heaviest → lightest):**
1. Electives vs. core (heaviest).
2. Electives vs. each other.
3. Avoid Biology-department electives.
4. Remote/Zoom sessions to morning / late afternoon.
5. Exercise after its course's lecture within the week (global, by `(day-index, hour)`; *every* exercise group after the lecture). Lowest weight — "good to have."

Weights are tunable by the planner.

**Freedom exploited:** ChemE-only and BioChemE-only courses may overlap each other (different audiences, different rooms).

### Solver scope
- The solver assigns **day/time AND room** for each department session.
- **TA→group assignment is given as input** (the planner decides who teaches what, externally). The solver only honors specific-TA constraints when supplied; load-balancing TAs is not the solver's job.
- The **room inventory** is fixed: Hall 1 (210), Classroom 2 (computer farm, 22), Classroom 3 (50), Classroom 4 (50), Classroom 5 (50), Hall 6 (120).

### Skeleton ingestion and validation
- Each semester: import skeleton XLSX → parse → **human-review screen** → validate against the user-defined persistent checklist of must-exist named lectures and dedicated exercise groups → solve.
- The skeleton's role is reduced to two jobs: supply this semester's offered department sessions/groups, and be the artifact the must-exist checklist validates against.

### Modules
- **Skeleton Parser** — Technion XLSX → clean offered-session domain objects, filtered to department courses by number. (Deep: messy input → domain objects.)
- **Skeleton Validator** — parsed skeleton + must-exist checklist → list of missing items. (Pure.)
- **Calendar Engine** — start date + blocked dates + day-substitutions → realized day sequence, per-course meeting counts, lost-session warnings, swap-induced order-inversion flags. (Pure.)
- **Constraint Evaluator** — an assignment → all hard/soft violations with scores. *Central deep module*, reused by both the solver's explanation and the live editor backstop. (Pure.)
- **Model Builder** — catalog + cohorts + externals + availability + soft ladder → a CP-SAT model. (Deep translation.)
- **Solver Runner** — runs CP-SAT → best-effort assignment + violation report.
- **Exporters** — PDF (per cohort/room/lecturer) and CSV/Excel.
- **Catalog Store** — SQLite CRUD for durable catalog and per-semester data.
- **Web API** — thin FastAPI orchestration layer.
- **Frontend** — React/TypeScript: interactive weekly grid editor (drag-drop, live validation), per-person availability grids, import-review screen, reports, bilingual Hebrew (RTL) / English.

### Stack
- Local web app: **React/TypeScript** frontend + **FastAPI (Python)** backend + **SQLite** + **OR-Tools CP-SAT**. Runs on the planner's machine; no hosting or auth.

## Testing Decisions

**What makes a good test here:** tests assert external behavior through a module's public interface — given these domain inputs, this report/assignment/violation set — never internal representation. The four pure modules have no I/O and are tested as pure functions over hand-built fixtures with known-correct expected outputs.

**Modules under test (all layers requested):**
- **Skeleton Parser** — feed representative XLSX fixtures (including Hebrew columns, multi-row courses, `SE0xx` group codes, the `16:00–17:00`-style outliers) and assert the extracted, filtered session objects. Include malformed/edge rows to assert robust handling.
- **Skeleton Validator** — given a parsed skeleton and a checklist, assert the exact set of missing items (present, absent, partially-present groups).
- **Calendar Engine** — given start date + blocks + substitutions, assert the realized day sequence, per-course meeting counts, lost-session warnings, and the precise set of swap-induced order-inversion flags.
- **Constraint Evaluator** — given assignments crafted to trigger each hard and soft rule (room clash, cohort double-book vs. external, blackout, capacity, computer-farm, TA-coincidence, lab cross-day, each soft tier), assert the exact violations and scores. Highest-value test target — it is the shared correctness core.
- **Model Builder + Solver Runner** — small hand-built scenarios with a known correct (or known-infeasible) outcome; assert the solver finds a valid assignment, respects every hard constraint, and that the best-effort/violation-report path triggers on infeasibility.
- **Exporters** — golden-file comparison of generated PDF/CSV/Excel output against approved fixtures.
- **API integration tests** — end-to-end happy path over FastAPI: import → review → validate → solve → export, asserting the wired pipeline produces a consistent schedule and reports.

**Prior art:** none yet — this is a greenfield repo. Establish the fixture-driven pure-function test pattern with the four core modules first; later modules follow it.

## Out of Scope

- **University XLSX writeback.** The system does not write the final schedule back into the Technion skeleton format. Outputs are in-app grids, PDF timetables, and flat CSV/Excel only.
- **Auto-solving external/shared courses.** External and shared-from-other-faculty courses are fixed walls; the solver never moves them or negotiates with other departments.
- **TA load-balancing / TA→group assignment.** Done externally by the planner; only fed in as constraints.
- **Per-student / study-plan modeling.** Collisions use the cohort model; individual elective/replacement choices are not simulated.
- **Multi-user / collaboration / auth.** Single planner, local app.
- **Hosted deployment.** Local-only for the first version (the stack permits later hosting without rewrite).
- **Preventing swap-induced order inversions in the solver.** These are flagged in the calendar report, not solved away.
- **Full-year scheduling in one run.** The system runs per semester (Winter / Spring).
- **Issue-tracker publication.** No tracker is configured; this PRD lives as a repo document. Run `/setup-matt-pocock-skills` then `/to-issues` to convert to tracked issues.

## Further Notes

- **Programs:** the source doc lists Chemical Engineering, Biochemical Engineering, and "Chemical Engineering Chemistry" (ChemE–Chemistry). Confirm whether the third is a full program with its own cohorts or a track within ChemE before building cohort enumeration.
- **Color taxonomy:** the doc's color coding (yellow = ChemE core, green = BioChemE core, light-blue = shared core, orange = shared electives, blue = replacements) maps directly onto the `role` + `cohort-set` model and can drive grid coloring in the UI.
- **Hebrew/RTL:** the skeleton is Hebrew; the UI is bilingual. Course objects should retain both Hebrew and English descriptions (both are present in the skeleton).
- **Solver explainability** is a first-class feature, not a nice-to-have: the best-effort report is what makes the auto-solver trustworthy and the manual-edit backstop usable.
- **Example to encode as a Constraint-Evaluator test case** (from the source doc): Thermodynamics A lab offered Sunday and Wednesday; Molecular Genetics (BioChemE core) on Sunday and Intro to Biochemistry & Enzymology (ChemE core) on Wednesday at the same times — cross-day satisfiability holds because BioChemE students take the lab Wednesday and ChemE students take it Sunday.

## Implementation Status

> Updated 2026-06-13. Backend engine complete and the frontend is a built, running MVP. **73 tests passing on Python 3.14**; the app runs single-process (FastAPI serves the built SPA) through a live catalog → availability/calendar → skeleton-pinned solve → edit → CSV / per-cohort-grid PDF pipeline.

### What is built

Implemented from the ground up, committed module-by-module. Stack as specified: Python 3.14 · OR-Tools CP-SAT · FastAPI · SQLite · React/TypeScript.

**Backend engine (`backend/schedy/`):**

| Module | Status | Notes |
| --- | --- | --- |
| `domain.py` | ✅ | Time grid (Sun–Thu, ten 60-min `:30`-aligned boxes), `Cohort`/`Room`/`Session`/`FixedEvent`, soft-weight ladder |
| `calendar_engine.py` (pure) | ✅ | Realize dated days, meeting counts/deficits, swap-induced order-inversion flags |
| `evaluator.py` (pure) | ✅ | Correctness core — every hard + soft violation; reused by solver *and* live editor |
| `parser.py` + `validator.py` (pure) | ✅ | Technion XLSX → sessions (columns matched by Hebrew header); must-exist checklist matching; smoke-tested against the real `raw/30.4.26.XLSX` |
| `model_builder.py` + `solver.py` | ✅ | CP-SAT model (hard no-overlap + weighted soft objective); best-effort solve + attached evaluator report |
| `catalog.py` / `store.py` / `api.py` / `exporters.py` | ✅ | Course aggregate → Problem; SQLite persistence; FastAPI orchestration; CSV + Hebrew-capable PDF export |
| `sample_data.py` | ✅ | Illustrative demo catalog (both programs, years 1–4, cross-day lab, electives, Zoom, computer-farm, external wall); `POST /catalog/seed` |

**Frontend (`frontend/`):** built and running (Vite + React + TS), single-process via FastAPI `StaticFiles`. Tabs:
- **Schedule** — drag-drop weekly grid with live re-validation; blocks colored by role and sized to their length; blackout + external-course walls overlaid; per-cohort/room/lecturer views; role/wall legend; CSV/PDF export; one-click sample-and-solve on the empty state.
- **Catalog** — full course editor + one-click "Load sample catalog".
- **Availability** — per-person click grid → hard `person_unavailable` walls on re-solve.
- **Calendar** — semester dates, blocked days, day-substitutions; Analyze → per-weekday teaching counts, uneven sessions, order inversions.
- **Import** — Technion XLSX upload, parsed and filtered to the catalog into an
  editable table (day/time/group); grid-aligned times pin as hard placements (🔒).

Exports: CSV and a printable PDF — one weekly Sun–Thu grid page **per cohort**
(Hebrew names, spanning blocks), or a flat assignments list.

Bilingual Hebrew-RTL / English throughout.

**Project infrastructure:** `environment.yml` (conda, Python 3.14), GitHub Actions (CI, CodeQL, MkDocs → gh-pages), MkDocs Material docs (builds clean under `--strict`), `launcher.py` one-command local/desktop launch, git history with one commit per feature.

### Honest caveats

- **Lab cross-day satisfiability uses a guided-repair loop.** Cross-day lab alternatives are excluded from the strict per-cohort no-overlap (a lab may overlap the cohort's course on its "off" day) and governed by the "≥1 clash-free day per cohort" rule. The base model omits that rule (it bloats the model and rarely binds); when the evaluator flags `lab_cross_day_unsatisfiable`, the solver encodes the constraint natively for the offending lab groups and re-solves (up to N rounds), falling back to the best-effort flagged schedule only if no clash-free arrangement exists.
- **Skeleton day/time → hard fixed placement (option a).** When the skeleton gives a session a concrete, grid-aligned weekday/time, that `(day, box)` is pinned as a hard constraint in CP-SAT and flagged `fixed_placement` by the evaluator if moved; the grid locks such blocks (🔒). The import table is editable (correct day/time/group before solving). Validated on the real Technion fixture (96% of timed rows pin). **By design:** labs are never pinned (the skeleton carries no labs — labs are department-scheduled), and the skeleton's *room* strings are university-wide locations, ignored for solving (the solver assigns our six rooms; no room collisions are expected).
- **Two design questions remain open** (see Further Notes): whether ChemE–Chemistry is a full program or a track within ChemE, and confirmation of the color→role mapping. Both affect cohort enumeration and should be resolved before populating a real catalog.

### Suggested next steps

1. Make the import table editable (correct day/time/group, persist back to `offered_rows`) — parsed times already feed the solve as hard fixed placements; this adds human review/correction before solving. Then extend pinning to labs and map skeleton room strings to the room inventory.
2. A native CP-SAT encoding (or guided repair loop) for lab cross-day satisfiability so the solver honours it natively rather than only flagging it.
3. Resolve the two open design questions (ChemE–Chemistry program-vs-track; color taxonomy) and populate a real catalog.
4. PDF polish: per-cohort/per-room timetable pages (grid layout) rather than a single flat table.
