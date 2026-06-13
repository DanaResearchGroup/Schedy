"""Tests for the Constraint Evaluator — one focused scenario per rule."""

from __future__ import annotations

import pytest

from schedy.domain import (
    Cohort,
    CourseRole,
    FixedEvent,
    Problem,
    Program,
    Room,
    Schedule,
    Session,
    SessionType,
    standing_blackouts,
)
from schedy.evaluator import evaluate

CHEME2 = Cohort(Program.CHEME, 2)
BIO2 = Cohort(Program.BIOCHEME, 2)


def kinds(result):
    return sorted(v.kind for v in result.violations)


def lecture(sid, course="C1", cohorts=frozenset({CHEME2}), length=2,
            role=CourseRole.CORE, **kw):
    return Session(id=sid, course_number=course, type=SessionType.LECTURE,
                   length_boxes=length, cohorts=cohorts, role=role, **kw)


def exercise(sid, course="C1", cohorts=frozenset({CHEME2}), group="SE011", **kw):
    return Session(id=sid, course_number=course, type=SessionType.EXERCISE,
                   length_boxes=1, cohorts=cohorts, group=group, **kw)


# --------------------------------------------------------------------------- #
# Clean baseline
# --------------------------------------------------------------------------- #

def test_fixed_placement_flagged_when_moved_and_clean_when_kept():
    fx = lecture("fx", fixed_day=1, fixed_box=2)
    # Placed exactly at its fixed slot -> no fixed_placement violation.
    kept = Schedule()
    kept.place("fx", day=1, start_box=2, room_id="hall1")
    assert "fixed_placement" not in kinds(evaluate(Problem(sessions=[fx]), kept))
    # Moved away (e.g. dragged in the editor) -> hard fixed_placement violation.
    moved = Schedule()
    moved.place("fx", day=0, start_box=0, room_id="hall1")
    res = evaluate(Problem(sessions=[fx]), moved)
    assert "fixed_placement" in kinds(res)
    assert all(v.severity == "hard"
               for v in res.violations if v.kind == "fixed_placement")


def test_no_violations_for_disjoint_schedule():
    a = lecture("a")
    b = lecture("b", course="C2")
    problem = Problem(sessions=[a, b])
    sched = Schedule()
    sched.place("a", day=0, start_box=0, room_id="hall1")
    sched.place("b", day=0, start_box=3, room_id="hall1")  # later, same room, no overlap
    result = evaluate(problem, sched)
    assert result.is_feasible
    assert result.violations == []


# --------------------------------------------------------------------------- #
# Hard rules
# --------------------------------------------------------------------------- #

def test_room_double_booking_is_hard():
    a, b = lecture("a"), lecture("b", course="C2", cohorts=frozenset({BIO2}))
    problem = Problem(sessions=[a, b])
    sched = Schedule()
    sched.place("a", 0, 0, "hall1")
    sched.place("b", 0, 1, "hall1")  # overlaps in hall1
    result = evaluate(problem, sched)
    assert "room_double_booked" in kinds(result)
    assert not result.is_feasible


def test_cohort_double_booking_is_hard():
    a, b = lecture("a"), lecture("b", course="C2")  # both serve CHEME2
    problem = Problem(sessions=[a, b])
    sched = Schedule()
    sched.place("a", 0, 0, "hall1")
    sched.place("b", 0, 0, "hall6")  # different rooms, same cohort+time
    assert "cohort_double_booked" in kinds(evaluate(problem, sched))


def test_chemE_and_biochemE_only_courses_may_overlap():
    a = lecture("a", cohorts=frozenset({CHEME2}))
    b = lecture("b", course="C2", cohorts=frozenset({BIO2}))
    problem = Problem(sessions=[a, b])
    sched = Schedule()
    sched.place("a", 0, 0, "hall1")
    sched.place("b", 0, 0, "hall6")  # different audience, different room
    assert evaluate(problem, sched).is_feasible


def test_person_double_booking_is_hard():
    a = lecture("a", lecturer_ids=("dr_x",))
    b = lecture("b", course="C2", cohorts=frozenset({BIO2}), lecturer_ids=("dr_x",))
    problem = Problem(sessions=[a, b])
    sched = Schedule()
    sched.place("a", 0, 0, "hall1")
    sched.place("b", 0, 0, "hall6")
    assert "person_double_booked" in kinds(evaluate(problem, sched))


