"""Exporters — turn a solved Schedule into the planner's deliverables.

Three views (per cohort, per room, per lecturer/TA) over two formats:
  * CSV  — a flat dump of all assignments (pure, deterministic, golden-testable).
  * PDF  — printable weekly timetables (reportlab), one grid page per cohort,
           room or person.

The view-building logic is pure and lives in `cohort_pages` / `room_pages` /
`person_pages` / `assignment_rows` / `to_csv`; only
`to_pdf` touches reportlab. No university-XLSX writeback (out of scope per PRD).
"""

from __future__ import annotations

import csv
import io
import os
from dataclasses import dataclass

from .domain import (
    BOXES_PER_DAY,
    DAY_NAMES,
    CourseLevel,
    Problem,
    Schedule,
    box_interval,
    box_label,
    minutes_to_hhmm,
)

_FONTS_DIR = os.path.join(os.path.dirname(__file__), "assets", "fonts")
_PDF_FONT = "DejaVuSans"        # bundled, carries Hebrew glyphs (RTL via python-bidi)
_PDF_FONT_BOLD = "DejaVuSans-Bold"
_fonts_registered = False


def _ensure_fonts() -> bool:
    """Register the bundled Hebrew-capable font with reportlab once.

    Returns True if the font is available; callers fall back to a built-in font
    (Hebrew will not render) when it is not.
    """
    global _fonts_registered
    if _fonts_registered:
        return True
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    reg = os.path.join(_FONTS_DIR, "DejaVuSans.ttf")
    bold = os.path.join(_FONTS_DIR, "DejaVuSans-Bold.ttf")
    if not os.path.isfile(reg):
        return False
    pdfmetrics.registerFont(TTFont(_PDF_FONT, reg))
    if os.path.isfile(bold):
        pdfmetrics.registerFont(TTFont(_PDF_FONT_BOLD, bold))
    _fonts_registered = True
    return True


def _rtl(text: str) -> str:
    """Reorder a (possibly Hebrew) string for visual display in the PDF.

    reportlab does not run the Unicode bidi algorithm, so right-to-left text must
    be pre-shaped. python-bidi handles mixed Hebrew/Latin/digits correctly; if it
    is unavailable we return the text unchanged.
    """
    if not text:
        return text
    try:
        from bidi import get_display
    except Exception:  # noqa: BLE001 — optional dependency, degrade gracefully
        return text
    return get_display(text)


@dataclass(frozen=True)
class AssignmentRow:
    course_number: str
    session_id: str
    session_type: str
    group: str
    day: str
    time: str
    room: str
    cohorts: str
    lecturers: str
    tas: str


def assignment_rows(problem: Problem, schedule: Schedule) -> list[AssignmentRow]:
    """Flat, sorted list of every placement — the canonical export view."""
    rows: list[AssignmentRow] = []
    for sid, p in schedule.placements.items():
        s = problem.session(sid)
        rows.append(AssignmentRow(
            course_number=s.course_number,
            session_id=s.id,
            session_type=s.type.value,
            group=s.group or "",
            day=DAY_NAMES[p.day],
            time=box_label(p.start_box) if s.length_boxes == 1 else
            f"{box_label(p.start_box).split('-')[0]}-"
            f"{box_label(p.start_box + s.length_boxes - 1).split('-')[1]}",
            room=problem.room(p.room_id).name,
            cohorts="; ".join(sorted(c.label for c in s.cohorts)),
            lecturers="; ".join(s.lecturer_ids),
            tas="; ".join(s.ta_ids),
        ))
    rows.sort(key=lambda r: (r.day, r.time, r.room))
    return rows


@dataclass(frozen=True)
class GridCell:
    """One placed session as it appears on a cohort's weekly grid."""
    session_id: str
    course_number: str
    type: str
    group: str | None
    room: str
    day: int
    start_box: int
    span: int  # length in boxes (rows it covers, starting at start_box)
    provisional: bool = False  # a graduate reservation, not a confirmed course


