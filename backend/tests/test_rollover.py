"""Rollover: last year's graduate courses become this year's reservations.

The department publishes the undergraduate week months before it knows which
graduate courses will run. Phase 1 therefore places last year's graduate courses
as *provisional* stand-ins, so the hours they will need are genuinely defended
against joint courses rather than merely hoped for. Phase 2 replaces the guess
with the truth.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from schedy.catalog import Cadence, Course, expand
from schedy.domain import Program
from schedy.api import create_app
from schedy.store import Store, TermId


@pytest.fixture()
def client(tmp_path):
    store = Store(str(tmp_path / "roll.sqlite"), term="2026-27-spring")
    store.create_term("2026-27", "spring")
    store.set_current_term("2026-27-spring")
    app = create_app(store)
    with TestClient(app) as c:
        c.store = store
        yield c
    store.close()


def _grad(number: str, **kw) -> dict:
    return {"number": number, "programs": [], "year": 0, "lecture_boxes": 2,
            "expected_enrollment": 15, **kw}


def _seed_last_year(client, *courses: dict) -> None:
    """Put courses in the same semester one year back, then come back."""
    here = client.get("/terms/current").json()["id"]
    prev = str(TermId.parse(here).previous_year())
    client.post("/terms", json={"year": prev.rpartition("-")[0],
                                "semester": prev.rpartition("-")[2]})
    client.put("/terms/current", json={"term": prev})
    for c in courses:
        client.post("/catalog/courses", json=c)
    client.put("/terms/current", json={"term": here})


# ---- a graduate course has no cohort ---------------------------------- #

def test_a_graduate_course_without_a_programme_still_expands_and_solves():
    # D4: a graduate student is not "ChemE Y2". Their protection is the level
    # rule, not a cohort.
    c = Course(number="00580001", programs=[], year=0, lecture_boxes=2)
    problem = expand([c])
    assert problem.sessions[0].cohorts == frozenset()


def test_a_cohortless_graduate_course_never_double_books_a_cohort(client):
    client.post("/catalog/courses", json={
        "number": "00540001", "programs": ["ChemE"], "year": 2, "lecture_boxes": 2})
    client.post("/catalog/courses", json=_grad("00580001"))
    r = client.post("/solve", json={"time_limit_s": 5}).json()
    assert r["solved"]
    assert not [v for v in r["violations"] if v["kind"] == "cohort_double_booked"]


# ---- cadence ----------------------------------------------------------- #

def test_a_course_runs_every_year_unless_told_otherwise():
    assert Course(number="00580001").cadence is Cadence.ANNUAL


def test_cadence_survives_a_round_trip_through_the_store(client):
    client.post("/catalog/courses", json=_grad("00580001", cadence="biennial"))
    assert client.get("/catalog/courses").json()[0]["cadence"] == "biennial"


def test_a_course_stored_before_cadence_existed_reads_as_annual(client):
    client.store.conn.execute(
        "INSERT INTO courses(term_id, number, data) VALUES(?, ?, ?)",
        (client.store.current_term(), "00580009",
         '{"number": "00580009", "programs": [], "year": 0, "role": "core"}'))
    client.store.conn.commit()
    got = next(c for c in client.get("/catalog/courses").json()
               if c["number"] == "00580009")
    assert got["cadence"] == "annual"


# ---- what rollover offers ---------------------------------------------- #

def test_offers_last_years_graduate_courses(client):
    _seed_last_year(client, _grad("00580001"), _grad("00580002"))
    body = client.get("/terms/current/rollover").json()
    assert [c["number"] for c in body["courses"]] == ["00580001", "00580002"]
    assert body["source"] == "2025-26-spring"


def test_offers_the_same_semester_a_year_back_not_the_one_in_between(client):
    # Spring rolls over from Spring: the planner is comparing like with like.
    assert client.get("/terms/current/rollover").json()["source"] == "2025-26-spring"


def test_does_not_offer_undergraduate_courses(client):
    _seed_last_year(client, _grad("00580001"),
                    {"number": "00540001", "programs": ["ChemE"], "year": 2,
                     "lecture_boxes": 2})
    body = client.get("/terms/current/rollover").json()
    assert [c["number"] for c in body["courses"]] == ["00580001"]


def test_offers_joint_courses_too(client):
    # A joint course is half a graduate course; it needs a reservation as much.
    _seed_last_year(client, _grad("00560001"))
    body = client.get("/terms/current/rollover").json()
    assert [c["number"] for c in body["courses"]] == ["00560001"]


def test_an_annual_course_that_ran_last_year_is_due(client):
    _seed_last_year(client, _grad("00580001"))
    course = client.get("/terms/current/rollover").json()["courses"][0]
    assert course["due"] is True


def test_a_biennial_course_that_ran_last_year_is_not_due(client):
    # It ran last year, so this is its off year — do not hold a slot for it.
    _seed_last_year(client, _grad("00580001", cadence="biennial"))
    course = client.get("/terms/current/rollover").json()["courses"][0]
    assert course["due"] is False


def test_a_biennial_course_that_ran_two_years_ago_is_due(client):
    here = client.get("/terms/current").json()["id"]
    two_back = str(TermId.parse(here).previous_year().previous_year())
    client.post("/terms", json={"year": two_back.rpartition("-")[0],
                                "semester": "spring"})
    client.put("/terms/current", json={"term": two_back})
    client.post("/catalog/courses", json=_grad("00580001", cadence="biennial"))
    client.put("/terms/current", json={"term": here})

    body = client.get("/terms/current/rollover").json()
    assert [c["number"] for c in body["courses"]] == ["00580001"]
    assert body["courses"][0]["due"] is True
    assert body["courses"][0]["last_run"] == two_back


def test_a_course_that_sat_out_last_year_is_not_offered_from_that_year(client):
    # `offered=false` means it did not run, so it is no evidence of anything.
    _seed_last_year(client, _grad("00580001", offered=False))
    assert client.get("/terms/current/rollover").json()["courses"] == []


def test_a_course_already_in_this_term_is_not_offered_again(client):
    _seed_last_year(client, _grad("00580001"))
    client.post("/catalog/courses", json=_grad("00580001"))
    assert client.get("/terms/current/rollover").json()["courses"] == []


def test_rollover_from_a_year_with_no_data_offers_nothing(client):
    assert client.get("/terms/current/rollover").json()["courses"] == []


# ---- availability carries over (D6) ------------------------------------ #

def test_a_new_term_pre_fills_availability_from_the_same_semester_last_year(client):
    # A lecturer's commitments are usually stable but not permanent, so the new
    # term gets its own editable copy rather than sharing one.
    client.put("/terms/current", json={"term": client.get("/terms").json()["current"]})
    client.put("/availability", json={"dr_a": [[0, 0]]})

    nxt = str(TermId.parse(client.get("/terms/current").json()["id"]))
    year, _, semester = nxt.rpartition("-")
    later = f"{int(year[:4]) + 1}-{(int(year[:4]) + 2) % 100:02d}"
    client.post("/terms", json={"year": later, "semester": semester})
    client.put("/terms/current", json={"term": f"{later}-{semester}"})

    assert client.get("/availability").json() == {"dr_a": [[0, 0]]}


def test_editing_the_new_terms_availability_leaves_last_years_alone(client):
    here = client.get("/terms/current").json()["id"]
    client.put("/availability", json={"dr_a": [[0, 0]]})
    client.post("/terms", json={"year": "2027-28", "semester": "spring"})
    client.put("/terms/current", json={"term": "2027-28-spring"})

    client.put("/availability", json={"dr_a": [[3, 3]]})
    client.put("/terms/current", json={"term": here})
    assert client.get("/availability").json() == {"dr_a": [[0, 0]]}


def test_a_new_term_with_no_previous_year_starts_empty(client):
    client.post("/terms", json={"year": "2040-41", "semester": "winter"})
    client.put("/terms/current", json={"term": "2040-41-winter"})
    assert client.get("/availability").json() == {}


# ---- what rollover does ------------------------------------------------ #

def test_copies_the_chosen_courses_in_as_provisional(client):
    _seed_last_year(client, _grad("00580001"), _grad("00580002"))
    r = client.post("/terms/current/rollover", json={"numbers": ["00580001"]})
    assert r.status_code == 200

    got = client.get("/catalog/courses").json()
    assert [c["number"] for c in got] == ["00580001"]
    assert got[0]["provisional"] is True


def test_a_provisional_course_holds_its_hours_in_phase_one(client):
    # The whole point: a joint course must be pushed out of the reserved slot,
    # exactly as the real graduate course would push it out.
    _seed_last_year(client, _grad("00580001"))
    client.post("/terms/current/rollover", json={"numbers": ["00580001"]})
    client.post("/catalog/courses", json=_grad("00560001"))

    r = client.post("/solve", json={"time_limit_s": 10}).json()
    assert r["solved"]
    grad = r["placements"]["00580001-lec"]
    joint = r["placements"]["00560001-lec"]
    assert (grad["day"], grad["start_box"]) != (joint["day"], joint["start_box"])


def test_rolling_over_twice_does_not_duplicate(client):
    _seed_last_year(client, _grad("00580001"))
    client.post("/terms/current/rollover", json={"numbers": ["00580001"]})
    client.post("/terms/current/rollover", json={"numbers": ["00580001"]})
    assert len(client.get("/catalog/courses").json()) == 1


def test_rollover_does_not_touch_the_source_term(client):
    _seed_last_year(client, _grad("00580001"))
    client.post("/terms/current/rollover", json={"numbers": ["00580001"]})

    client.put("/terms/current", json={"term": "2025-26-spring"})
    assert client.get("/catalog/courses").json()[0]["provisional"] is False


def test_rolling_over_an_unknown_number_is_a_400(client):
    _seed_last_year(client, _grad("00580001"))
    r = client.post("/terms/current/rollover", json={"numbers": ["00589999"]})
    assert r.status_code == 400


def test_a_provisional_course_can_be_confirmed(client):
    # Phase 2: the planner replaces the guess with the truth.
    _seed_last_year(client, _grad("00580001"))
    client.post("/terms/current/rollover", json={"numbers": ["00580001"]})

    got = client.get("/catalog/courses").json()[0]
    client.post("/catalog/courses", json={**got, "provisional": False})
    assert client.get("/catalog/courses").json()[0]["provisional"] is False
