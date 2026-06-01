"""Tests for the exporters — CSV golden content + PDF smoke test."""

from __future__ import annotations

from schedy.domain import (
    Cohort,
    Problem,
    Program,
    Schedule,
    Session,
    SessionType,
)
from schedy.exporters import CSV_HEADER, assignment_rows, to_csv, to_pdf

CHEME2 = Cohort(Program.CHEME, 2)


def _problem():
    lec = Session("c1-lec", "00540319", SessionType.LECTURE, 2,
                  cohorts=frozenset({CHEME2}), lecturer_ids=("dr_x",))
    ex = Session("c1-ex", "00540319", SessionType.EXERCISE, 1,
                 cohorts=frozenset({CHEME2}), group="SE011", ta_ids=("hedva",))
    problem = Problem(sessions=[lec, ex])
    sched = Schedule()
    sched.place("c1-lec", day=0, start_box=0, room_id="hall1")   # Sun 08:30-10:30
    sched.place("c1-ex", day=2, start_box=4, room_id="room3")    # Tue 12:30-13:30
    return problem, sched


def test_assignment_rows_sorted_and_complete():
    problem, sched = _problem()
    rows = assignment_rows(problem, sched)
    assert len(rows) == 2
    # Sorted by day then time -> Sunday lecture first.
    assert rows[0].day == "Sunday"
    assert rows[0].time == "08:30-10:30"
    assert rows[0].lecturers == "dr_x"
    assert rows[1].day == "Tuesday"
    assert rows[1].group == "SE011"
    assert rows[1].tas == "hedva"


def test_csv_export_is_deterministic_golden():
    problem, sched = _problem()
    out = to_csv(problem, sched)
    lines = out.splitlines()
    assert lines[0] == ",".join(CSV_HEADER)
    assert "00540319,c1-lec,lecture,,Sunday,08:30-10:30,Hall 1,ChemE Y2,dr_x," in lines[1]
    assert "00540319,c1-ex,exercise,SE011,Tuesday,12:30-13:30,Classroom 3,ChemE Y2,,hedva" in lines[2]


def test_pdf_export_smoke():
    problem, sched = _problem()
    pdf = to_pdf(problem, sched, title="Test")
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 500
