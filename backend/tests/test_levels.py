"""Course level — undergraduate, joint, or graduate.

Level is who may take a course, distinct from `role` (core/elective/…), which is
what a course is. The department's numbering encodes it, so the number supplies a
suggestion; the planner may always override, because plenty of courses from other
faculties are graduate-level without following our convention.
"""

from __future__ import annotations

from schedy.catalog import Course, expand, suggest_level
from schedy.catalog_io import from_csv, to_csv
from schedy.domain import CourseLevel, CourseRole, Program
from schedy.store import course_from_dict, course_to_dict


def _course(number="00540315", **kw):
    base = dict(number=number, programs=[Program.CHEME], year=2, lecture_boxes=2)
    base.update(kw)
    return Course(**base)


# ---- suggestion from the number --------------------------------------- #

def test_our_prefixes_map_to_levels():
    assert suggest_level("00540315") is CourseLevel.UG
    assert suggest_level("00560210") is CourseLevel.JOINT
    assert suggest_level("00580310") is CourseLevel.GRAD


def test_another_faculty_defaults_to_undergraduate():
    # Most foreign courses our students take are undergraduate; the graduate
    # ones are the exception the planner marks by hand.
    assert suggest_level("01040031") is CourseLevel.UG
    assert suggest_level("01360350") is CourseLevel.UG


def test_suggestion_tolerates_junk():
    assert suggest_level("") is CourseLevel.UG
    assert suggest_level("abc") is CourseLevel.UG
    assert suggest_level(None) is CourseLevel.UG


def test_suggestion_ignores_surrounding_whitespace():
    assert suggest_level("  00580310 ") is CourseLevel.GRAD


# ---- effective level on a course -------------------------------------- #

def test_level_is_derived_when_unset():
    assert _course("00580310").level is None
    assert _course("00580310").effective_level is CourseLevel.GRAD


def test_a_stored_level_beats_the_number():
    # A biology graduate course whose number tells us nothing.
    c = _course("01360428", level=CourseLevel.GRAD)
    assert c.effective_level is CourseLevel.GRAD
    # …and the reverse: our own 0058 number overridden down to undergraduate.
    assert _course("00580310", level=CourseLevel.UG).effective_level is CourseLevel.UG


def test_grad_and_joint_predicates():
    assert _course("00580310").is_grad_level
    assert _course("00560210").is_grad_level      # joint counts for the clash rule
    assert not _course("00540315").is_grad_level


# ---- propagation ------------------------------------------------------- #

def test_sessions_inherit_their_courses_level():
    problem = expand([_course("00580310", num_exercise_groups=1, lab_boxes=2)])
    assert problem.sessions
    assert all(s.level is CourseLevel.GRAD for s in problem.sessions)


def test_an_external_courses_wall_carries_its_level():
    ext = _course("01360428", level=CourseLevel.GRAD, is_external=True,
                  ext_day=1, ext_start_min=510, ext_end_min=630)
    problem = expand([ext])
    walls = [fe for fe in problem.fixed_events if fe.is_external_course]
    assert len(walls) == 1
    assert walls[0].level is CourseLevel.GRAD


# ---- persistence ------------------------------------------------------- #

def test_level_survives_the_store_roundtrip():
    c = _course("01360428", level=CourseLevel.GRAD)
    back = course_from_dict(course_to_dict(c))
    assert back.level is CourseLevel.GRAD

    unset = course_from_dict(course_to_dict(_course("00580310")))
    assert unset.level is None
    assert unset.effective_level is CourseLevel.GRAD


def test_level_survives_a_catalog_file_roundtrip():
    courses = [_course("01360428", level=CourseLevel.GRAD), _course("00540315")]
    back = {c.number: c for c in from_csv(to_csv(courses))}
    assert back["01360428"].level is CourseLevel.GRAD
    assert back["00540315"].level is None       # unset stays unset, not stamped


def test_a_catalog_file_without_the_column_derives_from_the_number():
    legacy = ("number,name_en,programs,year,role,lecture_boxes\n"
              "00580310,Adv Thermo,ChemE,2,elective,2\n")
    c = from_csv(legacy)[0]
    assert c.level is None
    assert c.effective_level is CourseLevel.GRAD


def test_role_and_level_are_independent():
    # A graduate course is usually an elective; that must not conflate them.
    c = _course("00580310", role=CourseRole.ELECTIVE)
    assert c.role is CourseRole.ELECTIVE
    assert c.effective_level is CourseLevel.GRAD
