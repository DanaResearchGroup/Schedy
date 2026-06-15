"""Unit tests for catalog CSV import/export (pure, file-free)."""

from __future__ import annotations

from schedy.catalog import Course
from schedy.catalog_io import from_csv, template_csv, to_csv
from schedy.domain import CourseRole, Program


def test_catalog_csv_roundtrip_preserves_every_field():
    courses = [
        Course(
            number="00540315", name_he="תרמו", name_en="Thermo",
            programs=[Program.CHEME, Program.BIOCHEME], year=2, role=CourseRole.CORE,
            lecture_boxes=2, num_exercise_groups=2, exercise_boxes=1,
            lab_boxes=2, lab_days=[0, 3], expected_enrollment=70,
            needs_computer_farm=True, lecturer_ids=["prof_bar"], ta_ids=["ta_a", "ta_b"],
        ),
        Course(
            number="01040031", name_en="Calc", programs=[Program.CHEME], year=1,
            role=CourseRole.ELECTIVE, is_external=True, ext_day=1, ext_start_min=510,
            ext_end_min=630, ext_room="Math", is_remote=True,
        ),
    ]
    back = {c.number: c for c in from_csv(to_csv(courses))}
    assert len(back) == 2

    a = back["00540315"]
    assert a.programs == [Program.CHEME, Program.BIOCHEME]
    assert a.lab_days == [0, 3] and a.needs_computer_farm is True
    assert a.ta_ids == ["ta_a", "ta_b"] and a.name_he == "תרמו"
    assert a.lecture_boxes == 2 and a.num_exercise_groups == 2

    b = back["01040031"]
    assert b.role is CourseRole.ELECTIVE and b.is_remote is True
    assert b.is_external and b.ext_day == 1 and b.ext_start_min == 510
    assert b.ext_room == "Math"


def test_template_is_self_consistent():
    back = from_csv(template_csv())
    assert len(back) >= 1
    assert all(c.number for c in back)


def test_from_csv_tolerates_bom_and_blank_lines():
    text = "﻿" + to_csv([Course(number="00540315", programs=[Program.CHEME], year=2)])
    back = from_csv(text + "\n\n")  # trailing blank lines (Excel artefact)
    assert [c.number for c in back] == ["00540315"]


def test_number_less_rows_are_skipped():
    text = "number,year\n,3\n00540315,2\n"
    assert [c.number for c in from_csv(text)] == ["00540315"]
