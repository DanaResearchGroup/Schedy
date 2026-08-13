"""Tests for the shared upload filename rules."""

from __future__ import annotations

import pytest

from schedy.uploads import is_excel, reject_legacy_xls


@pytest.mark.parametrize("name", ["book.xlsx", "book.xlsm", "BOOK.XLSX", "a.b.xlsx"])
def test_zip_based_formats_are_read_as_excel(name):
    assert is_excel(name) is True


@pytest.mark.parametrize("name", ["list.csv", "list.txt", "list", "notes.xlsb"])
def test_everything_else_falls_through_to_csv(name):
    assert is_excel(name) is False


def test_legacy_xls_is_not_excel_and_is_refused():
    # Both halves matter: it must not be routed to openpyxl, and it must be
    # refused explicitly rather than silently decoded as CSV text.
    assert is_excel("book.xls") is False
    with pytest.raises(ValueError, match="Save As"):
        reject_legacy_xls("book.xls")
    with pytest.raises(ValueError):
        reject_legacy_xls("BOOK.XLS")


@pytest.mark.parametrize("name", ["book.xlsx", "book.xlsm", "list.csv", ""])
def test_supported_names_pass_the_guard(name):
    assert reject_legacy_xls(name) is None
