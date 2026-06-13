"""Tests for catalog expansion, including skeleton-driven exercise groups."""

from __future__ import annotations

from schedy.catalog import Course, expand, offered_exercise_groups, offered_placements
from schedy.domain import CourseRole, Program, SessionType


def _course(num="00540319", **kw):
    base = dict(number=num, programs=[Program.CHEME], year=2, role=CourseRole.CORE,
                lecture_boxes=2, num_exercise_groups=1)
    base.update(kw)
    return Course(**base)


def test_offered_exercise_groups_helper():
    rows = [
        {"course_number": "A", "event_type": "exercise", "group_code": "SE011"},
        {"course_number": "A", "event_type": "exercise", "group_code": "SE011"},  # dup
        {"course_number": "A", "event_type": "exercise", "group_code": "SE012"},
        {"course_number": "A", "event_type": "exercise", "group_code": None},      # no code
        {"course_number": "A", "event_type": "lecture", "group_code": "SE099"},    # not ex
        {"course_number": "B", "event_type": "exercise", "group_code": "G1"},
    ]
    assert offered_exercise_groups(rows) == {"A": ["SE011", "SE012"], "B": ["G1"]}


def test_skeleton_groups_override_declared_count():
    c = _course(num_exercise_groups=1)  # catalog declares 1
    offered = [
        {"course_number": "00540319", "event_type": "exercise", "group_code": "SE011"},
        {"course_number": "00540319", "event_type": "exercise", "group_code": "SE012"},
    ]
    problem = expand([c], offered_rows=offered)
    ex = [s for s in problem.sessions if s.type is SessionType.EXERCISE]
    assert sorted(s.group for s in ex) == ["SE011", "SE012"]  # 2 from skeleton, not 1
    assert {s.id for s in ex} == {"00540319-ex-SE011", "00540319-ex-SE012"}
    assert any(s.type is SessionType.LECTURE for s in problem.sessions)


def test_falls_back_to_declared_count_without_skeleton():
    problem = expand([_course(num_exercise_groups=3)])
    ex = [s for s in problem.sessions if s.type is SessionType.EXERCISE]
    assert len(ex) == 3


def test_group_code_with_spaces_is_id_safe():
    c = _course()
    offered = [{"course_number": "00540319", "event_type": "exercise",
                "group_code": "HEDVA 13"}]
    [ex] = [s for s in expand([c], offered_rows=offered).sessions
            if s.type is SessionType.EXERCISE]
    assert ex.group == "HEDVA 13"          # display keeps the real code
    assert " " not in ex.id                # id is safe


# --------------------------------------------------------------------------- #
# Skeleton day/time -> hard fixed placement (option a)
# --------------------------------------------------------------------------- #

def test_offered_placements_maps_day_and_box():
    rows = [
        # 10:30 on Monday(1) -> box 2 (08:30 + 2h)
        {"course_number": "A", "event_type": "exercise", "group_code": "SE011",
         "day": 1, "start_min": 10 * 60 + 30, "end_min": 11 * 60 + 30},
        # lecture 08:30 on Sunday(0) -> box 0
        {"course_number": "A", "event_type": "lecture", "group_code": None,
         "day": 0, "start_min": 8 * 60 + 30, "end_min": 10 * 60 + 30},
        # no time slot -> ignored
        {"course_number": "A", "event_type": "exercise", "group_code": "SE012",
         "day": None, "start_min": None, "end_min": None},
    ]
    pl = offered_placements(rows)
    assert pl[("A", "exercise", "SE011")] == (1, 2)
    assert pl[("A", "lecture", None)] == (0, 0)
    assert ("A", "exercise", "SE012") not in pl


def test_expand_fixes_exercise_and_lecture_from_skeleton():
    c = _course()  # 00540319, lecture_boxes=2
    offered = [
        {"course_number": "00540319", "event_type": "exercise",
         "group_code": "SE011", "day": 2, "start_min": 11 * 60 + 30,
         "end_min": 12 * 60 + 30},  # Tue(2) box 3
        {"course_number": "00540319", "event_type": "lecture", "group_code": None,
         "day": 0, "start_min": 8 * 60 + 30, "end_min": 10 * 60 + 30},  # Sun box 0
    ]
    problem = expand([c], offered_rows=offered)
    ex = problem.session("00540319-ex-SE011")
    lec = problem.session("00540319-lec")
    assert (ex.fixed_day, ex.fixed_box) == (2, 3)
    assert (lec.fixed_day, lec.fixed_box) == (0, 0)


def test_expand_skips_out_of_range_or_unaligned_times():
    c = _course()
    offered = [
        # before 08:30 -> cannot sit on the grid, leave free
        {"course_number": "00540319", "event_type": "exercise",
         "group_code": "SE011", "day": 1, "start_min": 7 * 60 + 30,
         "end_min": 8 * 60 + 30},
    ]
    ex = expand([c], offered_rows=offered).session("00540319-ex-SE011")
    assert ex.fixed_day is None and ex.fixed_box is None
