# Constraints reference

## Hard constraints (inviolable)

| Rule | Where enforced |
| --- | --- |
| One room, one event at a time | model `_hard_room`, evaluator `room_double_booked` |
| A cohort `(program, year)` is never double-booked, incl. vs external cores | model `_hard_cohort`, evaluator `cohort_double_booked` |
| Blackout windows (Wed 12:30–14:30, Mon 13:30–14:30) | model `_hard_fixed_events`, evaluator `blackout_violation` |
| Lecturer/TA availability | model `_hard_availability`, evaluator `person_unavailable` |
| No person in two places at once (across all their courses) | model `_hard_person`, evaluator `person_double_booked` |
| Room capacity ≥ enrolment | room domain restriction, evaluator `capacity_exceeded` |
| Computer courses only in the computer farm (Classroom 2) | room domain restriction, evaluator `computer_farm_required` |
| A course's two TA sessions never coincide | model `_hard_same_course_ta`, evaluator `ta_sessions_coincide` |
| Graduate-level courses never overlap (grad×grad, grad×joint) | model `_hard_grad_level`, evaluator `grad_overlap` |
| A published session keeps its room, not just its hour | room domain restriction, evaluator `room_pin_broken` |
| A published session keeps its day and hour | pinned domain, evaluator `published_moved` |
| Lab cross-day satisfiability | evaluator `lab_cross_day_unsatisfiable` (post-hoc) |

**Exploited freedom:** ChemE-only and BioChemE-only courses *may* overlap each
other (different audiences, different rooms) — the solver packs the week with this.

**Course level** (`CourseLevel`: `ug` / `joint` / `grad`) is who may take a course,
distinct from `role`, which is what it is. Suggested from the number — `0054`
undergraduate, `0056` joint, `0058` graduate, anything else undergraduate — and
overridable, since another faculty's graduate course follows no convention of ours.

|            | grad | joint |
| ---------- | ---- | ----- |
| **grad**   | HARD | HARD  |
| **joint**  | HARD | allowed (soft `elective_vs_elective` still applies) |

Graduate students pick a few courses from a small pool, so a clash between them is
untakeable rather than merely unfortunate. Joint courses are largely
undergraduate-attended and behave like ordinary electives among themselves.
Exempt: exercise groups of one course (already `ta_sessions_coincide`) and
cross-day lab alternatives. The rule also applies against another faculty's
graduate courses, which carry a level on their `FixedEvent` wall — they own no
cohort of ours, so blocking by cohort would never reach them.

!!! warning "The graduate check must stay independent"
    `_check_pairwise` tests pairs in one `if/elif` chain where
    `elective_vs_elective` (soft) is evaluated first. Graduate courses are nearly
    always electives, so folding the graduate rule into that chain would let the
    soft branch win and silently downgrade a hard rule to a warning.
    `test_grad_overlap_is_hard_even_when_both_are_electives` guards this.

**Anchored is not published.** Both pin a session, and the difference is who may
override it. A *skeleton anchor* is the university's timetable: it constrains the
solver, but the planner may drag it in the editor, which scores a weight-0
`fixed_placement` notice. A *publication* is the week already handed to students:
it is frozen in day, hour **and** room, the blocks are not draggable, and moving
one anyway is a hard `published_moved`. `Session.is_published` is what separates
them — do not infer it from `fixed_room`.

## Soft ladder (weighted, minimised; heaviest → lightest)

| # | Rule | Default weight |
| --- | --- | --- |
| 1 | Electives vs core (an elective clashing a core is untakeable) | 1000 |
| 2 | Electives vs each other (so students combine electives) | 500 |
| 3 | Avoid the Biology department's electives | 200 |
| 4 | Remote/Zoom sessions to morning / late afternoon | 100 |
| 5 | Exercise after its course's lecture (global, "good to have") | 50 |

Weights live in `SoftWeights` and are tunable per semester.

## Lab cross-day satisfiability

A multi-day lab is offered on several days (e.g. Thermodynamics A on Sunday and
Wednesday). For **each cohort** served, at least one offered day must remain
clash-free against that cohort's core courses. The canonical example:

> Thermo A lab on Sunday & Wednesday. Molecular Genetics (BioChemE core) is on
> Sunday; Intro to Biochemistry & Enzymology (ChemE core) is on Wednesday. It
> works: BioChemE students take the lab Wednesday, ChemE students take it Sunday.

This is encoded as a hard check in the evaluator (it does not linearise cleanly
for CP-SAT), consistent with the evaluator being the single source of truth.
