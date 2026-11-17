"""Tests for the exporters — CSV golden content + PDF smoke test."""

from __future__ import annotations

import re

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
    person_pages,
    room_pages,
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


# ---- the graduate page (PRD D11) --------------------------------------- #

def _grad_problem():
    """A graduate course (no cohort), a joint one, and an undergraduate one."""
    from schedy.domain import CourseLevel
    grad = Session("g-lec", "00580001", SessionType.LECTURE, 2,
                   cohorts=frozenset(), level=CourseLevel.GRAD)
    joint = Session("j-lec", "00560001", SessionType.LECTURE, 2,
                    cohorts=frozenset({CHEME2}), level=CourseLevel.JOINT)
    ug = Session("u-lec", "00540001", SessionType.LECTURE, 2,
                 cohorts=frozenset({CHEME2}), level=CourseLevel.UG)
    problem = Problem(sessions=[grad, joint, ug])
    sched = Schedule()
    sched.place("g-lec", day=0, start_box=0, room_id="hall1")
    sched.place("j-lec", day=1, start_box=2, room_id="hall6")
    sched.place("u-lec", day=2, start_box=4, room_id="room3")
    return problem, sched


def test_a_graduate_course_appears_on_no_cohort_page():
    # It carries no cohort by design (D4) — which is exactly why it needs a page.
    problem, sched = _grad_problem()
    grids = cohort_grid_cells(problem, sched)
    assert all(c.session_id != "g-lec" for cells in grids.values() for c in cells)


def test_the_graduate_page_carries_graduate_and_joint_courses():
    # A graduate student combines the two, so their timetable is both.
    from schedy.exporters import GRADUATE_PAGE, graduate_grid_cells
    problem, sched = _grad_problem()
    cells = graduate_grid_cells(problem, sched)
    assert {c.session_id for c in cells} == {"g-lec", "j-lec"}
    assert GRADUATE_PAGE


def test_the_cohort_pdf_includes_a_graduate_page():
    problem, sched = _grad_problem()
    from schedy.exporters import GRADUATE_PAGE, cohort_pages
    assert GRADUATE_PAGE in cohort_pages(problem, sched)


def test_there_is_no_graduate_page_without_graduate_courses():
    problem, sched = _problem()   # undergraduate only
    from schedy.exporters import GRADUATE_PAGE, cohort_pages
    assert GRADUATE_PAGE not in cohort_pages(problem, sched)


def test_the_graduate_page_renders():
    problem, sched = _grad_problem()
    pdf = to_pdf(problem, sched, layout="cohort",
                 course_names={"00580001": "תרמודינמיקה מתקדמת"})
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 1000


# ---- per-room and per-person pages -------------------------------------- #

def _staffed_problem():
    lec = Session("s-lec", "C1", SessionType.LECTURE, 2,
                  cohorts=frozenset({CHEME2}), lecturer_ids=("dr_x", "dr_y"))
    ex = Session("s-ex", "C1", SessionType.EXERCISE, 1,
                 cohorts=frozenset({CHEME2}), group="SE011",
                 lecturer_ids=("dr_x",), ta_ids=("hedva",))
    idle = Session("s-idle", "C2", SessionType.LECTURE, 1,
                   cohorts=frozenset({CHEME2}), lecturer_ids=("dr_z",))
    problem = Problem(sessions=[lec, ex, idle])
    sched = Schedule()
    sched.place("s-lec", day=0, start_box=0, room_id="hall1")
    sched.place("s-ex", day=2, start_box=4, room_id="hall1")
    return problem, sched    # s-idle is never placed


def test_room_pages_has_one_page_per_used_room():
    problem, sched = _staffed_problem()
    sched.place("s-idle", day=1, start_box=1, room_id="room3")
    pages = room_pages(problem, sched)
    assert set(pages) == {"hall1", "room3"}
    assert sorted((c.day, c.start_box) for c in pages["hall1"]) == [(0, 0), (2, 4)]
    assert [c.session_id for c in pages["room3"]] == ["s-idle"]


def test_room_pages_skips_rooms_with_no_placement():
    problem, sched = _staffed_problem()
    assert set(room_pages(problem, sched)) == {"hall1"}


