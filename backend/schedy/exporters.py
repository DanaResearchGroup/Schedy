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
) -> bytes:
    """Printable PDF table of all assignments.

    `course_names` maps course number -> display name (Hebrew preferred); when
    given, a Name column is added and rendered right-to-left via the bundled
    Hebrew font. Without it (or the font), the export still works in ASCII.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
    from reportlab.lib.styles import getSampleStyleSheet

    has_font = _ensure_fonts()
    show_name = bool(course_names) and has_font
    body_font = _PDF_FONT if has_font else "Helvetica"
    head_font = _PDF_FONT_BOLD if has_font else "Helvetica-Bold"

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4))
    styles = getSampleStyleSheet()

    header = ["Course"]
    if show_name:
        header.append("Name")
    header += ["Type", "Group", "Day", "Time", "Room", "Cohorts"]
    data = [header]
    for r in assignment_rows(problem, schedule):
        row = [r.course_number]
        if show_name:
            row.append(_rtl((course_names or {}).get(r.course_number, "")))
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
    doc.build([Paragraph(title, styles["Title"]), table])
    return buf.getvalue()
