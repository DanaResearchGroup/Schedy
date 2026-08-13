"""The graduate non-overlap rule.

A graduate student combines a few courses from a small pool, so two graduate
courses at the same hour are untakeable — a hard rule, unlike undergraduate
electives, where an overlap is a reviewable compromise. Joint courses join the
rule against graduate courses but not against each other: they are largely
undergraduate-attended and behave like ordinary electives among themselves.

    grad  x grad   HARD
    grad  x joint  HARD
    joint x joint  allowed
"""

from __future__ import annotations

from schedy.domain import (
    Cohort,
    CourseLevel,
    CourseRole,
    FixedEvent,
    Problem,
    Program,
    Schedule,
    Session,
    SessionType,
)
from schedy.evaluator import evaluate
from schedy.solver import solve

CHEME2 = Cohort(Program.CHEME, 2)


def sess(sid, course, level, stype=SessionType.LECTURE, cohorts=frozenset(),
         role=CourseRole.ELECTIVE, **kw):
    return Session(id=sid, course_number=course, type=stype, length_boxes=2,
                   cohorts=cohorts, role=role, level=level, **kw)


def _at(*placements):
    """Build a schedule from (session_id, day, box, room) tuples."""
    sched = Schedule()
    for sid, day, box, room in placements:
        sched.place(sid, day, box, room)
    return sched


def _kinds(ev):
    return {v.kind for v in ev.violations}


def _hard(ev):
    return {v.kind for v in ev.violations if v.severity == "hard"}


# ---- the rule matrix --------------------------------------------------- #

def test_two_graduate_courses_may_not_overlap():
    a = sess("a", "00580310", CourseLevel.GRAD)
    b = sess("b", "00580415", CourseLevel.GRAD)
    ev = evaluate(Problem(sessions=[a, b], fixed_events=[]),
                  _at(("a", 0, 0, "room3"), ("b", 0, 0, "room4")))
    assert "grad_overlap" in _hard(ev)
    assert not ev.is_feasible


def test_a_graduate_course_may_not_overlap_a_joint_course():
    a = sess("a", "00580310", CourseLevel.GRAD)
    b = sess("b", "00560210", CourseLevel.JOINT)
    ev = evaluate(Problem(sessions=[a, b], fixed_events=[]),
                  _at(("a", 0, 0, "room3"), ("b", 0, 0, "room4")))
    assert "grad_overlap" in _hard(ev)


def test_two_joint_courses_may_overlap():
    # Largely undergraduate-attended; they behave like ordinary electives.
    a = sess("a", "00560210", CourseLevel.JOINT)
    b = sess("b", "00560330", CourseLevel.JOINT)
    ev = evaluate(Problem(sessions=[a, b], fixed_events=[]),
                  _at(("a", 0, 0, "room3"), ("b", 0, 0, "room4")))
    assert "grad_overlap" not in _kinds(ev)
    assert ev.is_feasible


def test_a_graduate_course_may_overlap_an_undergraduate_elective():
    # Different audiences — this stays the existing soft consideration.
    a = sess("a", "00580310", CourseLevel.GRAD)
    b = sess("b", "00540315", CourseLevel.UG, cohorts=frozenset({CHEME2}))
    ev = evaluate(Problem(sessions=[a, b], fixed_events=[]),
                  _at(("a", 0, 0, "room3"), ("b", 0, 0, "room4")))
    assert "grad_overlap" not in _kinds(ev)


# ---- the elif trap ----------------------------------------------------- #

def test_grad_overlap_is_hard_even_when_both_are_electives():
    """Regression: the elective branch must not swallow the graduate rule.

    `_check_pairs` tests pairs in one if/elif chain where elective-vs-elective
    (soft) is evaluated first. Graduate courses are nearly always electives, so
    a rule folded into that chain would silently degrade to a warning. This is
    the test that fails if the graduate check ever stops being independent.
    """
    a = sess("a", "00580310", CourseLevel.GRAD, role=CourseRole.ELECTIVE)
    b = sess("b", "00580415", CourseLevel.GRAD, role=CourseRole.ELECTIVE)
    ev = evaluate(Problem(sessions=[a, b], fixed_events=[]),
                  _at(("a", 0, 0, "room3"), ("b", 0, 0, "room4")))
    assert "grad_overlap" in _hard(ev), "graduate rule was swallowed by the elective branch"
    assert not ev.is_feasible


