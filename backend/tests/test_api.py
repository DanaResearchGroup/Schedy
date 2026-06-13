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


REAL_XLSX = os.path.join(os.path.dirname(__file__), "..", "..", "raw", "30.4.26.XLSX")


@pytest.mark.skipif(not os.path.exists(REAL_XLSX), reason="real skeleton not present")
def test_skeleton_upload_filters_to_catalog(client):
    # Catalog knows course 00940411 -> upload filters the skeleton to it.
    client.post("/catalog/courses", json={
        "number": "00940411", "programs": ["ChemE"], "year": 1, "role": "core",
        "lecture_boxes": 3,
    })
    with open(REAL_XLSX, "rb") as f:
        r = client.post("/skeleton/upload", files={"file": ("skeleton.xlsx", f)})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] > 0
    assert all(o["course_number"] == "00940411" for o in body["offered"])


@pytest.mark.skipif(not os.path.exists(REAL_XLSX), reason="real skeleton not present")
def test_skeleton_groups_drive_solve(client):
    # Catalog declares 1 exercise group; the skeleton offers several -> the solve
    # places the skeleton's actual groups (named SE0xx), not the declared count.
    client.post("/catalog/courses", json={
        "number": "00940411", "programs": ["ChemE"], "year": 1, "role": "core",
        "lecture_boxes": 3, "exercise_boxes": 2, "num_exercise_groups": 1,
    })
    with open(REAL_XLSX, "rb") as f:
        up = client.post("/skeleton/upload", files={"file": ("s.xlsx", f)}).json()
    assert up["count"] > 0
    # The real skeleton carries grid-aligned times, so rows are flagged pinnable.
    assert any(row.get("pinned") for row in up["offered"])

    r = client.post("/solve", json={"time_limit_s": 8}).json()
    assert r["solved"] is True
    ex_ids = [sid for sid, m in r["sessions"].items() if m["type"] == "exercise"]
    assert len(ex_ids) >= 2
    assert any("SE01" in sid for sid in ex_ids)  # real skeleton group codes
    # …and those timed exercises are pinned as hard fixed placements.
    assert any(m["fixed"] for sid, m in r["sessions"].items() if m["type"] == "exercise")


def test_solve_returns_session_metadata(client):
    client.post("/catalog/courses", json=_core("00540319", "dr_a"))
    r = client.post("/solve", json={"time_limit_s": 5}).json()
    assert "sessions" in r
    meta = r["sessions"]["00540319-lec"]
    assert meta["type"] == "lecture"
    assert meta["cohorts"] == ["ChemE Y2"]
    assert meta["role"] == "core"


def test_delete_course(client):
    client.post("/catalog/courses", json=_core("00540319", "dr_a"))
    assert client.delete("/catalog/courses/00540319").status_code == 200
    assert client.get("/catalog/courses").json() == []


def test_seed_catalog_loads_and_solves(client):
    assert client.get("/catalog/courses").json() == []
    r = client.post("/catalog/seed").json()
    assert r["seeded"] > 10
    courses = client.get("/catalog/courses").json()
    assert len(courses) == r["seeded"]
    # Seeding again without force is refused; with force it replaces cleanly.
    assert client.post("/catalog/seed").status_code == 409
    assert client.post("/catalog/seed", params={"force": "true"}).status_code == 200
    assert len(client.get("/catalog/courses").json()) == r["seeded"]

    # The demo catalog must actually solve so a first-run user sees a schedule.
    solved = client.post("/solve", json={"time_limit_s": 15}).json()
    assert solved["solved"], solved.get("status")
    assert len(solved["placements"]) > 15


def test_skeleton_time_fixes_session_in_solve(client):
    client.post("/catalog/courses", json=_core("00540319", "dr_a"))
    # Inject a skeleton offered row carrying a concrete day/time for an exercise.
    client.app.state.store.set_setting("offered_rows", [
        {"course_number": "00540319", "event_type": "exercise",
         "group_code": "SE011", "name_he": "", "name_en": "",
         "day": 2, "start_min": 11 * 60 + 30, "end_min": 12 * 60 + 30,
         "room": "", "package": "", "row": 1},
    ])
    r = client.post("/solve", json={"time_limit_s": 8}).json()
    assert r["solved"]
    sid = "00540319-ex-SE011"
    assert r["placements"][sid]["day"] == 2
    assert r["placements"][sid]["start_box"] == 3  # 11:30 -> box 3
    assert r["sessions"][sid]["fixed"] is True
    assert r["sessions"]["00540319-lec"]["fixed"] is False


def test_fixed_events_overlay(client):
    client.post("/catalog/seed")
    events = client.get("/fixed-events").json()
    kinds = {e["kind"] for e in events}
    assert "blackout" in kinds  # standing Wed-afternoon + Mon-seminar
    assert "external" in kinds  # the seeded Calculus wall
    wed = next(e for e in events if "Wed" in e["label"])
    assert wed["day"] == 3 and wed["start_box"] == 4 and wed["length_boxes"] == 2


def test_calendar_round_trips_and_analyzes(client):
    assert client.get("/calendar").json() == {}
    # Analyze before any calendar is a 404.
    assert client.get("/calendar/analyze").status_code == 404

    # A four-week semester (Sun 2026-03-01 .. Thu 2026-03-26) with one blocked
    # Sunday and a substitution making 2026-03-10 (Tue) run the Wednesday (3) template.
    cal = {
        "start": "2026-03-01", "end": "2026-03-26",
        "blocked_dates": ["2026-03-08"],
        "substitutions": {"2026-03-10": 3},
    }
    assert client.put("/calendar", json=cal).status_code == 200
    assert client.get("/calendar").json() == cal

    # Bad calendar is rejected.
    assert client.put("/calendar", json={"start": "nope", "end": "2026-03-26"}).status_code == 400

    a = client.get("/calendar/analyze").json()
    assert a["weeks"] == 4
    assert a["teaching_days"] > 0
    # Sunday (template 0) lost one teaching day to the block; Wednesday (3)
    # gained one from the substitution.
    assert a["template_counts"]["0"] == 3
    assert a["template_counts"]["3"] == 5
    assert {"date": "2026-03-10", "template": 3} in a["substituted_days"]
    # No solved schedule yet, so no per-session deficits.
    assert a["lost_sessions"] == []


def test_availability_round_trips_and_constrains_solve(client):
    # Empty before anything is stored.
    assert client.get("/availability").json() == {}

    client.post("/catalog/courses", json=_core("00540319", "dr_a"))
    # Block dr_a out of the entire first three days so the lecture must land Wed/Thu.
    blocked = [[d, box] for d in range(3) for box in range(10)]
    assert client.put("/availability", json={"dr_a": blocked}).status_code == 200
    assert client.get("/availability").json() == {"dr_a": blocked}

    r = client.post("/solve", json={"time_limit_s": 5}).json()
    assert r["solved"]
    assert r["placements"]["00540319-lec"]["day"] >= 3
