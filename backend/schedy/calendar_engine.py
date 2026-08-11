"""Calendar Engine (pure).

Overlays a dated semester calendar on top of the abstract Sunday..Thursday
weekly template that the solver fills. It answers three questions the PRD asks:

  1. Which real dates teach, and which weekday-template does each run?
     (Day-substitutions let a real Tuesday run the Wednesday template.)
  2. How many real meetings does each placed session actually get, and which
     sessions come up short ("lost/uneven sessions")?
  3. Which courses meet their exercise before their lecture, and why — because
     the weekly template itself orders them that way (repeats every week), or
     because a day-substitution flipped one particular week? (Flagged, never
     prevented.)

No I/O — everything is a pure function over the inputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from .domain import (
    Problem,
    Schedule,
    SessionType,
    day_rank,
)

# Python's date.weekday(): Monday=0 .. Sunday=6. Map to our Sunday=0 .. Thursday=4.
_PY_WEEKDAY_TO_TEMPLATE = {6: 0, 0: 1, 1: 2, 2: 3, 3: 4}  # Sun, Mon, Tue, Wed, Thu


def natural_template(d: date) -> int | None:
    """Weekday-template index 0..4 a date naturally runs, or None for Fri/Sat."""
    return _PY_WEEKDAY_TO_TEMPLATE.get(d.weekday())


@dataclass
class SemesterCalendar:
    """The dated calendar fed in advance each semester."""
    start: date
    end: date  # inclusive
    blocked_dates: set[date] = field(default_factory=set)
    # real date -> weekday-template index it should run instead (substitution).
    substitutions: dict[date, int] = field(default_factory=dict)


@dataclass(frozen=True)
class RealizedDay:
    date: date
    week_index: int          # 0-based, (date - start) // 7
    template: int | None     # weekday template actually run (after substitution)
    is_teaching: bool
    substituted: bool        # True if a substitution changed its template


@dataclass(frozen=True)
class LostSession:
    session_id: str
    course_number: str
    weekday_template: int
    realized: int
    baseline: int  # the busiest weekday's meeting count this semester

    @property
    def deficit(self) -> int:
        return self.baseline - self.realized


# Why an exercise lands before its lecture.
CAUSE_TEMPLATE_ORDER = "template_order"  # the template orders them so; every week
CAUSE_SUBSTITUTION = "substitution"      # a day-swap flipped this one week


@dataclass(frozen=True)
class OrderInversion:
    course_number: str
    week_index: int          # first realized week affected
    lecture_date: date
    exercise_date: date
    exercise_group: str | None
    cause: str = CAUSE_SUBSTITUTION
    weeks: int = 1           # how many realized weeks this same inversion hits
    # Academic-hour boxes. The two dates are equal when both sit on the same
    # weekday, and then only the boxes tell the pair apart.
    lecture_box: int = 0
    exercise_box: int = 0


# --------------------------------------------------------------------------- #
# 1. Realize the calendar
# --------------------------------------------------------------------------- #

def realize(cal: SemesterCalendar) -> list[RealizedDay]:
    """Expand the calendar into the dated sequence of teaching/non-teaching days."""
    days: list[RealizedDay] = []
    d = cal.start
    while d <= cal.end:
        week_index = (d - cal.start).days // 7
        substituted = d in cal.substitutions
        template = cal.substitutions[d] if substituted else natural_template(d)
        is_teaching = (
            template is not None
            and d not in cal.blocked_dates
        )
        days.append(
            RealizedDay(
                date=d,
                week_index=week_index,
                template=template,
                is_teaching=is_teaching,
                substituted=substituted,
            )
        )
        d += timedelta(days=1)
    return days


def week_anchor(cal: SemesterCalendar) -> int:
    """The weekday-template the semester's first teaching day runs (0..4).

    This is the day students actually start on, so it is where the teaching week
    begins for every ordering question. A semester opening on a Tuesday anchors
    at 2: its weeks run Tue, Wed, Thu, Sun, Mon. Defaults to Sunday (0) for a
    calendar with no teaching days at all.
    """
    for rd in realize(cal):
        if rd.is_teaching and rd.template is not None:
            return rd.template
    return 0


def teaching_days_by_template(cal: SemesterCalendar) -> dict[int, list[date]]:
    """For each weekday-template 0..4, the real dates that teach it this semester."""
    out: dict[int, list[date]] = {t: [] for t in range(5)}
    for rd in realize(cal):
        if rd.is_teaching and rd.template is not None:
            out[rd.template].append(rd.date)
    return out


# --------------------------------------------------------------------------- #
# 2. Per-session meeting counts + lost/uneven sessions
# --------------------------------------------------------------------------- #

def meeting_counts(
    cal: SemesterCalendar, schedule: Schedule, problem: Problem
) -> dict[str, int]:
    """How many real meetings each placed session gets (by its template weekday)."""
    by_template = teaching_days_by_template(cal)
    counts: dict[str, int] = {}
    for session_id, placement in schedule.placements.items():
        counts[session_id] = len(by_template.get(placement.day, []))
    return counts


def lost_sessions(
    cal: SemesterCalendar, schedule: Schedule, problem: Problem
) -> list[LostSession]:
    """Sessions that meet fewer times than the busiest weekday — the deficit warnings.

    Baseline = the maximum meeting count any teaching weekday gets this semester.
    A session placed on a weekday that teaches fewer times is flagged with its deficit.
    """
    by_template = teaching_days_by_template(cal)
    used_templates = {p.day for p in schedule.placements.values()}
    if not used_templates:
        return []
    baseline = max((len(by_template.get(t, [])) for t in used_templates), default=0)

    out: list[LostSession] = []
    for session_id, placement in schedule.placements.items():
        realized = len(by_template.get(placement.day, []))
        if realized < baseline:
            session = problem.session(session_id)
            out.append(
                LostSession(
                    session_id=session_id,
                    course_number=session.course_number,
                    weekday_template=placement.day,
                    realized=realized,
                    baseline=baseline,
                )
            )
    out.sort(key=lambda x: (-x.deficit, x.session_id))
    return out


# --------------------------------------------------------------------------- #
# 3. Lecture-before-exercise inversions, with their cause
# --------------------------------------------------------------------------- #

def order_inversions(
    cal: SemesterCalendar, schedule: Schedule, problem: Problem
) -> list[OrderInversion]:
    """Courses whose exercise meets before its lecture, and why.

    Weeks are cut from the semester's start date, so a week runs from the
    starting weekday onwards — a Tuesday start gives Tue..Mon weeks. Template
    order is read the same way (`day_rank` against `problem.week_anchor`), which
    keeps the two views consistent: inside an unsubstituted week, rank order and
    date order always agree.

    Two causes, reported differently because they need different responses:

      * CAUSE_TEMPLATE_ORDER — the template itself puts the exercise first once
        the semester's own week start is accounted for. It recurs every week, so
        it collapses to one entry carrying `weeks`; the fix is to move a session.
      * CAUSE_SUBSTITUTION — a day-substitution flipped one otherwise-correct
        week. One entry per affected week; the fix, if any, is that week's swap.
    """
    anchor = problem.week_anchor
    # Group placed sessions per course into lectures and exercises.
    by_course: dict[str, dict[str, list[tuple[int, int, str | None]]]] = {}
    for session_id, placement in schedule.placements.items():
        s = problem.session(session_id)
        if s.type not in (SessionType.LECTURE, SessionType.EXERCISE):
            continue
        bucket = by_course.setdefault(s.course_number, {"lecture": [], "exercise": []})
        key = "lecture" if s.type is SessionType.LECTURE else "exercise"
        bucket[key].append((placement.day, placement.start_box, s.group))

    realized = realize(cal)
    # week_index -> template -> list of dates (teaching only)
    weeks: dict[int, dict[int, list[date]]] = {}
    for rd in realized:
        if rd.is_teaching and rd.template is not None:
            weeks.setdefault(rd.week_index, {}).setdefault(rd.template, []).append(rd.date)

    out: list[OrderInversion] = []
    for course, parts in by_course.items():
        lectures = parts["lecture"]
        exercises = parts["exercise"]
        if not lectures or not exercises:
            continue
        # Intended order: the lecture the week reaches first.
        lec_rank, lec_box, lec_day = min(
            (day_rank(d, anchor), b, d) for d, b, _ in lectures)

        for ex_day, ex_box, ex_group in exercises:
            ex_rank = day_rank(ex_day, anchor)
            if (ex_rank, ex_box) == (lec_rank, lec_box):
                continue  # simultaneous, not out of order — a clash check owns it
            template_inverted = (ex_rank, ex_box) < (lec_rank, lec_box)

            # Realized weeks where this exercise beats the lecture. Compared as
            # (date, box), not date alone: when the two share a weekday their
            # dates are equal every week and the box is the whole difference.
            hits: list[tuple[int, date, date]] = []
            for week_index in sorted(weeks):
                by_template = weeks[week_index]
                lec_dates = by_template.get(lec_day, [])
                if not lec_dates:
                    continue
                earliest_lecture = min(lec_dates)
                for ex_date in by_template.get(ex_day, []):
                    if (ex_date, ex_box) < (earliest_lecture, lec_box):
                        hits.append((week_index, earliest_lecture, ex_date))
            if not hits:
                continue

            if template_inverted:
                # Same inversion every week — report it once, with its reach.
                week_index, lecture_date, exercise_date = hits[0]
                out.append(
                    OrderInversion(
                        course_number=course,
                        week_index=week_index,
                        lecture_date=lecture_date,
                        exercise_date=exercise_date,
                        exercise_group=ex_group,
                        cause=CAUSE_TEMPLATE_ORDER,
                        weeks=len(hits),
                        lecture_box=lec_box,
                        exercise_box=ex_box,
                    )
                )
            else:
                for week_index, lecture_date, exercise_date in hits:
                    out.append(
                        OrderInversion(
                            course_number=course,
                            week_index=week_index,
                            lecture_date=lecture_date,
                            exercise_date=exercise_date,
                            exercise_group=ex_group,
                            cause=CAUSE_SUBSTITUTION,
                            weeks=1,
                            lecture_box=lec_box,
                            exercise_box=ex_box,
                        )
                    )
    # Recurring inversions first — they cost the most weeks.
    out.sort(key=lambda x: (-x.weeks, x.week_index, x.course_number))
    return out
