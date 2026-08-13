"""Term scoping: academic year + semester, and migration from the single-term store.

The department plans one semester at a time and publishes per semester, so every
piece of working state belongs to a term. These tests pin the scoping rules and
the one-way migration that stamps a pre-term database as its first term.
"""

from __future__ import annotations

import sqlite3

import pytest

from schedy.catalog import Course
from schedy.domain import Program
from schedy.store import GLOBAL_KEYS, Store, TermId


def _course(number: str) -> Course:
    return Course(number=number, programs=[Program.CHEME], year=2, lecture_boxes=2)


@pytest.fixture()
def store(tmp_path):
    s = Store(str(tmp_path / "t.sqlite"))
    yield s
    s.close()


# ---- term identity ---------------------------------------------------- #

def test_term_id_renders_year_and_semester():
    t = TermId("2026-27", "spring")
    assert str(t) == "2026-27-spring"
    assert TermId.parse("2026-27-spring") == t


def test_term_id_rejects_a_malformed_year():
    with pytest.raises(ValueError):
        TermId("2026", "spring")
    with pytest.raises(ValueError):
        TermId("2026-27", "summer")


def test_previous_year_same_semester_is_the_rollover_source():
    # Rollover compares like with like: Spring rolls from Spring, not Winter.
    assert TermId("2026-27", "spring").previous_year() == TermId("2025-26", "spring")
    assert TermId("2026-27", "winter").previous_year() == TermId("2025-26", "winter")


# ---- scoping ---------------------------------------------------------- #

def test_a_fresh_store_has_a_current_term(store):
    assert store.current_term() is not None
    assert store.list_terms()


def test_two_terms_hold_independent_catalogs(store):
    a = store.create_term("2025-26", "spring")
    b = store.create_term("2026-27", "spring")

    store.set_current_term(a)
    store.upsert_course(_course("00540315"))
    assert [c.number for c in store.list_courses()] == ["00540315"]

    store.set_current_term(b)
    assert store.list_courses() == []
    store.upsert_course(_course("00580310"))
    assert [c.number for c in store.list_courses()] == ["00580310"]

    store.set_current_term(a)
    assert [c.number for c in store.list_courses()] == ["00540315"]


def test_the_same_course_number_may_exist_in_two_terms(store):
    a = store.create_term("2025-26", "spring")
    b = store.create_term("2026-27", "spring")
    store.set_current_term(a)
    store.upsert_course(_course("00540315"))
    store.set_current_term(b)
    store.upsert_course(_course("00540315"))  # must not collide with term a's row
    store.set_current_term(a)
    assert len(store.list_courses()) == 1


def test_settings_are_term_scoped(store):
    a = store.create_term("2025-26", "spring")
    b = store.create_term("2026-27", "spring")
    store.set_current_term(a)
    store.set_setting("calendar", {"start": "2026-03-01"})
    store.set_current_term(b)
    assert store.get_setting("calendar") is None
    store.set_current_term(a)
    assert store.get_setting("calendar") == {"start": "2026-03-01"}


def test_global_settings_are_shared_across_terms(store):
    a = store.create_term("2025-26", "spring")
    b = store.create_term("2026-27", "spring")
    store.set_current_term(a)
    # The faculty registry is the department's staff, not a fact about one term.
    store.set_setting("people", [{"id": "dr_a", "name": "A", "kind": "faculty"}])
    store.set_current_term(b)
    assert store.get_setting("people") == [{"id": "dr_a", "name": "A", "kind": "faculty"}]
    assert "people" in GLOBAL_KEYS


def test_deleting_a_course_only_affects_its_own_term(store):
    a = store.create_term("2025-26", "spring")
    b = store.create_term("2026-27", "spring")
    for t in (a, b):
        store.set_current_term(t)
        store.upsert_course(_course("00540315"))
    store.delete_course("00540315")          # current term is b
    assert store.list_courses() == []
    store.set_current_term(a)
    assert len(store.list_courses()) == 1


def test_creating_a_duplicate_term_is_rejected(store):
    store.create_term("2025-26", "spring")
    with pytest.raises(ValueError):
        store.create_term("2025-26", "spring")


# ---- migration -------------------------------------------------------- #

