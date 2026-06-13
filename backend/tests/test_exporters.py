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
from schedy.exporters import (
    CSV_HEADER,
    assignment_rows,
    cohort_grid_cells,
    to_csv,
    to_pdf,
)

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


def test_cohort_grid_cells_groups_placements_by_cohort_with_spans():
    problem, sched = _problem()  # both sessions serve ChemE Y2
    grids = cohort_grid_cells(problem, sched)
    assert set(grids) == {"ChemE Y2"}
    spans = sorted((c.day, c.start_box, c.span) for c in grids["ChemE Y2"])
    assert spans == [(0, 0, 2), (2, 4, 1)]  # lecture spans 2 boxes, exercise 1
    lec = next(c for c in grids["ChemE Y2"] if c.start_box == 0)
    assert lec.course_number == "00540319" and lec.type == "lecture"
    assert lec.room == "Hall 1"


def test_pdf_cohort_layout_is_multipage_pdf():
    # Two cohorts -> two grid pages.
    a = Session("a-lec", "C1", SessionType.LECTURE, 2,
                cohorts=frozenset({Cohort(Program.CHEME, 2)}))
    b = Session("b-lec", "C2", SessionType.LECTURE, 2,
                cohorts=frozenset({Cohort(Program.BIOCHEME, 3)}))
    problem = Problem(sessions=[a, b])
    sched = Schedule()
    sched.place("a-lec", day=0, start_box=0, room_id="hall1")
    sched.place("b-lec", day=1, start_box=2, room_id="hall6")
    pdf = to_pdf(problem, sched, layout="cohort",
                 course_names={"C1": "תרמודינמיקה", "C2": "ביוכימיה"})
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 1000


def test_pdf_export_with_hebrew_names():
    problem, sched = _problem()
    # Hebrew course name exercises the bundled font + RTL reordering path.
    pdf = to_pdf(problem, sched, title="Test",
                 course_names={"00540319": "תרמודינמיקה א׳"})
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 500