# ---- every session type ------------------------------------------------ #

def test_the_rule_covers_exercises_and_labs_not_just_lectures():
    lec = sess("a-lec", "00580310", CourseLevel.GRAD)
    ex = sess("b-ex", "00580415", CourseLevel.GRAD, stype=SessionType.EXERCISE)
    ev = evaluate(Problem(sessions=[lec, ex], fixed_events=[]),
                  _at(("a-lec", 0, 0, "room3"), ("b-ex", 0, 0, "room4")))
    assert "grad_overlap" in _hard(ev)

    lab = sess("c-lab", "00580520", CourseLevel.GRAD, stype=SessionType.LAB)
    ev = evaluate(Problem(sessions=[lec, lab], fixed_events=[]),
                  _at(("a-lec", 0, 0, "room3"), ("c-lab", 0, 0, "room4")))
    assert "grad_overlap" in _hard(ev)


def test_a_courses_own_lecture_and_exercise_may_not_overlap():
    # Graduate courses carry no cohort, so the cohort rule cannot catch this —
    # yet a student on the course attends both.
    lec = sess("a-lec", "00580310", CourseLevel.GRAD)
    ex = sess("a-ex", "00580310", CourseLevel.GRAD, stype=SessionType.EXERCISE)
    ev = evaluate(Problem(sessions=[lec, ex], fixed_events=[]),
                  _at(("a-lec", 0, 0, "room3"), ("a-ex", 0, 0, "room4")))
    assert "grad_overlap" in _hard(ev)


def test_two_exercise_groups_of_one_course_are_not_a_grad_overlap():
    # Students attend one group or the other. Their separation is already the
    # TA rule's business; reporting it twice would just be noise.
    g1 = sess("a-ex1", "00580310", CourseLevel.GRAD, stype=SessionType.EXERCISE)
    g2 = sess("a-ex2", "00580310", CourseLevel.GRAD, stype=SessionType.EXERCISE)
    ev = evaluate(Problem(sessions=[g1, g2], fixed_events=[]),
                  _at(("a-ex1", 0, 0, "room3"), ("a-ex2", 0, 0, "room4")))
    assert "grad_overlap" not in _kinds(ev)
    assert "ta_sessions_coincide" in _hard(ev)   # still caught, by its own rule


def test_cross_day_lab_alternatives_are_exempt_from_each_other():
    # Alternatives of ONE lab: a student takes it on one of the offered days, so
    # the two offerings overlapping is the arrangement, not a clash. The
    # exemption stops there — see
    # `test_a_multi_day_grad_lab_still_clashes_an_unrelated_grad_course`.
    a = sess("a-lab1", "00580310", CourseLevel.GRAD, stype=SessionType.LAB,
             lab_group="00580310")
    b = sess("a-lab2", "00580310", CourseLevel.GRAD, stype=SessionType.LAB,
             lab_group="00580310")
    ev = evaluate(Problem(sessions=[a, b], fixed_events=[]),
                  _at(("a-lab1", 0, 0, "room3"), ("a-lab2", 0, 0, "room4")))
    assert "grad_overlap" not in _kinds(ev)


# ---- another faculty's graduate courses -------------------------------- #

def test_an_external_graduate_course_blocks_ours():
    # It owns no cohort of ours, so only the level rule can reach it.
    ours = sess("a", "00580310", CourseLevel.GRAD)
    theirs = FixedEvent(id="ext-bio", label="Adv Protein Sci", day=0,
                        start_min=510, end_min=630, is_external_course=True,
                        level=CourseLevel.GRAD)
    ev = evaluate(Problem(sessions=[ours], fixed_events=[theirs]),
                  _at(("a", 0, 0, "room3")))
    assert "grad_overlap" in _hard(ev)


def test_an_external_undergraduate_course_does_not():
    ours = sess("a", "00580310", CourseLevel.GRAD)
    theirs = FixedEvent(id="ext-math", label="Calculus", day=0,
                        start_min=510, end_min=630, is_external_course=True,
                        level=CourseLevel.UG)
    ev = evaluate(Problem(sessions=[ours], fixed_events=[theirs]),
                  _at(("a", 0, 0, "room3")))
    assert "grad_overlap" not in _kinds(ev)


