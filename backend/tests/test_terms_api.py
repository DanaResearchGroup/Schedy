"""The /terms API surface — the first place terms become visible to the planner.

M1 made the store term-scoped but exposed nothing: the app opened whichever term
the database happened to name and offered no way to see it, switch it, or correct
a name that migration had to guess. These tests pin that surface.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from schedy.api import create_app
from schedy.store import Store


@pytest.fixture()
def client(tmp_path):
    store = Store(str(tmp_path / "terms.sqlite"))
    app = create_app(store)
    with TestClient(app) as c:
        c.store = store
        yield c
    store.close()


def _course(number: str) -> dict:
    return {"number": number, "programs": ["ChemE"], "year": 2, "lecture_boxes": 2}


# ---- listing ---------------------------------------------------------- #

def test_lists_the_single_term_a_fresh_database_opens_with(client):
    body = client.get("/terms").json()
    assert len(body["terms"]) == 1
    only = body["terms"][0]
    assert body["current"] == only["id"]
    assert only["year"] and only["semester"] in ("winter", "spring")
    assert only["published"] is None


def test_a_fresh_database_needs_no_naming(client):
    # Only a migrated database carries a guessed name to confirm.
    assert client.get("/terms").json()["needs_naming"] is None


def test_lists_terms_in_chronological_order(client):
    client.post("/terms", json={"year": "2027-28", "semester": "winter"})
    client.post("/terms", json={"year": "2026-27", "semester": "spring"})
    ids = [t["id"] for t in client.get("/terms").json()["terms"]]
    assert ids == sorted(ids)


# ---- creating --------------------------------------------------------- #

def test_creates_a_term(client):
    r = client.post("/terms", json={"year": "2027-28", "semester": "spring"})
    assert r.status_code == 200
    assert r.json()["id"] == "2027-28-spring"
    assert len(client.get("/terms").json()["terms"]) == 2


def test_creating_a_term_does_not_switch_to_it(client):
    before = client.get("/terms").json()["current"]
    client.post("/terms", json={"year": "2027-28", "semester": "spring"})
    assert client.get("/terms").json()["current"] == before


def test_rejects_a_malformed_academic_year(client):
    r = client.post("/terms", json={"year": "2027-29", "semester": "spring"})
    assert r.status_code == 400


def test_rejects_an_unknown_semester(client):
    r = client.post("/terms", json={"year": "2027-28", "semester": "summer"})
    assert r.status_code == 400


def test_rejects_a_duplicate_term(client):
    client.post("/terms", json={"year": "2027-28", "semester": "spring"})
    r = client.post("/terms", json={"year": "2027-28", "semester": "spring"})
    assert r.status_code == 409


# ---- switching -------------------------------------------------------- #

def test_switching_term_changes_which_catalog_is_served(client):
    client.post("/catalog/courses", json=_course("00540001"))
    client.post("/terms", json={"year": "2027-28", "semester": "spring"})
    client.put("/terms/current", json={"term": "2027-28-spring"})

    assert client.get("/catalog/courses").json() == []      # a fresh, empty term
    client.put("/terms/current", json={"term": client.store.list_terms()[0]["id"]})
    assert len(client.get("/catalog/courses").json()) == 1   # and back again


def test_switching_term_survives_a_new_request(client):
    client.post("/terms", json={"year": "2027-28", "semester": "spring"})
    client.put("/terms/current", json={"term": "2027-28-spring"})
    assert client.get("/terms/current").json()["id"] == "2027-28-spring"


def test_switching_term_swaps_the_solved_schedule(client):
    # The whole point of terms: last year's frozen plan does not bleed into this
    # year's working one.
    client.store.set_setting("last_schedule", {"s1": {"day": 0, "start_box": 0,
                                                      "room_id": "H6"}})
    client.post("/terms", json={"year": "2027-28", "semester": "spring"})
    client.put("/terms/current", json={"term": "2027-28-spring"})
    assert client.get("/export/csv").status_code == 404      # nothing solved here


def test_current_is_a_switch_target_not_a_term_name(client):
    # `PUT /terms/current` must out-rank `PUT /terms/{term}`; declared in the
    # wrong order FastAPI reads "current" as a term to rename and 404s.
    client.post("/terms", json={"year": "2027-28", "semester": "spring"})
    r = client.put("/terms/current", json={"term": "2027-28-spring"})
    assert r.status_code == 200
    assert r.json()["id"] == "2027-28-spring"


def test_switching_to_an_unknown_term_is_a_404(client):
    r = client.put("/terms/current", json={"term": "2099-00-spring"})
    assert r.status_code == 404


def test_the_faculty_registry_is_shared_across_terms(client):
    # People are a fact about the department, not about one semester.
    client.put("/people", json={"items": [{"id": "dr_a", "name": "Dr A"}]})
    client.post("/terms", json={"year": "2027-28", "semester": "spring"})
    client.put("/terms/current", json={"term": "2027-28-spring"})
    assert [p["id"] for p in client.get("/people").json()] == ["dr_a"]


# ---- renaming --------------------------------------------------------- #

def test_renames_a_term_and_keeps_its_courses(client):
    client.post("/catalog/courses", json=_course("00540001"))
    current = client.get("/terms/current").json()["id"]

    r = client.put(f"/terms/{current}", json={"year": "2025-26", "semester": "winter"})
    assert r.status_code == 200
    assert r.json()["id"] == "2025-26-winter"

    assert client.get("/terms/current").json()["id"] == "2025-26-winter"
    assert len(client.get("/catalog/courses").json()) == 1


def test_renaming_onto_an_existing_term_is_a_409(client):
    client.post("/terms", json={"year": "2027-28", "semester": "spring"})
    current = client.get("/terms/current").json()["id"]
    r = client.put(f"/terms/{current}", json={"year": "2027-28", "semester": "spring"})
    assert r.status_code == 409


def test_renaming_an_unknown_term_is_a_404(client):
    r = client.put("/terms/2099-00-spring", json={"year": "2027-28", "semester": "spring"})
    assert r.status_code == 404


def test_renaming_to_a_malformed_year_is_a_400(client):
    current = client.get("/terms/current").json()["id"]
    r = client.put(f"/terms/{current}", json={"year": "2027", "semester": "spring"})
    assert r.status_code == 400


# ---- confirming a guessed name ---------------------------------------- #

def test_a_guessed_term_name_is_reported_until_it_is_confirmed(client):
    # Migration names the pre-term database without being able to ask anyone.
    client.store.set_global("term_needs_naming", client.store.current_term())
    assert client.get("/terms").json()["needs_naming"] == client.store.current_term()

    current = client.get("/terms/current").json()["id"]
    client.put(f"/terms/{current}", json={"year": "2025-26", "semester": "winter"})
    assert client.get("/terms").json()["needs_naming"] is None


def test_a_guessed_name_can_be_confirmed_unchanged(client):
    current = client.store.current_term()
    client.store.set_global("term_needs_naming", current)
    year, _, semester = current.rpartition("-")

    r = client.put(f"/terms/{current}", json={"year": year, "semester": semester})
    assert r.status_code == 200
    assert client.get("/terms").json()["needs_naming"] is None