def test_same_course_ta_sessions_cannot_coincide():
    a = exercise("a", group="SE011")
    b = exercise("b", group="SE012")
    problem = Problem(sessions=[a, b])
    sched = Schedule()
    sched.place("a", 0, 0, "room3")
    sched.place("b", 0, 0, "room4")
    assert "ta_sessions_coincide" in kinds(evaluate(problem, sched))


def test_blackout_window_is_hard():
    # Monday seminar 13:30-14:30 == day 1, box 5.
    a = lecture("a", length=1)
    problem = Problem(sessions=[a], fixed_events=standing_blackouts())
    sched = Schedule()
    sched.place("a", day=1, start_box=5, room_id="hall1")
    assert "blackout_violation" in kinds(evaluate(problem, sched))


def test_capacity_exceeded_is_hard():
    a = lecture("a", expected_enrollment=100)
    problem = Problem(sessions=[a])
    sched = Schedule()
    sched.place("a", 0, 0, "room3")  # cap 50
    assert "capacity_exceeded" in kinds(evaluate(problem, sched))


def test_computer_farm_requirement_is_hard():
    a = lecture("a", needs_computer_farm=True)
    problem = Problem(sessions=[a])
    sched = Schedule()
    sched.place("a", 0, 0, "hall1")  # not the farm
    assert "computer_farm_required" in kinds(evaluate(problem, sched))


def test_person_unavailable_is_hard():
    a = lecture("a", lecturer_ids=("dr_x",))
    problem = Problem(sessions=[a], availability={"dr_x": {(0, 0)}})
    sched = Schedule()
    sched.place("a", day=0, start_box=0, room_id="hall1")
    assert "person_unavailable" in kinds(evaluate(problem, sched))


def test_external_core_clash_is_hard():
    a = lecture("a")  # CHEME2 core
    ext = FixedEvent(
        id="ext1", label="External Math", day=0, start_min=8 * 60 + 30,
        end_min=10 * 60 + 30, cohorts=frozenset({CHEME2}),
        is_external_course=True,
    )
    problem = Problem(sessions=[a], fixed_events=[ext])
    sched = Schedule()
    sched.place("a", 0, 0, "hall1")
    assert "cohort_double_booked" in kinds(evaluate(problem, sched))


# --------------------------------------------------------------------------- #
# Lab cross-day satisfiability
# --------------------------------------------------------------------------- #

def test_lab_cross_day_satisfied_via_alternate_day():
    # Thermo lab offered Sunday and Wednesday; CHEME core on Wednesday, BIO core on
    # Sunday. ChemE takes the lab Sunday, BioChemE takes it Wednesday — feasible.
    lab_sun = Session("lab-sun", "LAB", SessionType.LAB, 2,
                      cohorts=frozenset({CHEME2, BIO2}), lab_group="thermo")
    lab_wed = Session("lab-wed", "LAB", SessionType.LAB, 2,
                      cohorts=frozenset({CHEME2, BIO2}), lab_group="thermo")
    cheme_core = lecture("cheme_core", course="CC", cohorts=frozenset({CHEME2}))
    bio_core = lecture("bio_core", course="BC", cohorts=frozenset({BIO2}))
    problem = Problem(sessions=[lab_sun, lab_wed, cheme_core, bio_core])
    sched = Schedule()
    sched.place("lab-sun", day=0, start_box=0, room_id="room3")
    sched.place("lab-wed", day=3, start_box=0, room_id="room3")
    sched.place("cheme_core", day=3, start_box=0, room_id="hall1")  # blocks ChemE Wed
    sched.place("bio_core", day=0, start_box=0, room_id="hall6")    # blocks Bio Sun
    result = evaluate(problem, sched)
    assert "lab_cross_day_unsatisfiable" not in kinds(result)


