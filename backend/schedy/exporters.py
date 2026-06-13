"""Exporters — turn a solved Schedule into the planner's deliverables.

Three views (per cohort, per room, per lecturer/TA) over two formats:
  * CSV  — a flat dump of all assignments (pure, deterministic, golden-testable).
  * PDF  — printable weekly timetables (reportlab).

The view-building logic is pure and lives in `grid_rows` / `to_csv`; only
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
    Problem,
    Schedule,
    box_label,
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
) -> bytes:
    """Printable PDF of the schedule.

    `layout="flat"` (default) is one sorted table of every assignment;
    `layout="cohort"` is one weekly Sun–Thu × academic-hour grid page per cohort
    — the printable class timetable. `course_names` maps course number -> display
    name (Hebrew preferred), rendered right-to-left via the bundled Hebrew font;
    without it (or the font) the export still works in ASCII.
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
    if layout == "cohort":
        story = _cohort_story(problem, schedule, course_names or {}, fonts, styles, title)
    else:
        story = _flat_story(problem, schedule, course_names or {}, fonts, styles, title)
    doc.build(story)
    return buf.getvalue()


def _flat_story(problem, schedule, course_names, fonts, styles, title):
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
    return [Paragraph(title, styles["Title"]), table]


def _cohort_story(problem, schedule, course_names, fonts, styles, title):
    from xml.sax.saxutils import escape

    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import PageBreak, Paragraph, Spacer, Table, TableStyle

    body_font, head_font, has_font = fonts
    cell_style = ParagraphStyle("cell", fontName=body_font, fontSize=7, leading=8.5)
    grids = cohort_grid_cells(problem, schedule)
    if not grids:
        return [Paragraph(title, styles["Title"]),
                Paragraph("No sessions placed yet.", styles["Normal"])]

    col_widths = [2.2 * cm] + [4.5 * cm] * len(DAY_NAMES)
    story = []
    for page_i, label in enumerate(sorted(grids)):
        data = [["", *DAY_NAMES]]
        for b in range(BOXES_PER_DAY):
            data.append([box_label(b), "", "", "", "", ""])
        spans = []
        for c in sorted(grids[label], key=lambda x: (x.day, x.start_box)):
            col, row0 = c.day + 1, c.start_box + 1
            lines = [f"<b>{escape(c.course_number)}</b>"]
            name = course_names.get(c.course_number, "")
            if name and has_font:
                lines.append(escape(_rtl(name)))
            sub = c.type[:4]
            if c.group:
                sub += f" {escape(c.group)}"
            sub += f" · {escape(c.room)}"
            lines.append(sub)
            para = Paragraph("<br/>".join(lines), cell_style)
            existing = data[row0][col]
            data[row0][col] = para if not existing else [existing, para]
            if c.span > 1:
                spans.append(("SPAN", (col, row0), (col, c.start_box + c.span)))

        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2b6cb0")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#f1f5f9")),
            ("FONTNAME", (0, 0), (-1, 0), head_font),
            ("FONTNAME", (0, 1), (0, -1), body_font),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            *spans,
        ]))
        story.append(Paragraph(f"{title} — {label}", styles["Title"]))
        story.append(Spacer(1, 0.2 * cm))
        story.append(table)
        if page_i < len(grids) - 1:
            story.append(PageBreak())
    return story
