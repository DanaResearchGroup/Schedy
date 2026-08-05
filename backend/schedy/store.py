"""Catalog Store — durable SQLite persistence for the catalog and settings.

Single-planner, local app: a tiny key/value-ish schema is plenty. Courses live in
their own table (keyed by course number); free-form settings (availability,
checklist, calendar) live as JSON in a settings table.

Everything the planner edits belongs to a **term** — an academic year plus a
semester, e.g. ``2026-27 Spring`` — because the department plans and publishes one
semester at a time and must be able to say which year a frozen schedule belongs
to. A handful of settings describe the machine or the department rather than a
semester (see ``GLOBAL_KEYS``) and are shared by every term.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass

from .catalog import Course
from .domain import CourseRole, Program

SEMESTERS = ("winter", "spring")

# Settings that are facts about the department or the machine, not about one
# semester. Everything else is term-scoped.
GLOBAL_KEYS = frozenset({"people", "saves_dir", "current_term"})

# The sentinel term for global settings. Empty string rather than NULL so it can
# sit in a composite primary key.
_GLOBAL = ""

_SCHEMA = """
CREATE TABLE IF NOT EXISTS terms (
    id        TEXT PRIMARY KEY,
    year      TEXT NOT NULL,
    semester  TEXT NOT NULL,
    created   TEXT NOT NULL,
    published TEXT
);
CREATE TABLE IF NOT EXISTS courses (
    term_id TEXT NOT NULL,
    number  TEXT NOT NULL,
    data    TEXT NOT NULL,
    PRIMARY KEY (term_id, number)
);
CREATE TABLE IF NOT EXISTS settings (
    term_id TEXT NOT NULL,
    key     TEXT NOT NULL,
    value   TEXT NOT NULL,
    PRIMARY KEY (term_id, key)
);
"""

_YEAR_RE = re.compile(r"^(\d{4})-(\d{2})$")


@dataclass(frozen=True)
class TermId:
    """An academic year plus a semester — the unit everything is scoped by."""

    year: str       # "2026-27"
    semester: str   # "winter" | "spring"

    def __post_init__(self) -> None:
        m = _YEAR_RE.match(self.year)
        if not m:
            raise ValueError(f"academic year must look like 2026-27, got {self.year!r}")
        if int(m.group(1)) % 100 != (int(m.group(2)) - 1) % 100:
            raise ValueError(f"{self.year!r} is not a consecutive academic year")
        if self.semester not in SEMESTERS:
            raise ValueError(f"semester must be one of {SEMESTERS}, got {self.semester!r}")

    def __str__(self) -> str:
        return f"{self.year}-{self.semester}"

    @classmethod
    def parse(cls, s: str) -> TermId:
        year, _, semester = str(s).rpartition("-")
        return cls(year, semester)

    def previous_year(self) -> TermId:
        """The same semester one year earlier — the rollover source.

        Spring rolls over from Spring, never from the Winter in between: the
        planner is comparing like with like.
        """
        start, end = (int(x) for x in _YEAR_RE.match(self.year).groups())
        return TermId(f"{start - 1}-{(end - 1) % 100:02d}", self.semester)


def course_to_dict(c: Course) -> dict:
    d = asdict(c)
    d["programs"] = [p.value for p in c.programs]
    d["role"] = c.role.value
    return d


def course_from_dict(d: dict) -> Course:
    d = dict(d)
    d["programs"] = [Program(p) for p in d.get("programs", [])]
    d["role"] = CourseRole(d.get("role", "core"))
    return Course(**d)


class Store:
    def __init__(self, path: str = "schedy.sqlite", term: str | TermId | None = None):
        # check_same_thread=False: the local FastAPI app serves requests from a
        # threadpool; a single planner means no real concurrency to guard against.
        self.path = path  # used to site the default saved-schedules folder
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._migrate_from_single_term()
        self.conn.executescript(_SCHEMA)
        self.conn.commit()
        self._term = str(term) if term else self._resolve_current_term()

    # ---- migration --------------------------------------------------- #
    def _migrate_from_single_term(self) -> None:
        """Stamp a pre-term database as its first term, once.

        The planner's only copy of a semester's work lives in this file, so the
        original is backed up before anything is rewritten. Idempotent: a database
        already carrying `term_id` is left alone.
        """
        cur = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='courses'")
        if not cur.fetchone():
            return  # brand new file — nothing to migrate, nothing to lose
        cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(courses)")}
        if "term_id" in cols:
            return  # already migrated

        self.conn.commit()
        backup = f"{self.path}.pre-terms-{time.strftime('%Y%m%d-%H%M%S')}.bak"
        # Through SQLite rather than a file copy. Copying the main file captures
        # only what has been checkpointed into it: under WAL the newest writes
        # sit in a side file, so the backup would be a perfectly valid database
        # missing exactly the work most worth keeping, and saying nothing about
        # it. `backup()` also takes its snapshot under a read lock, so it cannot
        # catch another process mid-write.
        dest = sqlite3.connect(backup)
        try:
            self.conn.backup(dest)
        finally:
            dest.close()

        legacy_courses = list(self.conn.execute("SELECT number, data FROM courses"))
        legacy_settings = list(self.conn.execute("SELECT key, value FROM settings"))
        term = str(self._guess_legacy_term(legacy_settings))

        # One transaction: either the whole reshape lands or the file is left
        # exactly as it was. `executescript` would force an implicit commit
        # mid-way, so every statement is issued individually.
        self.conn.isolation_level = None
        try:
            self.conn.execute("BEGIN")
            self.conn.execute("DROP TABLE courses")
            self.conn.execute("DROP TABLE settings")
            for stmt in filter(None, (s.strip() for s in _SCHEMA.split(";"))):
                self.conn.execute(stmt)
            self.conn.execute(
                "INSERT INTO terms(id, year, semester, created) VALUES(?, ?, ?, ?)",
                (term, TermId.parse(term).year, TermId.parse(term).semester,
                 time.strftime("%Y-%m-%d")))
            self.conn.executemany(
                "INSERT INTO courses(term_id, number, data) VALUES(?, ?, ?)",
                [(term, r["number"], r["data"]) for r in legacy_courses])
            self.conn.executemany(
                "INSERT INTO settings(term_id, key, value) VALUES(?, ?, ?)",
                [(_GLOBAL if r["key"] in GLOBAL_KEYS else term, r["key"], r["value"])
                 for r in legacy_settings])
            self.conn.execute(
                "INSERT INTO settings(term_id, key, value) VALUES(?, ?, ?)",
                (_GLOBAL, "current_term", json.dumps(term)))
            # The guess is a guess — record that the planner should confirm it.
            self.conn.execute(
                "INSERT INTO settings(term_id, key, value) VALUES(?, ?, ?)",
                (_GLOBAL, "term_needs_naming", json.dumps(term)))
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise
        finally:
            self.conn.isolation_level = ""

    @staticmethod
    def _guess_legacy_term(settings: list) -> TermId:
        """Name the migrated term from the stored calendar, else from today.

        A semester starting in the back half of the calendar year is Winter of
        the academic year that opens then; otherwise it is Spring of the academic
        year that opened the previous autumn.
        """
        start = None
        for row in settings:
            if row["key"] == "calendar":
                try:
                    start = json.loads(row["value"]).get("start")
                except (ValueError, AttributeError):
                    start = None
                break
        y, m = (int(start[:4]), int(start[5:7])) if start else (
            int(time.strftime("%Y")), int(time.strftime("%m")))
        if m >= 8:
            return TermId(f"{y}-{(y + 1) % 100:02d}", "winter")
        return TermId(f"{y - 1}-{y % 100:02d}", "spring")

    # ---- terms ------------------------------------------------------- #
    def _insert_term(self, term: str) -> None:
        t = TermId.parse(term)
        self.conn.execute(
            "INSERT INTO terms(id, year, semester, created) VALUES(?, ?, ?, ?)",
            (str(t), t.year, t.semester, time.strftime("%Y-%m-%d")))

    def _resolve_current_term(self) -> str:
        stored = self.get_global("current_term")
        if stored and self.conn.execute(
                "SELECT 1 FROM terms WHERE id=?", (stored,)).fetchone():
            return stored
        row = self.conn.execute("SELECT id FROM terms ORDER BY id").fetchone()
        if row:
            self.set_global("current_term", row["id"])
            return row["id"]
        guess = self._guess_legacy_term([])
        return self.create_term(guess.year, guess.semester)

    def create_term(self, year: str, semester: str) -> str:
        term = str(TermId(year, semester))
        if self.conn.execute("SELECT 1 FROM terms WHERE id=?", (term,)).fetchone():
            raise ValueError(f"term {term} already exists")
        self._insert_term(term)
        self.conn.commit()
        if not self.get_global("current_term"):
            self.set_global("current_term", term)
        return term

    def list_terms(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT id, year, semester, created, published FROM terms ORDER BY id")]

    def rename_term(self, old: str, year: str, semester: str) -> str:
        """Re-label a term, keeping all its data.

        Migration has to name the pre-term database without being able to ask
        anyone — it runs before there is a UI. This is how that guess gets
        corrected, so a wrong guess is an annoyance rather than a wrong record.
        """
        old, new = str(old), str(TermId(year, semester))
        if not self.conn.execute("SELECT 1 FROM terms WHERE id=?", (old,)).fetchone():
            raise KeyError(f"no such term {old}")
        if new != old and self.conn.execute(
                "SELECT 1 FROM terms WHERE id=?", (new,)).fetchone():
            raise ValueError(f"term {new} already exists")
        self.conn.execute("UPDATE terms SET id=?, year=?, semester=? WHERE id=?",
                          (new, year, semester, old))
        self.conn.execute("UPDATE courses SET term_id=? WHERE term_id=?", (new, old))
        self.conn.execute("UPDATE settings SET term_id=? WHERE term_id=?", (new, old))
        self.conn.commit()
        if self._term == old:
            self._term = new
            self.set_global("current_term", new)
        if self.get_global("term_needs_naming") == old:
            self.set_global("term_needs_naming", None)
        return new

    def current_term(self) -> str:
        return self._term

    def set_current_term(self, term: str) -> None:
        term = str(term)
        if not self.conn.execute("SELECT 1 FROM terms WHERE id=?", (term,)).fetchone():
            raise KeyError(f"no such term {term}")
        self._term = term
        self.set_global("current_term", term)

    # ---- courses ----------------------------------------------------- #
    def upsert_course(self, c: Course) -> None:
        self.conn.execute(
            "INSERT INTO courses(term_id, number, data) VALUES(?, ?, ?) "
            "ON CONFLICT(term_id, number) DO UPDATE SET data=excluded.data",
            (self._term, c.number, json.dumps(course_to_dict(c))),
        )
        self.conn.commit()

    def get_course(self, number: str) -> Course | None:
        row = self.conn.execute(
            "SELECT data FROM courses WHERE term_id=? AND number=?",
            (self._term, number)).fetchone()
        return course_from_dict(json.loads(row["data"])) if row else None

    def list_courses(self) -> list[Course]:
        rows = self.conn.execute(
            "SELECT data FROM courses WHERE term_id=? ORDER BY number",
            (self._term,)).fetchall()
        return [course_from_dict(json.loads(r["data"])) for r in rows]

    def delete_course(self, number: str) -> None:
        self.conn.execute("DELETE FROM courses WHERE term_id=? AND number=?",
                          (self._term, number))
        self.conn.commit()

    # ---- settings ---------------------------------------------------- #
    def _scope(self, key: str) -> str:
        return _GLOBAL if key in GLOBAL_KEYS else self._term

    def set_setting(self, key: str, value) -> None:
        self.conn.execute(
            "INSERT INTO settings(term_id, key, value) VALUES(?, ?, ?) "
            "ON CONFLICT(term_id, key) DO UPDATE SET value=excluded.value",
            (self._scope(key), key, json.dumps(value)),
        )
        self.conn.commit()

    def get_setting(self, key: str, default=None):
        row = self.conn.execute(
            "SELECT value FROM settings WHERE term_id=? AND key=?",
            (self._scope(key), key)).fetchone()
        return json.loads(row["value"]) if row else default

    def set_global(self, key: str, value) -> None:
        self.conn.execute(
            "INSERT INTO settings(term_id, key, value) VALUES(?, ?, ?) "
            "ON CONFLICT(term_id, key) DO UPDATE SET value=excluded.value",
            (_GLOBAL, key, json.dumps(value)),
        )
        self.conn.commit()

    def get_global(self, key: str, default=None):
        row = self.conn.execute(
            "SELECT value FROM settings WHERE term_id=? AND key=?",
            (_GLOBAL, key)).fetchone()
        return json.loads(row["value"]) if row else default

    # ---- reset ------------------------------------------------------- #
    def reset(self, keep_settings: Sequence[str] = ()) -> dict[str, int]:
        """Drop every course and setting **in the current term** — "start over".

        ``keep_settings`` names keys that survive: a machine preference such as
        the saved-schedules folder is not planning data. Returns what was
        removed, so the caller can report it. Other terms are untouched.
        """
        keep = tuple(keep_settings)
        where = f" AND key NOT IN ({','.join('?' * len(keep))})" if keep else ""
        courses = self.conn.execute(
            "SELECT COUNT(*) FROM courses WHERE term_id=?", (self._term,)).fetchone()[0]
        settings = self.conn.execute(
            "SELECT COUNT(*) FROM settings WHERE term_id=?" + where,
            (self._term, *keep)).fetchone()[0]
        self.conn.execute("DELETE FROM courses WHERE term_id=?", (self._term,))
        self.conn.execute("DELETE FROM settings WHERE term_id=?" + where,
                          (self._term, *keep))
        self.conn.commit()
        return {"courses": int(courses), "settings": int(settings)}

    def close(self) -> None:
        self.conn.close()
