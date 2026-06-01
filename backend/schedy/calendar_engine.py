"""Calendar Engine (pure).

Overlays a dated semester calendar on top of the abstract Sunday..Thursday
weekly template that the solver fills. It answers three questions the PRD asks:

  1. Which real dates teach, and which weekday-template does each run?
     (Day-substitutions let a real Tuesday run the Wednesday template.)
  2. How many real meetings does each placed session actually get, and which
     sessions come up short ("lost/uneven sessions")?
  3. In which realized weeks does a day-substitution invert a course's intended
     lecture-before-exercise order? (Flagged, never prevented.)

No I/O — everything is a pure function over the inputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from .domain import (
    Problem,
    Schedule,
    SessionType,
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


@dataclass(frozen=True)
class OrderInversion:
    course_number: str
    week_index: int
    lecture_date: date
    exercise_date: date
    exercise_group: str | None


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
# 3. Swap-induced lecture-before-exercise inversions
# --------------------------------------------------------------------------- #

def order_inversions(
    cal: SemesterCalendar, schedule: Schedule, problem: Problem
) -> list[OrderInversion]:
    """Realized weeks where a substitution flips a course's lecture/exercise order.

    The template intends lecture before exercise (by day-index, then box). A
    day-substitution can make an exercise's real date fall before its lecture's
    real date within a single realized week. Those weeks are flagged.
    """
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
        # Intended order: earliest lecture by (day, box).
        lec_day, lec_box, _ = min(lectures, key=lambda t: (t[0], t[1]))
        for week_index, by_template in weeks.items():
            lec_dates = by_template.get(lec_day, [])
            if not lec_dates:
                continue
            earliest_lecture = min(lec_dates)
            for ex_day, ex_box, ex_group in exercises:
                # Only consider exercises the template places after the lecture.
                if (ex_day, ex_box) <= (lec_day, lec_box):
                    continue
                for ex_date in by_template.get(ex_day, []):
                    if ex_date < earliest_lecture:
                        out.append(
                            OrderInversion(
                                course_number=course,
                                week_index=week_index,
                                lecture_date=earliest_lecture,
                                exercise_date=ex_date,
                                exercise_group=ex_group,
                            )
                        )
    out.sort(key=lambda x: (x.week_index, x.course_number))
    return out
