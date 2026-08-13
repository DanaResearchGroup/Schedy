"""Pinning a session's room, not just its hour.

`fixed_day`/`fixed_box` pin when a session runs but leave the room to the solver.
That is fine for a skeleton import — the university dictates the hour, not our
room — but it is not enough to freeze a *published* schedule: the solver would
honour every published time while quietly reshuffling rooms. `fixed_room` closes
that gap, and is the prerequisite for the publish/append workflow.
"""

from __future__ import annotations

from schedy.domain import (
    Cohort,
    CourseRole,
    Problem,
    Program,
    Schedule,
    Session,
    SessionType,
)
from schedy.evaluator import evaluate
from schedy.solver import solve

CHEME2 = Cohort(Program.CHEME, 2)


def lecture(sid, course, **kw):
    return Session(id=sid, course_number=course, type=SessionType.LECTURE,
                   length_boxes=2, cohorts=frozenset({CHEME2}),
                   role=CourseRole.CORE, **kw)


def _kinds(ev):
    return {v.kind for v in ev.violations}


# ---- the model honours the pin ---------------------------------------- #

def test_solver_places_a_pinned_session_in_its_room():
    s = lecture("a-lec", "00540315", fixed_room="room3")
    result = solve(Problem(sessions=[s], fixed_events=[]), time_limit_s=5)
    assert result.solved
    assert result.schedule.placements["a-lec"].room_id == "room3"


def test_a_fully_pinned_session_keeps_day_box_and_room():
    s = lecture("a-lec", "00540315", fixed_day=2, fixed_box=3, fixed_room="hall6")
    result = solve(Problem(sessions=[s], fixed_events=[]), time_limit_s=5)
    assert result.solved
    p = result.schedule.placements["a-lec"]
    assert (p.day, p.start_box, p.room_id) == (2, 3, "hall6")


def test_pinning_survives_pressure_from_a_second_session():
    # The free session must move around the pinned one, not the reverse.
    pinned = lecture("a-lec", "00540315", fixed_day=0, fixed_box=0, fixed_room="room3")
    free = lecture("b-lec", "00540316")
    result = solve(Problem(sessions=[pinned, free], fixed_events=[]), time_limit_s=5)
    assert result.solved
    a = result.schedule.placements["a-lec"]
    assert (a.day, a.start_box, a.room_id) == (0, 0, "room3")


def test_a_pin_the_room_cannot_seat_is_reported_not_infeasible():
    # Enrolment can be edited after publishing. The pin must still hold and the
    # mismatch surface as a violation, rather than the solve dying with a bare
    # INFEASIBLE the planner cannot diagnose.
    s = lecture("a-lec", "00540315", fixed_room="room3", expected_enrollment=200)
    result = solve(Problem(sessions=[s], fixed_events=[]), time_limit_s=5)
    assert result.solved
    assert result.schedule.placements["a-lec"].room_id == "room3"
    assert "capacity_exceeded" in _kinds(result.evaluation)


# ---- the evaluator polices the pin ------------------------------------ #

def test_evaluator_flags_a_pinned_session_in_the_wrong_room():
    s = lecture("a-lec", "00540315", fixed_room="room3")
    sched = Schedule()
    sched.place("a-lec", 0, 0, "hall6")           # not where it was pinned
    ev = evaluate(Problem(sessions=[s], fixed_events=[]), sched)
    assert "room_pin_broken" in _kinds(ev)
    assert not ev.is_feasible


def test_evaluator_accepts_a_pinned_session_in_its_room():
    s = lecture("a-lec", "00540315", fixed_room="room3")
    sched = Schedule()
    sched.place("a-lec", 0, 0, "room3")
    ev = evaluate(Problem(sessions=[s], fixed_events=[]), sched)
    assert "room_pin_broken" not in _kinds(ev)


def test_an_unpinned_session_may_sit_anywhere():
    s = lecture("a-lec", "00540315")
    sched = Schedule()
    sched.place("a-lec", 0, 0, "hall1")
    ev = evaluate(Problem(sessions=[s], fixed_events=[]), sched)
    assert "room_pin_broken" not in _kinds(ev)


# ---- surface ----------------------------------------------------------- #

def test_a_pin_to_an_unknown_room_degrades_to_a_reported_violation():
    # Bad data (a renamed or mistyped room) must not crash the solve or wedge it
    # as INFEASIBLE — the planner needs to see what is wrong.
    s = lecture("a-lec", "00540315", fixed_room="no_such_room")
    result = solve(Problem(sessions=[s], fixed_events=[]), time_limit_s=5)
    assert result.solved
    assert "room_pin_broken" in _kinds(result.evaluation)


def test_a_room_pin_marks_the_session_fixed():
    # Drives the editor's anchor marker: a room-pinned session is not free.
    assert lecture("a", "1", fixed_room="room3").is_fixed
    assert not lecture("a", "1").is_fixed
