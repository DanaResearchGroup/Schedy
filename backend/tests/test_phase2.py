"""Phase 2: appending graduate courses to a published week.

Months after the undergraduate timetable was released, the department learns
which graduate courses will actually run. They are placed around what was
published — never through it.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from schedy.api import create_app
from schedy.store import Store


@pytest.fixture()
def client(tmp_path):
    store = Store(str(tmp_path / "p2.sqlite"))
    app = create_app(store)
    with TestClient(app) as c:
        c.store = store
        yield c
    store.close()


def _ug(number: str, **kw) -> dict:
    return {"number": number, "programs": ["ChemE"], "year": 2,
            "lecture_boxes": 2, "expected_enrollment": 30, **kw}


def _grad(number: str, **kw) -> dict:
    return {"number": number, "programs": [], "year": 0, "lecture_boxes": 2,
            "expected_enrollment": 15, **kw}


def _publish(client):
    assert client.post("/solve", json={"time_limit_s": 5}).json()["solved"]
    term = client.get("/terms/current").json()["id"]
    r = client.post(f"/terms/{term}/publish", params={"confirm": True})
    assert r.status_code == 200, r.text
    return r.json()


# ---- when phase 2 may run ---------------------------------------------- #

def test_phase_two_needs_a_published_term(client):
    client.post("/catalog/courses", json=_ug("00540001"))
    client.post("/solve", json={"time_limit_s": 5})
    r = client.post("/solve/grad", json={"time_limit_s": 5})
    assert r.status_code == 409
    assert "publish" in r.text.lower()


def test_phase_two_runs_once_the_term_is_published(client):
    client.post("/catalog/courses", json=_ug("00540001"))
    _publish(client)
    r = client.post("/solve/grad", json={"time_limit_s": 5})
    assert r.status_code == 200 and r.json()["solved"]


# ---- what phase 2 must not disturb -------------------------------------- #

def test_nothing_published_moves(client):
    client.post("/catalog/courses", json=_ug("00540001"))
    client.post("/catalog/courses", json=_ug("00540002"))
    _publish(client)
    before = client.store.get_setting("published_schedule")

    client.post("/catalog/courses", json=_grad("00580001"))
    after = client.post("/solve/grad", json={"time_limit_s": 10}).json()["placements"]
    for sid, p in before.items():
        assert after[sid] == p, f"{sid} moved in phase 2"


def test_a_graduate_course_added_in_phase_two_is_placed(client):
    client.post("/catalog/courses", json=_ug("00540001"))
    _publish(client)

    client.post("/catalog/courses", json=_grad("00580001"))
    r = client.post("/solve/grad", json={"time_limit_s": 10}).json()
    assert "00580001-lec" in r["placements"]


def test_graduate_courses_still_may_not_overlap_each_other(client):
    client.post("/catalog/courses", json=_ug("00540001"))
    _publish(client)

    client.post("/catalog/courses", json=_grad("00580001"))
    client.post("/catalog/courses", json=_grad("00580002"))
    r = client.post("/solve/grad", json={"time_limit_s": 10}).json()
    a, b = r["placements"]["00580001-lec"], r["placements"]["00580002-lec"]
    assert (a["day"], a["start_box"]) != (b["day"], b["start_box"])
    assert not [v for v in r["violations"] if v["severity"] == "hard"]


# ---- what phase 2 reports ---------------------------------------------- #

def test_reports_which_sessions_it_placed(client):
    client.post("/catalog/courses", json=_ug("00540001"))
    _publish(client)
    client.post("/catalog/courses", json=_grad("00580001"))

    r = client.post("/solve/grad", json={"time_limit_s": 10}).json()
    assert r["appended"] == ["00580001-lec"]


def test_reports_nothing_appended_when_there_are_no_graduate_courses(client):
    client.post("/catalog/courses", json=_ug("00540001"))
    _publish(client)
    assert client.post("/solve/grad", json={"time_limit_s": 5}).json()["appended"] == []


def test_an_unplaceable_graduate_course_leaves_the_published_week_intact(client):
    # The published week is the promise; a graduate course that will not fit is
    # the planner's problem to solve, not a reason to unpick it.
    client.post("/catalog/courses", json=_ug("00540001"))
    _publish(client)
    before = client.store.get_setting("published_schedule")

    # Unavailable every hour of every day: there is nowhere to put it.
    client.post("/catalog/courses", json=_grad("00580001", lecturer_ids=["ghost"]))
    client.put("/availability", json={
        "ghost": [[d, b] for d in range(5) for b in range(10)]})

    r = client.post("/solve/grad", json={"time_limit_s": 10}).json()
    assert not r["solved"]
    assert client.store.get_setting("published_schedule") == before
    assert client.store.get_setting("last_schedule") == before


# ---- provisional stand-ins --------------------------------------------- #

def test_a_provisional_reservation_does_not_block_the_course_it_stands_for(client):
    # The reservation is a guess about this same course; confirming it must not
    # make it clash with itself.
    client.post("/catalog/courses", json=_ug("00540001"))
    client.post("/catalog/courses", json=_grad("00580001", provisional=True))
    _publish(client)

    got = next(c for c in client.get("/catalog/courses").json()
               if c["number"] == "00580001")
    client.post("/catalog/courses", json={**got, "provisional": False})

    r = client.post("/solve/grad", json={"time_limit_s": 10}).json()
    assert r["solved"]
    assert not [v for v in r["violations"] if v["severity"] == "hard"]


def test_dropping_a_provisional_course_frees_its_hours(client):
    client.post("/catalog/courses", json=_ug("00540001"))
    client.post("/catalog/courses", json=_grad("00580001", provisional=True))
    _publish(client)

    client.delete("/catalog/courses/00580001")
    r = client.post("/solve/grad", json={"time_limit_s": 10}).json()
    assert r["solved"]
    assert "00580001-lec" not in r["placements"]