def _legacy_db(path: str) -> None:
    """A database in the pre-term shape, as shipped before this change."""
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE courses (number TEXT PRIMARY KEY, data TEXT NOT NULL);
        CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    """)
    conn.execute("INSERT INTO courses VALUES (?, ?)",
                 ("00540315", '{"number": "00540315", "programs": ["ChemE"], '
                              '"year": 2, "role": "core", "lecture_boxes": 2}'))
    conn.execute("INSERT INTO settings VALUES (?, ?)",
                 ("calendar", '{"start": "2026-03-01"}'))
    conn.execute("INSERT INTO settings VALUES (?, ?)",
                 ("people", '[{"id": "dr_a", "name": "A", "kind": "faculty"}]'))
    conn.execute("INSERT INTO settings VALUES (?, ?)", ("saves_dir", '"/tmp/saves"'))
    conn.commit()
    conn.close()


def test_migration_preserves_courses_and_term_settings(tmp_path):
    path = str(tmp_path / "legacy.sqlite")
    _legacy_db(path)
    s = Store(path)
    assert [c.number for c in s.list_courses()] == ["00540315"]
    assert s.get_setting("calendar") == {"start": "2026-03-01"}
    s.close()


def test_migration_moves_global_settings_out_of_the_term(tmp_path):
    path = str(tmp_path / "legacy.sqlite")
    _legacy_db(path)
    s = Store(path)
    other = s.create_term("2027-28", "winter")
    s.set_current_term(other)
    # People and the saves folder belong to the machine, not to a semester.
    assert s.get_setting("people") == [{"id": "dr_a", "name": "A", "kind": "faculty"}]
    assert s.get_setting("saves_dir") == "/tmp/saves"
    assert s.get_setting("calendar") is None      # term-scoped, stayed behind
    s.close()


def test_migration_writes_a_timestamped_backup(tmp_path):
    path = str(tmp_path / "legacy.sqlite")
    _legacy_db(path)
    s = Store(path)
    backups = list(tmp_path.glob("legacy.sqlite.pre-terms-*.bak"))
    assert len(backups) == 1, "the only copy of the planner's work must be preserved"
    assert backups[0].stat().st_size > 0
    s.close()

    # The backup is a real database still holding the original rows.
    conn = sqlite3.connect(str(backups[0]))
    assert conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0] == 1
    conn.close()


def test_the_backup_is_a_consistent_snapshot_not_a_file_copy(tmp_path):
    """Taken through SQLite, so it holds whatever journal mode the file is in.

    A plain file copy captures the main database only. Under WAL the recent
    writes live in a side file, so the ``.bak`` would be a real database missing
    exactly the work most worth keeping — and it would say nothing about it.
    """
    path = str(tmp_path / "legacy.sqlite")
    _legacy_db(path)
    # The writer stays open across the migration: closing it would checkpoint
    # the WAL back into the main file and hide the very thing being tested.
    writer = sqlite3.connect(path)
    writer.execute("PRAGMA journal_mode=WAL")
    writer.execute("INSERT INTO courses VALUES (?, ?)",
                   ("00540316", '{"number": "00540316"}'))
    writer.commit()
    try:
        Store(path).close()
    finally:
        writer.close()
    backup = next(iter(tmp_path.glob("legacy.sqlite.pre-terms-*.bak")))
    # No stray WAL/journal beside the backup: it has to stand on its own, since
    # the planner will copy this one file somewhere safe.
    assert not list(tmp_path.glob("*.bak-wal")) and not list(tmp_path.glob("*.bak-journal"))
    conn = sqlite3.connect(str(backup))
    numbers = {r[0] for r in conn.execute("SELECT number FROM courses")}
    conn.close()
    assert numbers == {"00540315", "00540316"}, "the WAL-resident row is missing"


def test_migration_is_idempotent(tmp_path):
    path = str(tmp_path / "legacy.sqlite")
    _legacy_db(path)
    Store(path).close()
    s = Store(path)                              # second open must not re-migrate
    assert len(s.list_terms()) == 1
    assert [c.number for c in s.list_courses()] == ["00540315"]
    assert len(list(tmp_path.glob("*.bak"))) == 1
    s.close()


def test_migration_flags_its_guessed_name_for_confirmation(tmp_path):
    # Migration must name the term without being able to ask anyone, so it
    # records that the guess is unconfirmed.
    path = str(tmp_path / "legacy.sqlite")
    _legacy_db(path)
    s = Store(path)
    assert s.get_global("term_needs_naming") == s.current_term()
    s.close()


def test_renaming_a_term_carries_its_data_and_clears_the_flag(tmp_path):
    path = str(tmp_path / "legacy.sqlite")
    _legacy_db(path)
    s = Store(path)
    guessed = s.current_term()
    new = s.rename_term(guessed, "2024-25", "spring")
    assert new == "2024-25-spring"
    assert s.current_term() == new
    assert [c.number for c in s.list_courses()] == ["00540315"]
    assert s.get_setting("calendar") == {"start": "2026-03-01"}
    assert s.get_global("term_needs_naming") is None
    assert [t["id"] for t in s.list_terms()] == ["2024-25-spring"]
    s.close()


def test_renaming_onto_an_existing_term_is_rejected(tmp_path):
    s = Store(str(tmp_path / "t.sqlite"))
    a = s.create_term("2025-26", "spring")
    s.create_term("2026-27", "spring")
    with pytest.raises(ValueError):
        s.rename_term(a, "2026-27", "spring")
    s.close()


def test_a_failed_migration_leaves_the_database_untouched(tmp_path, monkeypatch):
    # The reshape is one transaction: a crash part-way must not consume the
    # planner's only copy of a semester's work.
    path = str(tmp_path / "legacy.sqlite")
    _legacy_db(path)

    # Fail *after* the course rows have been inserted — the case where a
    # non-transactional migration would leave the file half-rewritten.
    def explode(*_a, **_k):
        raise RuntimeError("simulated crash mid-migration")

    monkeypatch.setattr("schedy.store.json.dumps", explode)
    with pytest.raises(RuntimeError):
        Store(path)
    monkeypatch.undo()

    conn = sqlite3.connect(path)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(courses)")}
    assert "term_id" not in cols, "schema was reshaped despite the failure"
    assert conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0] == 1
    conn.close()


def test_a_fresh_database_is_not_backed_up(tmp_path):
    # Nothing to lose, so no backup clutter.
    path = str(tmp_path / "new.sqlite")
    Store(path).close()
    assert list(tmp_path.glob("*.bak")) == []
