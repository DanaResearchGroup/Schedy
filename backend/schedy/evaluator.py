"""Constraint Evaluator (pure) — the correctness core of Schedy.

Given a Problem and a Schedule (an assignment of sessions to day/box/room), it
returns every hard and soft constraint violation with a human-readable message
and, for soft violations, the weight that feeds the solver's objective.

This single module is reused twice: the Solver Runner uses it to *explain* a
best-effort result, and the interactive editor uses it as the *live validator*
backstop. Keeping the rules here (and only here) means both paths agree exactly.

No I/O — a pure function of (Problem, Schedule).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .domain import (
    CourseRole,
    Cohort,
    DayInterval,
    Problem,
    Schedule,
    Session,
    SessionType,
)

HARD = "hard"
SOFT = "soft"


@dataclass(frozen=True)
class Violation:
    kind: str                         # machine code, e.g. "room_double_booked"
    severity: str                     # HARD | SOFT
    message: str
    session_ids: tuple[str, ...] = ()
    weight: int = 0                   # soft penalty contribution (0 for hard)


@dataclass
class EvaluationResult:
    violations: list[Violation] = field(default_factory=list)

    @property
    def hard(self) -> list[Violation]:
        return [v for v in self.violations if v.severity == HARD]

    @property
    def soft(self) -> list[Violation]:
        return [v for v in self.violations if v.severity == SOFT]

    @property
    def is_feasible(self) -> bool:
        return not self.hard

    @property
    def soft_penalty(self) -> int:
        return sum(v.weight for v in self.soft)


# --------------------------------------------------------------------------- #
# Internal placed-session view
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class _Placed:
    session: Session
    day: int
    start_box: int
    room_id: str
    interval: DayInterval


def _placed(problem: Problem, schedule: Schedule) -> list[_Placed]:
    out: list[_Placed] = []
    for sid, p in schedule.placements.items():
        s = problem.session(sid)
        out.append(_Placed(s, p.day, p.start_box, p.room_id, s.interval(p)))
    return out


def _is_elective(s: Session) -> bool:
    return s.role is CourseRole.ELECTIVE


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #

def evaluate(problem: Problem, schedule: Schedule) -> EvaluationResult:
    placed = _placed(problem, schedule)
    w = problem.soft_weights
    violations: list[Violation] = []

    _check_pairwise(placed, w, violations)
    _check_vs_fixed_events(problem, placed, w, violations)
    _check_single_session(problem, placed, w, violations)
    _check_fixed_placement(placed, violations)
    _check_lecture_before_exercise(placed, w, violations)
    _check_lab_cross_day(problem, placed, violations)

    return EvaluationResult(violations)


# --------------------------------------------------------------------------- #
# Pairwise checks between placed department sessions
# --------------------------------------------------------------------------- #

def _check_pairwise(placed, w, out: list[Violation]) -> None:
    for i in range(len(placed)):
        for j in range(i + 1, len(placed)):
            a, b = placed[i], placed[j]
            if not a.interval.overlaps(b.interval):
                continue
            sa, sb = a.session, b.session
            ids = (sa.id, sb.id)

            if a.room_id == b.room_id:
                out.append(Violation(
                    "room_double_booked", HARD,
                    f"{sa.id} and {sb.id} share room {a.room_id} at overlapping times.",
                    ids,
                ))

            shared_people = set(sa.people) & set(sb.people)
            if shared_people:
                out.append(Violation(
                    "person_double_booked", HARD,
                    f"{', '.join(sorted(shared_people))} is double-booked across "
                    f"{sa.id} and {sb.id}.",
                    ids,
                ))

            if (sa.type is SessionType.EXERCISE and sb.type is SessionType.EXERCISE
                    and sa.course_number == sb.course_number):
                out.append(Violation(
                    "ta_sessions_coincide", HARD,
                    f"TA sessions {sa.id} and {sb.id} of course "
                    f"{sa.course_number} run at the same time.",
                    ids,
                ))

            ae, be = _is_elective(sa), _is_elective(sb)
            shared_cohorts = sa.cohorts & sb.cohorts
            if ae and be:
                out.append(Violation(
                    "elective_vs_elective", SOFT,
                    f"Electives {sa.id} and {sb.id} overlap; students cannot take both.",
                    ids, weight=w.elective_vs_elective,
                ))
            elif (ae or be) and shared_cohorts:
                out.append(Violation(
                    "elective_vs_core", SOFT,
                    f"Elective overlaps a core course for {_fmt(shared_cohorts)} "
                    f"({sa.id}, {sb.id}).",
                    ids, weight=w.elective_vs_core,
                ))
            elif shared_cohorts:  # neither elective
                out.append(Violation(
                    "cohort_double_booked", HARD,
                    f"{_fmt(shared_cohorts)} double-booked across {sa.id} and {sb.id}.",
                    ids,
                ))


# --------------------------------------------------------------------------- #
# Placed sessions vs immovable fixed events (externals + blackouts)
# --------------------------------------------------------------------------- #

def _check_vs_fixed_events(problem, placed, w, out: list[Violation]) -> None:
    for pl in placed:
        s = pl.session
        for fe in problem.fixed_events:
            if not pl.interval.overlaps(fe.interval):
                continue
            if fe.is_blackout:
                out.append(Violation(
                    "blackout_violation", HARD,
                    f"{s.id} falls inside blackout window '{fe.label}'.",
                    (s.id,),
                ))
                continue
            if fe.room_id and fe.room_id == pl.room_id:
                out.append(Violation(
                    "room_double_booked", HARD,
                    f"{s.id} shares room {pl.room_id} with external '{fe.label}'.",
                    (s.id,),
                ))
            shared = s.cohorts & fe.cohorts
            if shared:
                if _is_elective(s):
                    out.append(Violation(
                        "elective_vs_core", SOFT,
                        f"Elective {s.id} overlaps external core '{fe.label}' "
                        f"for {_fmt(shared)}.",
                        (s.id,), weight=w.elective_vs_core,
                    ))
                else:
                    out.append(Violation(
                        "cohort_double_booked", HARD,
                        f"{_fmt(shared)} double-booked: {s.id} vs external "
                        f"'{fe.label}'.",
                        (s.id,),
                    ))

        # Biology-department electives to soft-avoid.
        if _is_elective(s):
            for bio in problem.biology_intervals:
                if pl.interval.overlaps(bio):
                    out.append(Violation(
                        "avoid_biology", SOFT,
                        f"Elective {s.id} overlaps a Biology-department offering.",
                        (s.id,), weight=w.avoid_biology,
                    ))


# --------------------------------------------------------------------------- #
# Single-session checks
# --------------------------------------------------------------------------- #

def _check_single_session(problem, placed, w, out: list[Violation]) -> None:
    for pl in placed:
        s = pl.session
        room = problem.room(pl.room_id)

        if s.expected_enrollment > room.capacity:
            out.append(Violation(
                "capacity_exceeded", HARD,
                f"{s.id} expects {s.expected_enrollment} > room {room.id} "
                f"capacity {room.capacity}.",
                (s.id,),
            ))

        if s.needs_computer_farm and not room.is_computer_farm:
            out.append(Violation(
                "computer_farm_required", HARD,
                f"{s.id} needs the computer farm but is in {room.id}.",
                (s.id,),
            ))

        # Availability: every occupied (day, box) must be free for all people.
        for person in s.people:
            unavail = problem.availability.get(person, set())
            for i in range(s.length_boxes):
                cell = (pl.day, pl.start_box + i)
                if cell in unavail:
                    out.append(Violation(
                        "person_unavailable", HARD,
                        f"{person} is unavailable at "
                        f"day {pl.day} box {pl.start_box + i} but assigned {s.id}.",
                        (s.id,),
                    ))
                    break

        # Zoom/remote sessions should sit in the morning or late afternoon.
        if s.is_remote:
            morning = pl.start_box <= 1
            late = pl.start_box >= 7
            if not (morning or late):
                out.append(Violation(
                    "zoom_timing", SOFT,
                    f"Remote session {s.id} sits in the middle of the day.",
                    (s.id,), weight=w.zoom_timing,
                ))


# --------------------------------------------------------------------------- #
# Skeleton-fixed placement: a pinned session must stay on its (day, box)
# --------------------------------------------------------------------------- #

def _check_fixed_placement(placed, out: list[Violation]) -> None:
    for pl in placed:
        s = pl.session
        if (s.fixed_day is not None and pl.day != s.fixed_day) or \
           (s.fixed_box is not None and pl.start_box != s.fixed_box):
            out.append(Violation(
                "fixed_placement", HARD,
                f"{s.id} is pinned by the skeleton to "
                f"day {s.fixed_day} box {s.fixed_box} but sits at "
                f"day {pl.day} box {pl.start_box}.",
                (s.id,),
            ))


# --------------------------------------------------------------------------- #
# Soft: every exercise should fall after its course's lecture
# --------------------------------------------------------------------------- #

def _check_lecture_before_exercise(placed, w, out: list[Violation]) -> None:
    by_course: dict[str, dict[str, list[_Placed]]] = {}
    for pl in placed:
        if pl.session.type in (SessionType.LECTURE, SessionType.EXERCISE):
            b = by_course.setdefault(pl.session.course_number,
                                     {"lecture": [], "exercise": []})
            key = "lecture" if pl.session.type is SessionType.LECTURE else "exercise"
            b[key].append(pl)
    for course, parts in by_course.items():
        if not parts["lecture"] or not parts["exercise"]:
            continue
        lec = min(parts["lecture"], key=lambda p: (p.day, p.start_box))
        for ex in parts["exercise"]:
            if (ex.day, ex.start_box) < (lec.day, lec.start_box):
                out.append(Violation(
                    "lecture_before_exercise", SOFT,
                    f"Exercise {ex.session.id} is scheduled before lecture "
                    f"{lec.session.id} of course {course}.",
                    (ex.session.id, lec.session.id),
                    weight=w.lecture_before_exercise,
                ))


# --------------------------------------------------------------------------- #
# Hard: lab cross-day satisfiability
# --------------------------------------------------------------------------- #

def _check_lab_cross_day(problem, placed, out: list[Violation]) -> None:
    by_id = {pl.session.id: pl for pl in placed}
    groups = problem.lab_alternatives()
    if not groups:
        return

    # Busy intervals per cohort from non-lab core/replacement sessions + externals.
    def cohort_busy(cohort: Cohort) -> list[DayInterval]:
        intervals: list[DayInterval] = []
        for pl in placed:
            if pl.session.lab_group:
                continue
            if _is_elective(pl.session):
                continue
            if cohort in pl.session.cohorts:
                intervals.append(pl.interval)
        for fe in problem.fixed_events:
            if not fe.is_blackout and cohort in fe.cohorts:
                intervals.append(fe.interval)
        return intervals

    for group_id, sessions in groups.items():
        cohorts: set[Cohort] = set()
        for s in sessions:
            cohorts |= s.cohorts
        for cohort in cohorts:
            busy = cohort_busy(cohort)
            attainable = False
            for s in sessions:
                pl = by_id.get(s.id)
                if pl is None:
                    continue
                if not any(pl.interval.overlaps(b) for b in busy):
                    attainable = True
                    break
            if not attainable:
                out.append(Violation(
                    "lab_cross_day_unsatisfiable", HARD,
                    f"{cohort.label} has no clash-free day for lab group "
                    f"'{group_id}'.",
                    tuple(s.id for s in sessions),
                ))


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _fmt(cohorts) -> str:
    return ", ".join(sorted(c.label for c in cohorts))
