"""Tests for the Calendar Engine — behaviour only, over hand-built calendars."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from schedy.calendar_engine import (
    CAUSE_SUBSTITUTION,
    CAUSE_TEMPLATE_ORDER,
    SemesterCalendar,
    lost_sessions,
    meeting_counts,
    natural_template,
    order_inversions,
    realize,
    teaching_days_by_template,
    week_anchor,
)
from schedy.domain import (
    Cohort,
    Program,
    Schedule,
    Session,
    SessionType,
    Problem,
)

# 2026-03-01 is a Sunday — a convenient semester anchor.
SUN = date(2026, 3, 1)
MON = date(2026, 3, 2)
TUE = date(2026, 3, 3)
WED = date(2026, 3, 4)
THU = date(2026, 3, 5)
FRI = date(2026, 3, 6)
SAT = date(2026, 3, 7)


def test_natural_template_maps_israeli_week():
    assert natural_template(SUN) == 0
    assert natural_template(MON) == 1
    assert natural_template(WED) == 3
    assert natural_template(THU) == 4
    assert natural_template(FRI) is None  # Friday: no teaching
    assert natural_template(SAT) is None  # Saturday: Shabbat


def test_realize_marks_weekend_and_blocked_as_non_teaching():
    cal = SemesterCalendar(start=SUN, end=SAT, blocked_dates={TUE})
    by_date = {rd.date: rd for rd in realize(cal)}
    assert by_date[SUN].is_teaching
    assert by_date[TUE].is_teaching is False  # blocked
    assert by_date[FRI].is_teaching is False  # Friday
    assert by_date[SAT].is_teaching is False  # Saturday
    assert all(rd.week_index == 0 for rd in by_date.values())


def test_substitution_runs_another_weekday_template():
    # A real Tuesday runs the Wednesday (template 3) schedule.
    cal = SemesterCalendar(start=SUN, end=THU, substitutions={TUE: 3})
    by_date = {rd.date: rd for rd in realize(cal)}
    assert by_date[TUE].template == 3
    assert by_date[TUE].substituted is True
    assert by_date[TUE].is_teaching is True
    # Wednesday template now teaches on both Tue (substituted) and Wed.
    by_template = teaching_days_by_template(cal)
    assert set(by_template[3]) == {TUE, WED}
    assert by_template[2] == []  # nothing naturally runs the Tuesday template


def _lecture(course="C1", day=0, box=0):
    return Session(
        id=f"{course}-lec", course_number=course, type=SessionType.LECTURE,
        length_boxes=2, cohorts=frozenset({Cohort(Program.CHEME, 2)}),
    )


def _exercise(course="C1", day=3, box=4, group="SE011"):
    return Session(
        id=f"{course}-ex-{group}", course_number=course, type=SessionType.EXERCISE,
        length_boxes=1, cohorts=frozenset({Cohort(Program.CHEME, 2)}), group=group,
    )


def test_meeting_counts_and_lost_sessions():
    # Three weeks; block one Wednesday so the Wed template teaches less.
    cal = SemesterCalendar(
        start=SUN,
        end=SUN + __import__("datetime").timedelta(days=20),  # 3 weeks
        blocked_dates={WED},  # one Wednesday lost
    )
    lec = _lecture(day=0, box=0)        # Sunday lecture
    ex = _exercise(day=3, box=4)        # Wednesday exercise
    problem = Problem(sessions=[lec, ex])
    schedule = Schedule()
    schedule.place(lec.id, day=0, start_box=0, room_id="hall1")
    schedule.place(ex.id, day=3, start_box=4, room_id="room3")

    counts = meeting_counts(cal, schedule, problem)
    assert counts[lec.id] == 3        # 3 Sundays
    assert counts[ex.id] == 2         # 3 Wednesdays minus 1 blocked

    lost = lost_sessions(cal, schedule, problem)
    assert len(lost) == 1
    assert lost[0].session_id == ex.id
    assert lost[0].realized == 2 and lost[0].baseline == 3
    assert lost[0].deficit == 1


def test_order_inversion_not_flagged_when_lecture_absent_that_week():
    # This Sunday runs the Wednesday (exercise) template, and no day runs the
    # Sunday (lecture) template this week. With no lecture meeting in the week,
    # there is nothing to invert against -> no flag.
    cal = SemesterCalendar(
        start=SUN,
        end=THU,
        substitutions={SUN: 3},  # this Sunday runs the Wednesday template
    )
    lec = _lecture(day=0, box=0)
    ex = _exercise(day=3, box=4)
    problem = Problem(sessions=[lec, ex])
    schedule = Schedule()
    schedule.place(lec.id, day=0, start_box=0, room_id="hall1")
    schedule.place(ex.id, day=3, start_box=4, room_id="room3")
    # No lecture day this week, so no inversion is reported.
    assert order_inversions(cal, schedule, problem) == []


def test_order_inversion_positive_case():
    # Two-day teaching week: Tue runs Wednesday-template (exercise), Wed runs
    # Sunday-template (lecture). So in the same week the exercise (Tue) falls
    # chronologically before the lecture (Wed) -> inversion.
    cal = SemesterCalendar(
        start=TUE,
        end=WED,
        substitutions={TUE: 3, WED: 0},  # Tue->Wed template, Wed->Sun template
    )
    lec = _lecture(day=0, box=0)   # template Sunday
    ex = _exercise(day=3, box=4)   # template Wednesday, after lecture in template
    problem = Problem(sessions=[lec, ex])
    schedule = Schedule()
    schedule.place(lec.id, day=0, start_box=0, room_id="hall1")
    schedule.place(ex.id, day=3, start_box=4, room_id="room3")

    inv = order_inversions(cal, schedule, problem)
    assert len(inv) == 1
    assert inv[0].course_number == "C1"
    assert inv[0].exercise_date == TUE
    assert inv[0].lecture_date == WED
    assert inv[0].exercise_group == "SE011"
    # The template order is fine; only this week's swap flipped it.
    assert inv[0].cause == CAUSE_SUBSTITUTION
    assert inv[0].weeks == 1


# --------------------------------------------------------------------------- #
# Semester start weekday: the teaching week does not have to begin on Sunday
# --------------------------------------------------------------------------- #

def test_week_anchor_is_the_first_teaching_day():
    assert week_anchor(SemesterCalendar(start=SUN, end=THU)) == 0
    assert week_anchor(SemesterCalendar(start=TUE, end=THU)) == 2
    # Fri/Sat never teach, so a weekend start rolls forward to the Sunday.
    assert week_anchor(SemesterCalendar(start=FRI, end=THU + timedelta(days=7))) == 0
    # A blocked first day rolls forward too.
    assert week_anchor(
        SemesterCalendar(start=TUE, end=THU, blocked_dates={TUE})) == 3
    # No teaching days at all -> the Sunday-first default.
    assert week_anchor(SemesterCalendar(start=FRI, end=SAT)) == 0


def _mon_lecture_thu_exercise(anchor: int):
    """Lecture on Monday, exercise on Thursday, judged from `anchor`."""
    lec = _lecture(day=1, box=0)
    ex = _exercise(day=4, box=4)
    problem = Problem(sessions=[lec, ex], week_anchor=anchor)
    schedule = Schedule()
    schedule.place(lec.id, day=1, start_box=0, room_id="hall1")
    schedule.place(ex.id, day=4, start_box=4, room_id="room3")
    return problem, schedule


def test_sunday_start_leaves_monday_lecture_before_thursday_exercise():
    cal = SemesterCalendar(start=SUN, end=SUN + timedelta(days=27))  # 4 weeks
    problem, schedule = _mon_lecture_thu_exercise(anchor=0)
    assert order_inversions(cal, schedule, problem) == []


def test_mid_week_start_reports_one_recurring_inversion_not_one_per_week():
    # Semester opens on a Tuesday, so its weeks run Tue..Mon: the Thursday
    # exercise is reached before the Monday lecture, every single week.
    cal = SemesterCalendar(start=TUE, end=TUE + timedelta(days=27))  # 4 weeks
    problem, schedule = _mon_lecture_thu_exercise(anchor=2)

    inv = order_inversions(cal, schedule, problem)
    assert len(inv) == 1                      # collapsed, not one row per week
    assert inv[0].cause == CAUSE_TEMPLATE_ORDER
    assert inv[0].weeks == 4                  # ...but its reach is reported
    assert inv[0].week_index == 0
    assert inv[0].exercise_date == THU        # first Thursday
    assert inv[0].lecture_date == MON + timedelta(days=7)  # the Monday after it


def test_same_weekday_inversion_is_caught_by_the_box_not_the_date():
    # Lecture and exercise both on Monday, exercise the earlier hour. The dates
    # are equal every week, so only the box distinguishes them — comparing bare
    # dates would silently drop this.
    cal = SemesterCalendar(start=SUN, end=SUN + timedelta(days=20))  # 3 weeks
    lec = _lecture(day=1, box=5)
    ex = _exercise(day=1, box=2)
    problem = Problem(sessions=[lec, ex])
    schedule = Schedule()
    schedule.place(lec.id, day=1, start_box=5, room_id="hall1")
    schedule.place(ex.id, day=1, start_box=2, room_id="room3")

    inv = order_inversions(cal, schedule, problem)
    assert len(inv) == 1
    assert inv[0].cause == CAUSE_TEMPLATE_ORDER
    assert inv[0].weeks == 3                            # every Monday
    assert inv[0].exercise_date == inv[0].lecture_date  # same day...
    assert (inv[0].exercise_box, inv[0].lecture_box) == (2, 5)  # ...earlier hour

    # The reverse order on the same day is fine and must stay unreported.
    ok = Schedule()
    ok.place(lec.id, day=1, start_box=2, room_id="hall1")
    ok.place(ex.id, day=1, start_box=5, room_id="room3")
    assert order_inversions(cal, ok, problem) == []