def cohort_grid_cells(problem: Problem, schedule: Schedule) -> dict[str, list[GridCell]]:
    """Group placed sessions by cohort label for the per-cohort grid pages."""
    out: dict[str, list[GridCell]] = {}
    for sid, p in schedule.placements.items():
        s = problem.session(sid)
        cell = GridCell(
            session_id=sid, course_number=s.course_number, type=s.type.value,
            group=s.group, room=problem.room(p.room_id).name,
            day=p.day, start_box=p.start_box, span=s.length_boxes,
        )
        for c in s.cohorts:
            out.setdefault(c.label, []).append(cell)
    return out


# The graduate timetable is not a cohort, so it needs a name of its own.
GRADUATE_PAGE = "Graduate"


def graduate_grid_cells(problem: Problem, schedule: Schedule) -> list[GridCell]:
    """The graduate timetable: every graduate and joint session.

    Graduate courses carry no cohort (PRD D4), so they appear on no per-cohort
    page — this page is what makes that safe. Joint courses belong here too: a
    graduate student combines the two, and their week is both.

    Provisional stand-ins are left off: they hold hours during phase 1, but this
    page is a timetable handed to students, and a guess has no place on one.
    """
    out: list[GridCell] = []
    for sid, p in schedule.placements.items():
        s = problem.session(sid)
        if s.level not in (CourseLevel.GRAD, CourseLevel.JOINT):
            continue
        if s.provisional:
            continue    # a placeholder, not a course anyone can enrol in
        out.append(GridCell(
            session_id=sid, course_number=s.course_number, type=s.type.value,
            group=s.group, room=problem.room(p.room_id).name,
            day=p.day, start_box=p.start_box, span=s.length_boxes,
        ))
    return out


def cohort_pages(problem: Problem, schedule: Schedule) -> dict[str, list[GridCell]]:
    """Every page of the printable timetable: one per cohort, plus graduate."""
    pages = cohort_grid_cells(problem, schedule)
    grad = graduate_grid_cells(problem, schedule)
    if grad:
        pages[GRADUATE_PAGE] = grad
    return pages


# Sessions with no lecturer and no TA land on this page of the person layout.
UNASSIGNED_PAGE = "\x00unassigned"


def _resource_cell(problem: Problem, sid: str, p) -> GridCell:
    s = problem.session(sid)
    return GridCell(
        session_id=sid, course_number=s.course_number, type=s.type.value,
        group=s.group, room=problem.room(p.room_id).name,
        day=p.day, start_box=p.start_box, span=s.length_boxes,
        provisional=s.provisional,
    )


def room_pages(problem: Problem, schedule: Schedule) -> dict[str, list[GridCell]]:
    """Group placed sessions by room id: one page per room in use.

    Keyed by id, not name, so two rooms that share a name stay two pages.
    Provisional sessions are kept (the room really is held) and flagged.
    """
    out: dict[str, list[GridCell]] = {}
    for sid, p in schedule.placements.items():
        out.setdefault(p.room_id, []).append(_resource_cell(problem, sid, p))
    return out


def person_pages(problem: Problem, schedule: Schedule) -> dict[str, list[GridCell]]:
    """Group placed sessions by lecturer/TA id; shared sessions appear on each.

    Sessions with no staff go on `UNASSIGNED_PAGE` so none is silently dropped.
    """
    out: dict[str, list[GridCell]] = {}
    for sid, p in schedule.placements.items():
        s = problem.session(sid)
        cell = _resource_cell(problem, sid, p)
        ids = list(dict.fromkeys((*s.lecturer_ids, *s.ta_ids))) or [UNASSIGNED_PAGE]
        for pid in ids:
            out.setdefault(pid, []).append(cell)
    return out


@dataclass(frozen=True)
class StackedBlock:
    """One drawn block on a grid: a cell, or several that overlap in time."""
    day: int
    start_box: int
    span: int
    cells: tuple[GridCell, ...]