def test_person_pages_cover_every_lecturer_and_ta_of_a_placed_session():
    problem, sched = _staffed_problem()
    pages = person_pages(problem, sched)
    assert set(pages) == {"dr_x", "dr_y", "hedva"}   # dr_z teaches only s-idle
    # the two-lecturer session appears on both lecturers' pages
    assert [c.session_id for c in pages["dr_y"]] == ["s-lec"]
    assert sorted(c.session_id for c in pages["dr_x"]) == ["s-ex", "s-lec"]
    assert [(c.day, c.start_box) for c in pages["hedva"]] == [(2, 4)]


def _page_count(pdf: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page(?!s)", pdf))


def test_pdf_room_layout_has_one_page_per_room():
    problem, sched = _staffed_problem()
    sched.place("s-idle", day=1, start_box=1, room_id="room3")
    assert _page_count(to_pdf(problem, sched, layout="room")) == 2


def test_pdf_person_layout_has_one_page_per_person():
    problem, sched = _staffed_problem()
    assert _page_count(to_pdf(problem, sched, layout="person")) == 3


# ---- hardening (review round 4) ---------------------------------------- #

def test_labels_are_escaped_in_pdf_markup(tmp_path):
    evil = Session("e", "C9", SessionType.LECTURE, 1, cohorts=frozenset({CHEME2}),
                   lecturer_ids=('<img src="/etc/hostname" width="9" height="9"/>',
                                 "<b>unclosed"))
    problem = Problem(sessions=[evil])
    sched = Schedule()
    sched.place("e", day=0, start_box=0, room_id="hall1")
    for layout in ("person", "room", "cohort", "flat"):
        pdf = to_pdf(problem, sched, layout=layout, title="<b>t")
        assert pdf[:4] == b"%PDF"
        assert b"/Subtype /Image" not in pdf and b"/Subtype/Image" not in pdf


def test_overlapping_cells_are_all_kept_in_stacked_blocks():
    from schedy.exporters import GridCell, stack_cells
    a = GridCell("a", "A1", "lecture", None, "R", 0, 0, 3)
    b = GridCell("b", "B1", "lecture", None, "R", 0, 2, 1)   # starts inside a
    c = GridCell("c", "C1", "lecture", None, "R", 0, 5, 1)
    d = GridCell("d", "D1", "lecture", None, "R", 1, 0, 1)
    blocks = stack_cells([c, b, a, d])
    assert sorted(x.session_id for blk in blocks for x in blk.cells) == ["a", "b", "c", "d"]
    ab = next(blk for blk in blocks if len(blk.cells) == 2)
    assert (ab.day, ab.start_box, ab.span) == (0, 0, 3)
    assert [x.session_id for x in ab.cells] == ["a", "b"]


def test_stacked_lines_print_each_own_time_when_ranges_differ():
    from schedy.exporters import GridCell, stack_cells, stacked_lines
    a = GridCell("a", "A1", "lecture", None, "R", 0, 0, 3)   # 08:30-11:30
    b = GridCell("b", "B1", "lecture", None, "R", 0, 2, 1)   # 10:30-11:30
    (blk,) = stack_cells([a, b])
    la, lb = stacked_lines(blk, {}, False)
    assert la == ["<b>A1</b>", "lect · R", "08:30\u201311:30"]
    assert lb == ["<b>B1</b>", "lect · R", "10:30\u201311:30"]


def test_stacked_lines_omit_time_for_single_or_identical_ranges():
    from schedy.exporters import GridCell, stack_cells, stacked_lines
    a = GridCell("a", "A1", "lecture", None, "R", 0, 0, 2)
    b = GridCell("b", "B1", "lab", "g1", "R2", 0, 0, 2)
    (solo,) = stack_cells([a])
    assert stacked_lines(solo, {}, False) == [["<b>A1</b>", "lect · R"]]
    (pair,) = stack_cells([a, b])
    assert stacked_lines(pair, {}, False) == [
        ["<b>A1</b>", "lect · R"], ["<b>B1</b>", "lab g1 · R2"]]


def test_overlapping_sessions_render_in_room_pdf():
    s1 = Session("a", "C1", SessionType.LECTURE, 3, cohorts=frozenset({CHEME2}))
    s2 = Session("b", "C2", SessionType.LECTURE, 1, cohorts=frozenset({CHEME2}))
    problem = Problem(sessions=[s1, s2])
    sched = Schedule()
    sched.place("a", day=0, start_box=0, room_id="hall1")
    sched.place("b", day=0, start_box=2, room_id="hall1")
    assert to_pdf(problem, sched, layout="room")[:4] == b"%PDF"


def test_provisional_sessions_are_flagged_on_room_and_person_pages():
    prov = Session("p", "G1", SessionType.LECTURE, 1, cohorts=frozenset(),
                   lecturer_ids=("dr_x",), provisional=True)
    real = Session("r", "C1", SessionType.LECTURE, 1, cohorts=frozenset({CHEME2}),
                   lecturer_ids=("dr_x",))
    problem = Problem(sessions=[prov, real])
    sched = Schedule()
    sched.place("p", day=0, start_box=0, room_id="hall1")
    sched.place("r", day=1, start_box=0, room_id="hall1")
    for pages in (room_pages(problem, sched), person_pages(problem, sched)):
        (cells,) = pages.values()
        assert {c.session_id: c.provisional for c in cells} == {"p": True, "r": False}


def test_rooms_with_the_same_name_get_separate_pages():
    from schedy.domain import Room
    s1 = Session("a", "C1", SessionType.LECTURE, 1, cohorts=frozenset({CHEME2}))
    s2 = Session("b", "C2", SessionType.LECTURE, 1, cohorts=frozenset({CHEME2}))
    problem = Problem(sessions=[s1, s2],
                      rooms=[Room("r1", "Same", 10), Room("r2", "Same", 10)])
    sched = Schedule()
    sched.place("a", day=0, start_box=0, room_id="r1")
    sched.place("b", day=0, start_box=0, room_id="r2")
    assert set(room_pages(problem, sched)) == {"r1", "r2"}
    assert _page_count(to_pdf(problem, sched, layout="room")) == 2


def test_person_page_titles_use_registry_names_and_hebrew_renders():
    from schedy.exporters import _grid_story
    problem, sched = _staffed_problem()
    # the registry name reaches the story's title row
    story = _grid_story({"dr_x": []}, {}, ("Helvetica", "Helvetica-Bold", False),
                        __import__("reportlab.lib.styles", fromlist=["x"]).getSampleStyleSheet(),
                        "T", labels={"dr_x": "Dr. Xavier"})
    assert "Dr. Xavier" in story[0]._cellvalues[0][0].text
    pdf = to_pdf(problem, sched, layout="person",
                 person_names={"dr_x": "ד\"ר כהן", "hedva": "Hedva"})
    assert pdf[:4] == b"%PDF"


def test_resource_heading_repeats_on_continuation_pages():
    from schedy.exporters import _grid_story
    from reportlab.lib.styles import getSampleStyleSheet
    cells = [GridCellX(i) for i in range(10)]
    story = _grid_story({"hall1": cells}, {f"C{i}": "x" * 70 for i in range(10)},
                        ("Helvetica", "Helvetica-Bold", False),
                        getSampleStyleSheet(), "T", labels={"hall1": "Hall 1"})
    tables = [f for f in story if hasattr(f, "_cellvalues")]
    assert tables[0].repeatRows == 2        # title row + day-header row repeat
    problem = Problem(sessions=[
        Session(f"s{i}", f"C{i}", SessionType.LECTURE, 1, cohorts=frozenset({CHEME2}))
        for i in range(10)])
    sched = Schedule()
    for i in range(10):
        sched.place(f"s{i}", day=0, start_box=i, room_id="hall1")
    to_pdf(problem, sched, layout="room",
           course_names={f"C{i}": "ש" * 70 for i in range(10)})


def GridCellX(i):
    from schedy.exporters import GridCell
    return GridCell(f"s{i}", f"C{i}", "lecture", None, "Hall 1", 0, i, 1)


def test_unstaffed_sessions_get_an_unassigned_page():
    from schedy.exporters import UNASSIGNED_PAGE
    s = Session("u", "C1", SessionType.LECTURE, 1, cohorts=frozenset({CHEME2}))
    problem = Problem(sessions=[s])
    sched = Schedule()
    sched.place("u", day=0, start_box=0, room_id="hall1")
    pages = person_pages(problem, sched)
    assert [c.session_id for c in pages[UNASSIGNED_PAGE]] == ["u"]
    assert _page_count(to_pdf(problem, sched, layout="person")) == 1
