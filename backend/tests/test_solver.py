"""Tests for the CP-SAT Model Builder + Solver Runner.

Small hand-built scenarios with known-correct outcomes. The Constraint Evaluator
is trusted as the arbiter, so most assertions check that the solved schedule is
hard-feasible and that obvious soft conflicts are avoided when avoidable.
"""

from __future__ import annotations

import pytest

from schedy.domain import (
    Cohort,
    CourseRole,
    FixedEvent,
    Problem,
    Program,
    Schedule,
    Session,
    SessionType,
    standing_blackouts,
)
from schedy.solver import solve

CHEME2 = Cohort(Program.CHEME, 2)
BIO2 = Cohort(Program.BIOCHEME, 2)


def lecture(sid, course, cohorts=frozenset({CHEME2}), length=2,
            role=CourseRole.CORE, **kw):
    return Session(id=sid, course_number=course, type=SessionType.LECTURE,
                   length_boxes=length, cohorts=cohorts, role=role, **kw)


def test_solver_separates_cohort_clashing_lectures():
    a = lecture("a", "C1")
    b = lecture("b", "C2")  # both serve CHEME2 -> must not overlap
    problem = Problem(sessions=[a, b])
    result = solve(problem, time_limit_s=5)
    assert result.solved
    assert result.evaluation.is_feasible
    # The two intervals must not overlap.
    pa = result.schedule.placements["a"]
    pb = result.schedule.placements["b"]
    ia = a.interval(pa)
    ib = b.interval(pb)
    assert not ia.overlaps(ib)


def test_solver_respects_room_capacity():
    big = lecture("big", "C1", expected_enrollment=200)
    problem = Problem(sessions=[big])
    result = solve(problem, time_limit_s=5)
    assert result.solved
    room = result.schedule.placements["big"].room_id
    assert room == "hall1"  # only room that seats 200


def test_solver_routes_computer_course_to_farm():
    comp = lecture("comp", "C1", needs_computer_farm=True, expected_enrollment=20)
    problem = Problem(sessions=[comp])
    result = solve(problem, time_limit_s=5)
    assert result.solved
    assert result.schedule.placements["comp"].room_id == "room2"


def test_solver_avoids_blackout_windows():
    sessions = [lecture(f"s{i}", f"C{i}", length=1) for i in range(6)]
    problem = Problem(sessions=sessions, fixed_events=standing_blackouts())
    result = solve(problem, time_limit_s=5)
    assert result.solved
    assert result.evaluation.is_feasible
    # No session lands in a blackout window.
    assert not any(v.kind == "blackout_violation"
                   for v in result.evaluation.violations)


def test_solver_minimises_elective_core_overlap_when_avoidable():
    # An elective and a core for the same cohort, both 2 boxes, plenty of room in
    # the week -> the solver should place them without overlap (zero penalty).
    core = lecture("core", "C1", role=CourseRole.CORE)
    elec = lecture("elec", "E1", role=CourseRole.ELECTIVE)
    problem = Problem(sessions=[core, elec])
    result = solve(problem, time_limit_s=5)
    assert result.solved
    assert result.objective == 0
    assert result.evaluation.soft_penalty == 0


def test_solver_respects_lecturer_availability():
    a = lecture("a", "C1", length=1, lecturer_ids=("dr_x",))
    # dr_x unavailable every box on every day except Thursday box 0.
    unavail = {(d, b) for d in range(5) for b in range(10)} - {(4, 0)}
    problem = Problem(sessions=[a], availability={"dr_x": unavail})
    result = solve(problem, time_limit_s=5)
    assert result.solved
    p = result.schedule.placements["a"]
    assert (p.day, p.start_box) == (4, 0)