def stack_cells(cells: list[GridCell]) -> list[StackedBlock]:
    """Merge cells that overlap in one day into stacked blocks.

    Manual edits can place two sessions on top of each other; a grid cannot
    draw overlapping spans, so the overlapping sessions share one block
    (spanning their union) and every one of them is shown.
    """
    blocks: list[list] = []   # [day, start, end(excl), [cells]]
    for c in sorted(cells, key=lambda x: (x.day, x.start_box, x.session_id)):
        end = c.start_box + c.span
        last = blocks[-1] if blocks else None
        if last and last[0] == c.day and c.start_box < last[2]:
            last[2] = max(last[2], end)
            last[3].append(c)
        else:
            blocks.append([c.day, c.start_box, end, [c]])
    return [StackedBlock(d, st, en - st, tuple(cs)) for d, st, en, cs in blocks]


def stacked_lines(blk: StackedBlock, course_names: dict[str, str],
                  has_font: bool) -> list[list[str]]:
    """Markup lines for each cell of a block, one list per cell.

    When the cells of a stacked block cover different time ranges, each also
    gets its own range: the block spans their union, so without it a reader
    would take every session for the full block.
    """
    from xml.sax.saxutils import escape

    ranges = {(c.start_box, c.span) for c in blk.cells}
    out = []
    for c in blk.cells:
        lines = [f"<b>{escape(c.course_number)}</b>"]
        name = course_names.get(c.course_number, "")
        if name and has_font:
            lines.append(escape(_rtl(name)))
        sub = c.type[:4]
        if c.group:
            sub += f" {escape(c.group)}"
        sub += f" · {escape(c.room)}"
        if c.provisional:
            sub += " (provisional)"
        lines.append(sub)
        if len(ranges) > 1:
            s, e = box_interval(c.start_box, c.span)
            lines.append(f"{minutes_to_hhmm(s)}\u2013{minutes_to_hhmm(e)}")
        out.append(lines)
    return out


CSV_HEADER = [
    "course_number", "session_id", "session_type", "group", "day", "time",
    "room", "cohorts", "lecturers", "tas",
]


