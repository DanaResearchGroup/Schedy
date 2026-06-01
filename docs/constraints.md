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
| Lab cross-day satisfiability | evaluator `lab_cross_day_unsatisfiable` (post-hoc) |

**Exploited freedom:** ChemE-only and BioChemE-only courses *may* overlap each
other (different audiences, different rooms) — the solver packs the week with this.

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
