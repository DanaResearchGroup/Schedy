"""End-to-end API integration tests over the FastAPI layer."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from schedy.api import create_app
from schedy.store import Store


@pytest.fixture()
def client(tmp_path):
    store = Store(str(tmp_path / "test.sqlite"))
    app = create_app(store)
    with TestClient(app) as c:
        yield c
    store.close()


def _core(number, lecturer):
    return {
        "number": number, "programs": ["ChemE"], "year": 2, "role": "core",
        "lecture_boxes": 2, "expected_enrollment": 40,
        "lecturer_ids": [lecturer],
    }


def test_health_empty(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "courses": 0}


def test_serves_built_spa_when_present(tmp_path):
    # A built SPA in SCHEDY_STATIC is served at "/" while API routes still win.
    static = tmp_path / "dist"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html><title>Schedy</title>")
    os.environ["SCHEDY_STATIC"] = str(static)
    try:
        store = Store(str(tmp_path / "spa.sqlite"))
        with TestClient(create_app(store)) as c:
            assert c.get("/health").json()["status"] == "ok"   # API still wins
            root = c.get("/")
            assert root.status_code == 200
            assert "Schedy" in root.text                        # SPA served
        store.close()
    finally:
        del os.environ["SCHEDY_STATIC"]


def test_full_pipeline_catalog_solve_export(client):
    # Two cohort-clashing core courses -> solver must separate them.
    assert client.post("/catalog/courses", json=_core("00540319", "dr_a")).status_code == 200
    assert client.post("/catalog/courses", json=_core("00540320", "dr_b")).status_code == 200
    assert len(client.get("/catalog/courses").json()) == 2

    solved = client.post("/solve", json={"time_limit_s": 5}).json()
    assert solved["solved"] is True
    assert solved["feasible"] is True
    assert set(solved["placements"]) == {"00540319-lec", "00540320-lec"}

    csv = client.get("/export/csv")
    assert csv.status_code == 200
    assert "00540319" in csv.text and "00540320" in csv.text

    pdf = client.get("/export/pdf")
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF"


def test_export_before_solve_is_404(client):
    assert client.get("/export/csv").status_code == 404


def test_skeleton_validate_reports_missing(client):
    header = ["מקצוע", "תיאור חבילת רישום", "סוג אירוע D", "ראשון"]
    rows = [["00540319", "SE011", "תרגול", "09:30-10:30"]]
    payload = {
        "header": header, "rows": rows,
        "checklist": [
            {"course_number": "00540319", "event_type": "lecture", "label": "Thermo lecture"},
        ],
    }
    r = client.post("/skeleton/validate", json=payload).json()
    assert r["ok"] is False
    assert r["missing"] == ["Thermo lecture"]


def test_evaluate_live_revalidation(client):
    # Two cohort-clashing cores. Overlap them by hand -> hard violation; then
    # move one off the overlap -> feasible.
    client.post("/catalog/courses", json=_core("00540319", "dr_a"))
    client.post("/catalog/courses", json=_core("00540320", "dr_b"))

    overlap = {"placements": {
        "00540319-lec": {"day": 0, "start_box": 0, "room_id": "hall1"},
        "00540320-lec": {"day": 0, "start_box": 0, "room_id": "hall6"},
    }}
    r = client.post("/evaluate", json=overlap).json()
    assert r["feasible"] is False
    assert any(v["kind"] == "cohort_double_booked" for v in r["violations"])

    moved = {"placements": {
        "00540319-lec": {"day": 0, "start_box": 0, "room_id": "hall1"},
        "00540320-lec": {"day": 1, "start_box": 0, "room_id": "hall6"},
    }}
    r2 = client.post("/evaluate", json=moved).json()
    assert r2["feasible"] is True
    # The edit is persisted, so export now works without a fresh solve.
    assert client.get("/export/csv").status_code == 200


def test_delete_course(client):
    client.post("/catalog/courses", json=_core("00540319", "dr_a"))
    assert client.delete("/catalog/courses/00540319").status_code == 200
    assert client.get("/catalog/courses").json() == []