def to_csv(problem: Problem, schedule: Schedule) -> str:
    """Flat CSV/Excel-compatible export of all assignments."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_HEADER)
    for r in assignment_rows(problem, schedule):
        writer.writerow([
            r.course_number, r.session_id, r.session_type, r.group, r.day,
            r.time, r.room, r.cohorts, r.lecturers, r.tas,
        ])
    return buf.getvalue()


def to_pdf(
    problem: Problem,
    schedule: Schedule,
    title: str = "Schedy timetable",
    course_names: dict[str, str] | None = None,
    layout: str = "flat",
    person_names: dict[str, str] | None = None,
) -> bytes:
    """Printable PDF of the schedule.

    `layout="flat"` (default) is one sorted table of every assignment;
    `layout="cohort"` is one weekly Sun–Thu × academic-hour grid page per cohort
    — the printable class timetable; `"room"` and `"person"` give the same grid
    per room and per lecturer/TA. `course_names` maps course number -> display
    name (Hebrew preferred), rendered right-to-left via the bundled Hebrew font;
    without it (or the font) the export still works in ASCII. `person_names`
    maps lecturer/TA id -> display name for the person layout's page titles.
    """
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate
    from reportlab.lib.styles import getSampleStyleSheet

    has_font = _ensure_fonts()
    fonts = (
        _PDF_FONT if has_font else "Helvetica",
        _PDF_FONT_BOLD if has_font else "Helvetica-Bold",
        has_font,
    )
    styles = getSampleStyleSheet()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4))
    pages_by_layout = {"cohort": cohort_pages, "room": room_pages, "person": person_pages}
    if layout in pages_by_layout:
        grids = pages_by_layout[layout](problem, schedule)
        labels: dict[str, str] = {}
        if layout == "room":
            labels = {rid: problem.room(rid).name for rid in grids}
        elif layout == "person":
            labels = {pid: (person_names or {}).get(pid) or pid for pid in grids}
            labels[UNASSIGNED_PAGE] = "Unassigned"
        story = _grid_story(grids, course_names or {}, fonts, styles, title,
                            labels=labels)
    else:
        story = _flat_story(problem, schedule, course_names or {}, fonts, styles, title)
    doc.build(story)
    return buf.getvalue()


def _flat_story(problem, schedule, course_names, fonts, styles, title):
    from xml.sax.saxutils import escape

    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle, Paragraph

    body_font, head_font, has_font = fonts
    show_name = bool(course_names) and has_font
    header = ["Course"]
    if show_name:
        header.append("Name")
    header += ["Type", "Group", "Day", "Time", "Room", "Cohorts"]
    data = [header]
    for r in assignment_rows(problem, schedule):
        row = [r.course_number]
        if show_name:
            row.append(_rtl(course_names.get(r.course_number, "")))
        row += [r.session_type, r.group, r.day, r.time, r.room, r.cohorts]
        data.append(row)

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2b6cb0")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), head_font),
        ("FONTNAME", (0, 1), (-1, -1), body_font),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f0f4f8")]),
    ]))
    return [Paragraph(escape(title), styles["Title"]), table]


def _grid_story(grids, course_names, fonts, styles, title, labels=None):
    from xml.sax.saxutils import escape

    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import PageBreak, Paragraph, Table, TableStyle

    body_font, head_font, has_font = fonts
    labels = labels or {}
    cell_style = ParagraphStyle("cell", fontName=body_font, fontSize=7, leading=8.5)
    title_style = ParagraphStyle("pagetitle", parent=styles["Title"], fontName=head_font)
    if not grids:
        return [Paragraph(escape(title), title_style),
                Paragraph("No sessions placed yet.", styles["Normal"])]

    def heading(label):
        text = labels.get(label, label)
        if has_font:
            text = _rtl(text)
        return Paragraph(escape(f"{title} — {text}"), title_style)

    ncols = 1 + len(DAY_NAMES)
    col_widths = [2.2 * cm] + [4.5 * cm] * len(DAY_NAMES)
    story = []
    # Pages alphabetically by label, then the graduate page and the unassigned
    # page last: appendices to the main timetable, not members of it.
    order = sorted(grids, key=lambda k: (k in (GRADUATE_PAGE, UNASSIGNED_PAGE),
                                         k == UNASSIGNED_PAGE, labels.get(k, k)))
    for page_i, label in enumerate(order):
        # Row 0 is the page title and row 1 the day header; both repeat when a
        # crowded page spills, so a continuation still says whose it is.
        data = [[heading(label)] + [""] * (ncols - 1), ["", *DAY_NAMES]]
        for b in range(BOXES_PER_DAY):
            data.append([box_label(b), "", "", "", "", ""])
        spans = [("SPAN", (0, 0), (-1, 0))]
        for blk in stack_cells(grids[label]):
            col, row0 = blk.day + 1, blk.start_box + 2
            paras = [Paragraph("<br/>".join(lines), cell_style)
                     for lines in stacked_lines(blk, course_names, has_font)]
            data[row0][col] = paras[0] if len(paras) == 1 else paras
            if blk.span > 1:
                spans.append(("SPAN", (col, row0), (col, row0 + blk.span - 1)))

        table = Table(data, colWidths=col_widths, repeatRows=2)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 1), colors.HexColor("#2b6cb0")),
            ("TEXTCOLOR", (0, 0), (-1, 1), colors.white),
            ("BACKGROUND", (0, 2), (0, -1), colors.HexColor("#f1f5f9")),
            ("FONTNAME", (0, 0), (-1, 1), head_font),
            ("FONTNAME", (0, 2), (0, -1), body_font),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 1), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            *spans,
        ]))
        story.append(table)
        if page_i < len(order) - 1:
            story.append(PageBreak())
    return story