# ---- the solver honours it --------------------------------------------- #

def test_the_solver_separates_graduate_courses():
    a = sess("a", "00580310", CourseLevel.GRAD)
    b = sess("b", "00580415", CourseLevel.GRAD)
    c = sess("c", "00560210", CourseLevel.JOINT)
    result = solve(Problem(sessions=[a, b, c], fixed_events=[]), time_limit_s=10)
    assert result.solved
    assert "grad_overlap" not in _hard(result.evaluation)


def test_the_solver_places_ours_clear_of_a_foreign_graduate_course():
    ours = sess("a", "00580310", CourseLevel.GRAD)
    theirs = FixedEvent(id="ext-bio", label="Adv Protein Sci", day=0,
                        start_min=510, end_min=630, is_external_course=True,
                        level=CourseLevel.GRAD)
    result = solve(Problem(sessions=[ours], fixed_events=[theirs]), time_limit_s=10)
    assert result.solved
    assert "grad_overlap" not in _hard(result.evaluation)


# ---- holes found in adversarial review (spar round 1) ------------------ #

def test_a_multi_day_grad_lab_still_clashes_an_unrelated_grad_course():
    # Cross-day alternatives may overlap *each other* — a student picks one day.
    # They are not thereby exempt from the rule against other courses: D2 covers
    # every session, and a cohort-less graduate lab gets no protection from
    # `lab_cross_day_unsatisfiable`, which reasons entirely about cohorts.
    lab = sess("g-lab1", "00580001", CourseLevel.GRAD, SessionType.LAB,
               lab_group="00580001")
    lec = sess("g2-lec", "00580002", CourseLevel.GRAD)
    ev = evaluate(Problem(sessions=[lab, lec], fixed_events=[]),
                  _at(("g-lab1", 0, 0, "hall1"), ("g2-lec", 0, 0, "hall6")))
    assert "grad_overlap" in _hard(ev)


def test_two_alternatives_of_one_grad_lab_may_overlap_each_other():
    # That is what a cross-day alternative is; only one runs for a given student.
    a = sess("g-lab1", "00580001", CourseLevel.GRAD, SessionType.LAB,
             lab_group="00580001")
    b = sess("g-lab2", "00580001", CourseLevel.GRAD, SessionType.LAB,
             lab_group="00580001")
    ev = evaluate(Problem(sessions=[a, b], fixed_events=[]),
                  _at(("g-lab1", 0, 0, "hall1"), ("g-lab2", 0, 0, "hall6")))
    assert "grad_overlap" not in _hard(ev)


# ---- external walls carry a level, and it has to mean the same thing ---- #

def _ext(fid, day, start_min, end_min, level):
    return FixedEvent(id=fid, label=fid, day=day, start_min=start_min,
                      end_min=end_min, cohorts=frozenset(), level=level)


def test_the_model_lets_two_external_joint_courses_overlap():
    # D1: joint x joint is allowed. Putting external joint walls into the same
    # no-overlap set as the graduate ones forbids it and can make the model
    # infeasible over a rule that does not exist.
    a = _ext("ext-j1", 0, 510, 630, CourseLevel.JOINT)
    b = _ext("ext-j2", 0, 510, 630, CourseLevel.JOINT)
    one = sess("u-lec", "00540001", CourseLevel.UG, cohorts=frozenset({CHEME2}),
               role=CourseRole.CORE)
    result = solve(Problem(sessions=[one], fixed_events=[a, b]), time_limit_s=5)
    assert result.solved


def test_the_model_keeps_a_joint_session_off_an_external_grad_course():
    # The evaluator calls this hard, so the model must not be free to choose it.
    wall = _ext("ext-g", 0, 510, 630, CourseLevel.GRAD)
    joint = sess("j-lec", "00560001", CourseLevel.JOINT)
    result = solve(Problem(sessions=[joint], fixed_events=[wall]), time_limit_s=5)
    assert result.solved
    p = result.schedule.placements["j-lec"]
    assert not (p.day == 0 and p.start_box < 2)   # 08:30-10:30 is taken
