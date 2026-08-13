"""Filename rules shared by the file-import endpoints (pure).

Three endpoints take a spreadsheet upload — the catalog, the courses-of-interest
list, and the Technion skeleton — and all three read it with openpyxl, which
handles only the zip-based formats. Deciding "Excel or CSV?" and refusing the one
format that looks supported but isn't belongs in one place, or the three drift.
"""

from __future__ import annotations

# What openpyxl actually reads. `.xlsm` is a zip like `.xlsx`, just macro-enabled.
EXCEL_SUFFIXES = (".xlsx", ".xlsm")

LEGACY_SUFFIX = ".xls"

LEGACY_MESSAGE = (
    "legacy .xls files are not supported; open it in Excel and use "
    "Save As → .xlsx (or .csv)"
)


def reject_legacy_xls(filename: str) -> None:
    """Raise on a pre-2007 `.xls`, which openpyxl cannot read.

    Left to reach openpyxl, an `.xls` fails as "File is not a zip file" — true,
    but it tells the planner nothing about what to do next.
    """
    if filename.lower().endswith(LEGACY_SUFFIX):
        raise ValueError(LEGACY_MESSAGE)


def is_excel(filename: str) -> bool:
    """Whether to read this upload with openpyxl rather than as CSV text."""
    return filename.lower().endswith(EXCEL_SUFFIXES)