def test_cross_day_lab_overlapping_cohort_core_is_not_double_booked():
    # A cross-day lab alternative may overlap the cohort's own course on its
    # "off" day (students attend the other day) — that's governed by the
    # lab_cross_day rule, not a cohort double-booking.
    lab1 = Session("L-1", "TH", SessionType.LAB, 2,
                   cohorts=frozenset({CHEME2}), lab_group="thermo")
    lab2 = Session("L-2", "TH", SessionType.LAB, 2,
                   cohorts=frozenset({CHEME2}), lab_group="thermo")
    core = lecture("core", course="CC", cohorts=frozenset({CHEME2}))
    problem = Problem(sessions=[lab1, lab2, core])
    sched = Schedule()
    sched.place("L-1", day=0, start_box=0, room_id="room3")    # overlaps core
    sched.place("L-2", day=3, start_box=0, room_id="room3")    # clear day
    sched.place("core", day=0, start_box=0, room_id="hall1")
    result = evaluate(problem, sched)
    assert "cohort_double_booked" not in kinds(result)
    assert "lab_cross_day_unsatisfiable" not in kinds(result)  # Wed is clear


def test_lab_cross_day_unsatisfiable_when_all_days_blocked():
    lab_sun = Session("lab-sun", "LAB", SessionType.LAB, 2,
                      cohorts=frozenset({CHEME2}), lab_group="thermo")
    lab_wed = Session("lab-wed", "LAB", SessionType.LAB, 2,
                      cohorts=frozenset({CHEME2}), lab_group="thermo")
    core_sun = lecture("core_sun", course="CC", cohorts=frozenset({CHEME2}))
    core_wed = lecture("core_wed", course="CD", cohorts=frozenset({CHEME2}))
    problem = Problem(sessions=[lab_sun, lab_wed, core_sun, core_wed])
    sched = Schedule()
    sched.place("lab-sun", day=0, start_box=0, room_id="room3")
    sched.place("lab-wed", day=3, start_box=0, room_id="room4")
    sched.place("core_sun", day=0, start_box=0, room_id="hall1")  # blocks Sunday
    sched.place("core_wed", day=3, start_box=0, room_id="hall6")  # blocks Wednesday
    assert "lab_cross_day_unsatisfiable" in kinds(evaluate(problem, sched))


# --------------------------------------------------------------------------- #
# Soft rules + weights
# --------------------------------------------------------------------------- #

def test_elective_vs_core_is_soft_weighted():
    elec = lecture("elec", course="E1", role=CourseRole.ELECTIVE)
    core = lecture("core", course="C1", role=CourseRole.CORE)  # shares CHEME2
    problem = Problem(sessions=[elec, core])
    sched = Schedule()
    sched.place("elec", 0, 0, "room3")
    sched.place("core", 0, 0, "hall1")
    result = evaluate(problem, sched)
    assert result.is_feasible  # soft only
    assert "elective_vs_core" in kinds(result)
    assert result.soft_penalty == problem.soft_weights.elective_vs_core


def test_two_electives_overlapping_is_soft():
    e1 = lecture("e1", course="E1", role=CourseRole.ELECTIVE)
    e2 = lecture("e2", course="E2", role=CourseRole.ELECTIVE,
                 cohorts=frozenset({BIO2}))
    problem = Problem(sessions=[e1, e2])
    sched = Schedule()
    sched.place("e1", 0, 0, "room3")
    sched.place("e2", 0, 0, "room4")
    result = evaluate(problem, sched)
    assert kinds(result) == ["elective_vs_elective"]
    assert result.soft_penalty == problem.soft_weights.elective_vs_elective


def test_lecture_before_exercise_is_soft():
    lec = lecture("lec", length=1)         # placed later
    ex = exercise("ex")                    # placed earlier -> inversion
    problem = Problem(sessions=[lec, ex])
    sched = Schedule()
    sched.place("ex", day=0, start_box=0, room_id="room3")
    sched.place("lec", day=2, start_box=0, room_id="hall1")
    result = evaluate(problem, sched)
    assert "lecture_before_exercise" in kinds(result)
    assert result.is_feasible


def test_zoom_in_middle_of_day_is_soft():
    a = lecture("a", length=1, is_remote=True)
    problem = Problem(sessions=[a])
    sched = Schedule()
    sched.place("a", day=0, start_box=4, room_id="hall1")  # midday
    assert "zoom_timing" in kinds(evaluate(problem, sched))
    # Morning placement is clean.
    sched.place("a", day=0, start_box=0, room_id="hall1")
    assert evaluate(problem, sched).is_feasible
