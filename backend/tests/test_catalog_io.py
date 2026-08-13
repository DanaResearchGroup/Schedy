"""Unit tests for catalog CSV import/export (pure, file-free)."""

from __future__ import annotations

import pytest

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


def test_offered_flag_and_reason_survive_a_roundtrip():
    courses = [
        Course(number="00540777", programs=[Program.CHEME], year=3,
               role=CourseRole.ELECTIVE, lecture_boxes=2,
               offered=False, skip_reason="Prof. X sabbatical 2026"),
        Course(number="00540315", programs=[Program.CHEME], year=2, lecture_boxes=2),
    ]
    back = {c.number: c for c in from_csv(to_csv(courses))}
    assert back["00540777"].offered is False
    assert back["00540777"].skip_reason == "Prof. X sabbatical 2026"
    assert back["00540315"].offered is True


def test_catalog_file_without_offered_column_stays_offered():
    # Files exported before the column existed must not silently empty the
    # semester — a missing or blank cell means offered.
    legacy = (
        "number,name_en,programs,year,role,lecture_boxes\n"
        "00540315,Thermo,ChemE,2,core,2\n"
    )
    back = from_csv(legacy)
    assert len(back) == 1 and back[0].offered is True

    blank = "number,lecture_boxes,offered\n00540315,2,\n"
    assert from_csv(blank)[0].offered is True


def test_credit_points_survive_a_roundtrip():
    courses = [
        Course(number="00540315", programs=[Program.CHEME], year=2,
               lecture_boxes=2, credit=3.5),
        Course(number="00540777", programs=[Program.CHEME], year=3, lecture_boxes=2),
    ]
    back = {c.number: c for c in from_csv(to_csv(courses))}
    assert back["00540315"].credit == 3.5
    assert back["00540777"].credit is None  # unset stays unset, never coerced to 0


def test_catalog_file_without_credit_column_leaves_it_unset():
    # Files exported before the column existed have no cell here; a missing or
    # blank credit must read as unset (None), never 0.0.
    legacy = (
        "number,name_en,programs,year,role,lecture_boxes\n"
        "00540315,Thermo,ChemE,2,core,2\n"
    )
    assert from_csv(legacy)[0].credit is None
    blank = "number,lecture_boxes,credit\n00540315,2,\n"
    assert from_csv(blank)[0].credit is None


def test_credit_rejects_non_finite_and_negative():
    # A crafted file could slip nan/inf past float() (they serialize as invalid
    # JSON downstream) or a negative credit; both must fail the import loudly.
    for bad in ("nan", "inf", "-inf", "-1"):
        with pytest.raises(ValueError):
            from_csv(f"number,lecture_boxes,credit\n00540315,2,{bad}\n")


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


def test_cadence_survives_a_csv_round_trip():
    from schedy.catalog import Cadence
    c = Course(number="00580001", programs=[], year=0, cadence=Cadence.BIENNIAL)
    assert from_csv(to_csv([c]))[0].cadence is Cadence.BIENNIAL


def test_a_file_written_before_cadence_existed_reads_as_annual():
    from schedy.catalog import Cadence
    # No column at all: the course ran every year, which is both the common case
    # and the safe one — it reserves a slot rather than losing one.
    assert from_csv("number\n00580001\n")[0].cadence is Cadence.ANNUAL


def test_a_provisional_course_exports_as_provisional():
    c = Course(number="00580001", programs=[], year=0, provisional=True)
    assert from_csv(to_csv([c]))[0].provisional is True


def test_a_file_without_the_provisional_column_reads_as_confirmed():
    # Absent means settled: a hand-written catalog is not a set of guesses.
    assert from_csv("number\n00580001\n")[0].provisional is False
