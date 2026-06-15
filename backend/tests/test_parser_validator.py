"""Tests for the Skeleton Parser and Validator."""

from __future__ import annotations

import os

import pytest

from schedy.domain import SessionType
from schedy.parser import parse_rows, parse_skeleton, _extract_group_code
from schedy.validator import ChecklistItem, find_missing

# A hand-built skeleton mirroring the real column layout (Hebrew headers).
HEADER = [
    "מקצוע", "תיאור מקצוע עברית", "תיאור חבילת רישום", "סוג אירוע D",
    "ראשון", "שני", "שלישי", "רביעי", "חמישי",
    "חדר", "פקולטה", "שפת הוראת אירוע", "אדם מוקצה", "תיאור מקצוע אנגלית",
]


def row(course, package, etype, *, sun="", mon="", tue="", wed="", thu="",
        room="", faculty="הנדסה כימית", lang="HE", person="", en=""):
    return [course, "קורס", package, etype, sun, mon, tue, wed, thu,
            room, faculty, lang, person, en]


def test_parses_event_type_day_and_time():
    rows = [row("00540319", "SE011 תרמודינמיקה", "הרצאה", sun="09:30-12:30",
                room="Hall 1", en="Thermodynamics")]
    [s] = parse_rows(HEADER, rows)
    assert s.course_number == "00540319"
    assert s.event_type is SessionType.LECTURE
    assert s.day == 0                      # Sunday
    assert (s.start_min, s.end_min) == (9 * 60 + 30, 12 * 60 + 30)
    assert s.group_code == "SE011"
    assert s.room == "Hall 1"
    assert s.name_en == "Thermodynamics"


def test_exercise_type_and_hebrew_group_code():
    rows = [row("00540319", "קב025 תרמודינמיקה", "תרגול", tue="16:30-18:30")]
    [s] = parse_rows(HEADER, rows)
    assert s.event_type is SessionType.EXERCISE
    assert s.day == 2
    assert s.group_code == "קב025"


def test_extract_group_code_rejects_non_code_tokens():
    assert _extract_group_code("SE011 something") == "SE011"
    assert _extract_group_code("קבוצה עבור סינים בלבד") is None  # leading word, no digit
    assert _extract_group_code("") is None


def test_filtering_by_relevant_course_numbers():
    rows = [
        row("00540319", "SE011", "הרצאה", sun="09:30-10:30"),
        row("00940411", "SE011", "הרצאה", sun="09:30-10:30"),  # not ours
    ]
    out = parse_rows(HEADER, rows, relevant_course_numbers={"00540319"})
    assert [s.course_number for s in out] == ["00540319"]


def test_row_without_course_number_is_skipped():
    rows = [row("", "x", "הרצאה")]
    assert parse_rows(HEADER, rows) == []


def test_missing_course_column_raises():
    with pytest.raises(ValueError):
        parse_rows(["foo", "bar"], [["a", "b"]])


def test_visual_timetable_grid_gives_a_clear_error():
    # A hand-made draft timetable: day-name headers across the top, time ranges
    # down column A, free-text course names in the cells. Not a registration
    # export -> the error must say so, not just "missing column".
    header = [None, "ראשון", None, "שני", "שלישי", "רביעי", "חמישי"]
    rows = [
        ["8:30-9:30", "אלגברה ה.2", "", "חדו\"א 1", "פיזיקה 1 ת 21", "", ""],
        ["9:30-10:30", "", "", "", "ה.1", "", ""],
    ]
    with pytest.raises(ValueError, match="timetable grid"):
        parse_rows(header, rows)


# --------------------------------------------------------------------------- #
# Validator
# --------------------------------------------------------------------------- #

def test_validator_flags_missing_lecture():
    offered = parse_rows(HEADER, [row("00540319", "SE011", "תרגול", sun="9:30-10:30")])
    checklist = [
        ChecklistItem("00540319", SessionType.LECTURE, label="Thermo lecture"),
    ]
    missing = find_missing(checklist, offered)
    assert len(missing) == 1
    assert missing[0].describe() == "Thermo lecture"


def test_validator_passes_when_present():
    offered = parse_rows(HEADER, [
        row("00540319", "SE011", "הרצאה", sun="9:30-10:30"),
        row("00540319", "HEDVA 13", "תרגול", mon="14:30-16:30"),
    ])
    checklist = [
        ChecklistItem("00540319", SessionType.LECTURE),
        ChecklistItem("00540319", SessionType.EXERCISE, group_code="HEDVA"),
    ]
    assert find_missing(checklist, offered) == []


def test_validator_matches_dedicated_group_by_substring():
    offered = parse_rows(HEADER, [row("00540319", "HEDVA 13 תרמו", "תרגול", mon="14:30-15:30")])
    present = ChecklistItem("00540319", SessionType.EXERCISE, group_code="HEDVA 13")
    absent = ChecklistItem("00540319", SessionType.EXERCISE, group_code="HEDVA 99")
    assert find_missing([present], offered) == []
    assert find_missing([absent], offered) == [absent]


# --------------------------------------------------------------------------- #
# Smoke test against the real Technion skeleton
# --------------------------------------------------------------------------- #

REAL_XLSX = os.path.join(os.path.dirname(__file__), "..", "..", "raw", "30.4.26.XLSX")


@pytest.mark.skipif(not os.path.exists(REAL_XLSX), reason="real skeleton not present")
def test_real_skeleton_parses_known_course():
    offered = parse_skeleton(REAL_XLSX, relevant_course_numbers={"00940411"})
    assert offered, "expected at least one session for course 00940411"
    assert all(s.course_number == "00940411" for s in offered)
    # That course has both a lecture and exercises in the sample file.
    types = {s.event_type for s in offered}
    assert SessionType.LECTURE in types
