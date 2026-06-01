"""Catalog Store — durable SQLite persistence for the catalog and settings.

Single-planner, local app: a tiny key/value-ish schema is plenty. Courses live in
their own table (keyed by course number); free-form settings (availability,
checklist, calendar) live as JSON in a settings table.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict

from .catalog import Course
from .domain import CourseRole, Program

_SCHEMA = """
CREATE TABLE IF NOT EXISTS courses (
    number TEXT PRIMARY KEY,
    data   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


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
    def __init__(self, path: str = "schedy.sqlite"):
        # check_same_thread=False: the local FastAPI app serves requests from a
        # threadpool; a single planner means no real concurrency to guard against.
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    # ---- courses ---------------------------------------------------- #
    def upsert_course(self, c: Course) -> None:
        self.conn.execute(
            "INSERT INTO courses(number, data) VALUES(?, ?) "
            "ON CONFLICT(number) DO UPDATE SET data=excluded.data",
            (c.number, json.dumps(course_to_dict(c))),
        )
        self.conn.commit()

    def get_course(self, number: str) -> Course | None:
        row = self.conn.execute(
            "SELECT data FROM courses WHERE number=?", (number,)).fetchone()
        return course_from_dict(json.loads(row["data"])) if row else None

    def list_courses(self) -> list[Course]:
        rows = self.conn.execute("SELECT data FROM courses ORDER BY number").fetchall()
        return [course_from_dict(json.loads(r["data"])) for r in rows]

    def delete_course(self, number: str) -> None:
        self.conn.execute("DELETE FROM courses WHERE number=?", (number,))
        self.conn.commit()

    # ---- settings --------------------------------------------------- #
    def set_setting(self, key: str, value) -> None:
        self.conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(value)),
        )
        self.conn.commit()

    def get_setting(self, key: str, default=None):
        row = self.conn.execute(
            "SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(row["value"]) if row else default

    def close(self) -> None:
        self.conn.close()
