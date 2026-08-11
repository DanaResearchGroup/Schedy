"""Tests for the courses-of-interest file reader.

The file is hand-maintained, so most of what matters here is tolerance: the
shapes a planner might plausibly hand us all have to land on the same records.
"""

from __future__ import annotations

import io

import openpyxl
import pytest

from schedy.coi_io import (
    from_csv,
    from_rows,
    from_upload,
    from_xlsx_bytes,
    normalize_number,
    template_csv,
    to_csv,
)

NUMBERS = ["00540315", "00540319", "01040031"]


def numbers(items) -> list[str]:
    return [it["number"] for it in items]


# --- the accepted shapes -------------------------------------------------- #

def test_headed_csv():
    items = from_csv("number,name\n00540315,תרמודינמיקה\n00540319,תופעות מעבר\n")
    assert items == [
        {"number": "00540315", "name": "תרמודינמיקה"},
        {"number": "00540319", "name": "תופעות מעבר"},
    ]


def test_bare_list_without_a_header():
    assert numbers(from_csv("00540315\n00540319\n01040031\n")) == NUMBERS


def test_column_order_and_hebrew_headers():
    """Either column order, either language — the header names the columns."""
    assert from_csv("name,number\nתרמודינמיקה,00540315\n") == [
        {"number": "00540315", "name": "תרמודינמיקה"}]
    assert from_csv("מקצוע,שם\n00540315,תרמודינמיקה\n") == [
        {"number": "00540315", "name": "תרמודינמיקה"}]


def test_unrecognised_header_falls_back_to_positional_columns():
    items = from_csv("Course code,Title\n00540315,תרמודינמיקה\n")
    assert items == [{"number": "00540315", "name": "תרמודינמיקה"}]


def test_blank_lines_and_repeats_are_dropped():
    items = from_csv("00540315\n\n00540315\n00540319\n\n")
    assert numbers(items) == ["00540315", "00540319"]


def test_empty_file_gives_no_records():
    assert from_csv("") == []
    assert from_csv("number,name\n") == []
    assert from_rows([]) == []


def test_bom_is_tolerated():
    assert numbers(from_csv("﻿number,name\n00540315,x\n")) == ["00540315"]


# --- Excel's leading-zero problem ----------------------------------------- #

def test_excel_stripped_leading_zeros_are_restored():
    """Excel turns 00540315 into 540315; unrepaired, the list matches nothing."""
    assert normalize_number(540315) == "00540315"
    assert normalize_number("540315") == "00540315"
    assert normalize_number(540315.0) == "00540315"
    assert numbers(from_csv("number\n540315\n")) == ["00540315"]


def test_already_padded_numbers_are_left_alone():
    assert normalize_number("00540315") == "00540315"
    assert normalize_number(" 00540315 ") == "00540315"


def test_non_numeric_values_pass_through_unchanged():
    assert normalize_number("054031A") == "054031A"


# --- round trips ---------------------------------------------------------- #

def test_csv_round_trip():
    items = [{"number": n, "name": f"course {n}"} for n in NUMBERS]
    assert from_csv(to_csv(items)) == items


def test_template_is_readable_by_our_own_reader():
    items = from_csv(template_csv())
    assert len(items) == 3
    assert all(len(it["number"]) == 8 and it["name"] for it in items)


# --- Excel files ---------------------------------------------------------- #

def xlsx_bytes(rows) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    for r in rows:
        ws.append(list(r))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_xlsx_headed():
    data = xlsx_bytes([["number", "name"], ["00540315", "תרמודינמיקה"]])
    assert from_xlsx_bytes(data) == [{"number": "00540315", "name": "תרמודינמיקה"}]


def test_xlsx_numeric_cells_are_repaired():
    """openpyxl hands numeric-looking cells back as int/float."""
    data = xlsx_bytes([["number", "name"], [540315, "a"], [540319.0, "b"]])
    assert numbers(from_xlsx_bytes(data)) == ["00540315", "00540319"]


def test_xlsx_bare_list():
    data = xlsx_bytes([[n] for n in NUMBERS])
    assert numbers(from_xlsx_bytes(data)) == NUMBERS


def test_from_upload_picks_the_reader_by_extension():
    csv_text = "number,name\n00540315,x\n".encode("utf-8")
    assert numbers(from_upload(csv_text, "list.csv")) == ["00540315"]

    data = xlsx_bytes([["number", "name"], ["00540315", "x"]])
    assert numbers(from_upload(data, "list.xlsx")) == ["00540315"]
    # openpyxl reads macro-enabled workbooks too; without this they would fall
    # through to the CSV reader and die on a decode error.
    assert numbers(from_upload(data, "list.xlsm")) == ["00540315"]


def test_legacy_xls_is_refused_with_a_useful_message():
    """openpyxl can't read .xls; say so instead of "not a zip file"."""
    ole2 = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 512
    with pytest.raises(ValueError, match="Save As"):
        from_upload(ole2, "list.xls")


def test_all_three_example_shapes_agree():
    """The three shapes shipped in examples/ must produce the same numbers."""
    headed = from_csv("number,name\n" + "".join(f"{n},x\n" for n in NUMBERS))
    bare = from_csv("".join(f"{n}\n" for n in NUMBERS))
    excel = from_xlsx_bytes(xlsx_bytes([["number", "name"], *[[n, "x"] for n in NUMBERS]]))
    assert numbers(headed) == numbers(bare) == numbers(excel) == NUMBERS
