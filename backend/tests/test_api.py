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
    # Excel-friendly: UTF-8 BOM so Hebrew renders, and a download filename.
    assert csv.content[:3] == b"\xef\xbb\xbf"
    assert "filename=" in csv.headers.get("content-disposition", "")

    pdf = client.get("/export/pdf")
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF"


def test_export_before_solve_is_404(client):
    assert client.get("/export/csv").status_code == 404


def test_credit_persists_through_upsert(client):
    course = _core("00540319", "dr_a")
    course["credit"] = 2.5
    assert client.post("/catalog/courses", json=course).status_code == 200
    got = {c["number"]: c for c in client.get("/catalog/courses").json()}
    assert got["00540319"]["credit"] == 2.5


def test_export_after_deleting_a_solved_course_does_not_500(client):
    # Solve with two courses, then delete one. The last-schedule setting still
    # holds a placement for the removed session; the export path must ignore
    # that stale id rather than crash with a 500.
    client.post("/catalog/courses", json=_core("00540319", "dr_a"))
    client.post("/catalog/courses", json=_core("00540320", "dr_b"))
    solved = client.post("/solve", json={"time_limit_s": 5})
    assert solved.json()["solved"] is True

    deleted = client.delete("/catalog/courses/00540319")
    assert deleted.status_code == 200

    csv = client.get("/export/csv")
    assert csv.status_code == 200
    assert "00540320" in csv.text          # the survivor still exports
    assert "00540319" not in csv.text      # the deleted course is gone
    assert client.get("/export/pdf").status_code == 200


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

# The committed example pair (examples/README.md documents them). Unlike the real
# skeleton these ship with the repo, so tests over them always run.
_EXAMPLES = os.path.join(os.path.dirname(__file__), "..", "..", "examples")
EXAMPLE_SKELETON = os.path.join(_EXAMPLES, "skeleton-example.xlsx")
EXAMPLE_INTEREST = os.path.join(_EXAMPLES, "courses-of-interest.csv")


def _upload(client, url, path, name):
    with open(path, "rb") as fh:
        return client.post(url, files={"file": (name, fh.read())})


def test_people_registry_roundtrip_and_import(client):
    client.post("/catalog/courses", json={
        **_core("00540319", "prof_levi"), "ta_ids": ["ta_adi"],
    })
    assert client.get("/people").json() == []
    # Import from the catalog: lecturers -> faculty, TAs -> grad.
    imported = client.post("/people/import-from-catalog").json()
    by_id = {p["id"]: p for p in imported}
    assert by_id["prof_levi"]["kind"] == "faculty"
    assert by_id["ta_adi"]["kind"] == "grad"
    # Add a manual person (no id -> derived) and persist.
    saved = client.put("/people", json={
        "items": imported + [{"name": "Dana Cohen", "kind": "grad"}],
    }).json()
    manual = next(p for p in saved if p["name"] == "Dana Cohen")
    assert manual["id"] and manual["kind"] == "grad"
    assert client.get("/people").json() == saved


def test_courses_of_interest_roundtrip(client):
    assert client.get("/courses-of-interest").json() == []
    items = [{"number": "00540319", "name": "Thermo"}, {"number": "01250300", "name": ""}]
    client.put("/courses-of-interest", json={"items": items})
    assert client.get("/courses-of-interest").json() == items


def test_courses_of_interest_template_export_and_import(client):
    tmpl = client.get("/courses-of-interest/template.csv")
    assert tmpl.status_code == 200
    assert tmpl.content.startswith(b"\xef\xbb\xbf")     # BOM, so Excel reads Hebrew
    assert "attachment" in tmpl.headers["content-disposition"]

    r = client.post("/courses-of-interest/import",
                    files={"file": ("list.csv", tmpl.content, "text/csv")})
    assert r.status_code == 200
    assert len(r.json()) == 3
    assert client.get("/courses-of-interest").json() == r.json()

    # Exporting gives back a file our own importer reads to the same list.
    exp = client.get("/courses-of-interest/export.csv")
    again = client.post("/courses-of-interest/import",
                        files={"file": ("list.csv", exp.content, "text/csv")})
    assert again.json() == r.json()


def test_courses_of_interest_import_accepts_a_bare_list(client):
    r = client.post("/courses-of-interest/import",
                    files={"file": ("list.csv", b"00540315\n00540319\n", "text/csv")})
    assert [it["number"] for it in r.json()] == ["00540315", "00540319"]


def test_courses_of_interest_import_restores_stripped_zeros(client):
    """A list that has been through Excel must still match the skeleton."""
    r = client.post("/courses-of-interest/import",
                    files={"file": ("list.csv", b"number\n540315\n", "text/csv")})
    assert [it["number"] for it in r.json()] == ["00540315"]


def test_courses_of_interest_import_explains_a_legacy_xls(client):
    ole2 = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 512
    r = client.post("/courses-of-interest/import",
                    files={"file": ("list.xls", ole2, "application/vnd.ms-excel")})
    assert r.status_code == 400
    assert "Save As" in r.json()["detail"]      # not "File is not a zip file"


def test_courses_of_interest_import_rejects_an_empty_file(client):
    client.put("/courses-of-interest", json={"items": [{"number": "00540319"}]})
    r = client.post("/courses-of-interest/import",
                    files={"file": ("list.csv", b"number,name\n", "text/csv")})
    assert r.status_code == 400
    # The existing list is left alone rather than silently emptied.
    assert client.get("/courses-of-interest").json() == [
        {"number": "00540319", "name": ""}]


def test_example_files_filter_the_skeleton_as_documented(client):
    """The pair shipped in examples/ must behave the way its README says."""
    coi = _upload(client, "/courses-of-interest/import",
                  EXAMPLE_INTEREST, "courses-of-interest.csv")
    assert [it["number"] for it in coi.json()] == ["00540315", "00540319", "01040031"]

    body = _upload(client, "/skeleton/upload",
                   EXAMPLE_SKELETON, "skeleton-example.xlsx").json()
    assert body["count"] == 6
    kept = {o["course_number"] for o in body["offered"]}
    assert kept == {"00540315", "00540319", "01040031"}
    # The two courses off the list are gone; the whole file had five.
    assert set(client.get("/skeleton/course-numbers").json()["numbers"]) == kept | {
        "00940411", "02340114"}

    lecture = next(o for o in body["offered"]
                   if o["course_number"] == "00540315" and o["event_type"] == "lecture")
    assert lecture["details"]["building"] == "בניין הנדסה כימית"
    assert lecture["details"]["exam_a_date"] == "2026-02-11"
    assert lecture["person"] == "מרצה א׳"
    assert lecture["pinned"] is True

    # 01040031 starts at 09:00 — off the grid, so it imports unanchored.
    calculus = next(o for o in body["offered"] if o["course_number"] == "01040031")
    assert calculus["pinned"] is False


@pytest.mark.skipif(not os.path.exists(REAL_XLSX), reason="real skeleton not present")
def test_skeleton_course_numbers_are_unfiltered(client):
    # The check must see the FULL university-wide skeleton, not just our catalog.
    client.post("/catalog/courses", json=_core("00540319", "dr_a"))
    assert client.get("/skeleton/course-numbers").json()["imported"] is False
    with open(REAL_XLSX, "rb") as f:
        client.post("/skeleton/upload", files={"file": ("s.xlsx", f)})
    cn = client.get("/skeleton/course-numbers").json()
    assert cn["imported"] is True
    # many courses present even though our catalog has just one
    assert len(cn["numbers"]) > 5
    # clearing the import forgets the skeleton entirely
    client.delete("/skeleton/rows")
    assert client.get("/skeleton/course-numbers").json()["imported"] is False


@pytest.mark.skipif(not os.path.exists(REAL_XLSX), reason="real skeleton not present")
def test_skeleton_upload_filters_to_courses_of_interest(client):
    # The interest list — not the catalog — decides what survives the import.
    client.put("/courses-of-interest",
               json={"items": [{"number": "00940411", "name": ""}]})
    with open(REAL_XLSX, "rb") as f:
        r = client.post("/skeleton/upload", files={"file": ("skeleton.xlsx", f)})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] > 0
    assert all(o["course_number"] == "00940411" for o in body["offered"])
    assert "warning" not in body


@pytest.mark.skipif(not os.path.exists(REAL_XLSX), reason="real skeleton not present")
def test_a_catalog_course_off_the_interest_list_is_not_imported(client):
    """The catalog no longer widens the import; only the list does."""
    client.post("/catalog/courses", json={
        "number": "00940411", "programs": ["ChemE"], "year": 1, "role": "core",
        "lecture_boxes": 3,
    })
    client.put("/courses-of-interest",
               json={"items": [{"number": "00540319", "name": ""}]})
    with open(REAL_XLSX, "rb") as f:
        body = client.post("/skeleton/upload", files={"file": ("s.xlsx", f)}).json()
    assert all(o["course_number"] != "00940411" for o in body["offered"])


@pytest.mark.skipif(not os.path.exists(REAL_XLSX), reason="real skeleton not present")
def test_skeleton_upload_without_an_interest_list_keeps_nothing(client):
    # Not an error: the file parsed and its course numbers are remembered, but
    # nothing yet says which of them we care about, so nothing is kept.
    client.post("/catalog/courses", json={
        "number": "00940411", "programs": ["ChemE"], "year": 1, "role": "core",
        "lecture_boxes": 3,
    })
    with open(REAL_XLSX, "rb") as f:
        r = client.post("/skeleton/upload", files={"file": ("s.xlsx", f)})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 0
    assert body["offered"] == []
    assert body["warning"] == "no_courses_of_interest"
    # The university-wide numbers are still stored, so the checklist works.
    assert client.get("/skeleton/course-numbers").json()["imported"] is True


@pytest.mark.skipif(not os.path.exists(REAL_XLSX), reason="real skeleton not present")
def test_skeleton_upload_keeps_the_whole_record(client):
    client.put("/courses-of-interest",
               json={"items": [{"number": "00940411", "name": ""}]})
    with open(REAL_XLSX, "rb") as f:
        body = client.post("/skeleton/upload", files={"file": ("s.xlsx", f)}).json()
    row = body["offered"][0]
    for key in ("faculty", "language", "person", "details"):
        assert key in row
    assert row["details"]["weekly_hours"]           # a pass-through column
    assert row["details"]["academic_level"]
    # The identity columns are never persisted.
    assert "employee" not in str(row) and "ת.ז" not in str(row)


@pytest.mark.skipif(not os.path.exists(REAL_XLSX), reason="real skeleton not present")
def test_skeleton_groups_drive_solve(client):
    # Catalog declares 1 exercise group; the skeleton offers several -> the solve
    # places the skeleton's actual groups (named SE0xx), not the declared count.
    client.post("/catalog/courses", json={
        "number": "00940411", "programs": ["ChemE"], "year": 1, "role": "core",
        "lecture_boxes": 3, "exercise_boxes": 2, "num_exercise_groups": 1,
    })
    client.put("/courses-of-interest",
               json={"items": [{"number": "00940411", "name": ""}]})
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
    # Enrollment + farm need drive the per-room board's capacity hinting.
    assert meta["enrollment"] == 40
    assert meta["needs_farm"] is False
    # lab_group lets the drop-validity preview exempt cross-day labs.
    assert meta["lab_group"] is None


def test_catalog_export_template_and_import(client):
    client.post("/catalog/seed")
    n = len(client.get("/catalog/courses").json())

    exp = client.get("/catalog/export.csv")
    assert exp.status_code == 200
    assert exp.content[:3] == b"\xef\xbb\xbf"  # Excel-friendly BOM
    assert "filename=" in exp.headers.get("content-disposition", "")

    tpl = client.get("/catalog/template.csv")
    assert tpl.status_code == 200 and "number" in tpl.text

    # Wipe the catalog, then re-import the exported file -> fully restored.
    for c in client.get("/catalog/courses").json():
        client.delete(f"/catalog/courses/{c['number']}")
    assert client.get("/catalog/courses").json() == []

    r = client.post("/catalog/import",
                    files={"file": ("catalog.csv", exp.content, "text/csv")})
    assert r.status_code == 200 and r.json()["imported"] == n
    assert len(client.get("/catalog/courses").json()) == n


def test_catalog_import_empty_file_is_rejected(client):
    r = client.post("/catalog/import",
                    files={"file": ("x.csv", b"number,year\n", "text/csv")})
    assert r.status_code == 400


def test_delete_course(client):
    client.post("/catalog/courses", json=_core("00540319", "dr_a"))
    assert client.delete("/catalog/courses/00540319").status_code == 200
    assert client.get("/catalog/courses").json() == []


def test_saved_schedules_lifecycle(client):
    client.post("/catalog/seed")
    solved = client.post("/solve", json={"time_limit_s": 15}).json()
    assert solved["solved"], solved.get("status")
    n_sessions = len(solved["placements"])

    # Save the current solution as a named, self-contained scenario.
    saved = client.post("/schedules", json={"name": "2026 Spring", "note": "final"}).json()
    assert saved["name"] == "2026 Spring"
    assert saved["id"] and saved["created_at"]
    assert saved["stats"]["sessions"] == n_sessions
    assert saved["stats"]["hard"] == 0
    sid = saved["id"]

    # The list is lightweight (stats, no payload) and shows our save.
    lst = client.get("/schedules").json()
    assert len(lst) == 1 and lst[0]["name"] == "2026 Spring"
    assert lst[0]["stats"]["sessions"] == n_sessions
    assert "payload" not in lst[0]

    # Editing the live catalog must NOT disturb the frozen save.
    victim = client.get("/catalog/courses").json()[0]["number"]
    client.delete(f"/catalog/courses/{victim}")
    assert all(c["number"] != victim for c in client.get("/catalog/courses").json())

    # Loading restores the frozen scenario and returns a render-ready schedule.
    loaded = client.post(f"/schedules/{sid}/load").json()
    assert loaded["solved"] is True
    assert len(loaded["placements"]) == n_sessions
    assert "sessions" in loaded
    # the deleted course is back — catalog was restored from the snapshot.
    assert any(c["number"] == victim for c in client.get("/catalog/courses").json())

    # Rename, then delete.
    renamed = client.put(f"/schedules/{sid}", json={"name": "2026 Spring — final"}).json()
    assert renamed["name"] == "2026 Spring — final"
    new_id = renamed["id"]
    assert client.get("/schedules").json()[0]["name"] == "2026 Spring — final"
    assert client.delete(f"/schedules/{new_id}").status_code == 200
    assert client.get("/schedules").json() == []


def test_compare_schedules(client):
    client.post("/catalog/seed")
    solved = client.post("/solve", json={"time_limit_s": 15}).json()
    pls = solved["placements"]
    a = client.post("/schedules", json={"name": "A"}).json()

    # Move one session and remove another, then save B.
    ids = list(pls)
    moved_id, removed_id = ids[0], ids[1]
    edited = {k: v for k, v in pls.items() if k != removed_id}
    edited[moved_id] = {**pls[moved_id], "day": (pls[moved_id]["day"] + 1) % 5}
    client.post("/evaluate", json={"placements": edited})
    b = client.post("/schedules", json={"name": "B"}).json()

    cmp = client.get(f"/schedules/compare?a={a['id']}&b={b['id']}").json()
    assert cmp["summary"]["moved"] >= 1
    assert cmp["summary"]["removed"] >= 1
    statuses = {c["session_id"]: c["status"] for c in cmp["changes"]}
    assert statuses.get(moved_id) == "moved"
    assert statuses.get(removed_id) == "removed"
    # changes carry a human label (course number + name)
    moved_change = next(c for c in cmp["changes"] if c["session_id"] == moved_id)
    assert moved_change["course_number"] and "a" in moved_change and "b" in moved_change

    assert client.get("/schedules/compare?a=nope&b=nope").status_code == 404


def test_save_schedule_guards(client):
    # Nothing solved yet -> nothing to save.
    client.post("/catalog/seed")
    assert client.post("/schedules", json={"name": "x"}).status_code == 400
    # A name is required even once a schedule exists.
    client.post("/solve", json={"time_limit_s": 10})
    assert client.post("/schedules", json={"name": "  "}).status_code == 400
    # Unknown ids are 404s.
    assert client.post("/schedules/nope/load").status_code == 404
    assert client.delete("/schedules/nope").status_code == 404


def test_config_saves_dir_roundtrip(client, tmp_path):
    # Defaults to a folder beside the DB; can be pointed at any folder under
    # the root (see the containment tests below).
    default_dir = client.get("/config").json()["saves_dir"]
    assert default_dir.endswith("saves")
    target = str(tmp_path / "my-saves")
    out = client.put("/config", json={"saves_dir": target}).json()
    assert out["saves_dir"] == target
    assert os.path.isdir(target)  # created on set
    # Saves now land in the chosen folder.
    client.post("/catalog/seed")
    client.post("/solve", json={"time_limit_s": 10})
    client.post("/schedules", json={"name": "here"})
    import glob
    assert glob.glob(os.path.join(target, "*.schedy.json"))


# ---- the saves folder is confined ---------------------------------------- #
#
# Which folder holds the saves arrives in a request body, so it is the one
# piece of filesystem addressing a caller controls. Left open, a single PUT
# points the app at any folder on the machine and it then creates, reads,
# rewrites and deletes files there. The boundary belongs to whoever installed
# the app, not to the request.

def test_a_saves_folder_outside_the_root_is_refused(client, tmp_path):
    outside = tmp_path.parent / "outside-the-root"
    r = client.put("/config", json={"saves_dir": str(outside)})
    assert r.status_code == 400
    # Refused *before* touching the filesystem — a rejected request must not
    # leave a folder behind on the way out.
    assert not outside.exists()
    # ...and the working folder is unchanged.
    assert client.get("/config").json()["saves_dir"].endswith("saves")


def test_traversal_out_of_the_root_is_refused(client, tmp_path):
    r = client.put("/config", json={"saves_dir": str(tmp_path / ".." / "escape")})
    assert r.status_code == 400


def test_a_sibling_of_the_root_is_not_inside_it(client, tmp_path):
    # Containment is a path check, not a string prefix: "<root>-next-door"
    # starts with the root's name and is still a different folder.
    r = client.put("/config", json={"saves_dir": str(tmp_path) + "-next-door"})
    assert r.status_code == 400


def test_a_relative_folder_is_read_under_the_root(client, tmp_path):
    # The only reading of a relative name that cannot escape.
    out = client.put("/config", json={"saves_dir": "saves-2026"}).json()
    assert out["saves_dir"] == str((tmp_path / "saves-2026").resolve())


def test_config_reports_the_root_so_the_boundary_is_visible(client, tmp_path):
    # The planner gets told where they may put saves, rather than discovering
    # it by being refused.
    assert client.get("/config").json()["saves_root"] == str(tmp_path.resolve())


def test_a_stored_folder_outside_the_root_is_reported_not_silently_used(client, tmp_path):
    # A value stored before this boundary existed. It must not quietly keep
    # working — and it must not quietly disappear either, or the planner just
    # finds their saves gone with nothing said.
    stale = str(tmp_path.parent / "configured-long-ago")
    client.app.state.store.set_setting("saves_dir", stale)
    cfg = client.get("/config").json()
    assert cfg["saves_dir"] == str((tmp_path / "saves").resolve())
    assert cfg["rejected_saves_dir"] == stale


def test_an_operator_can_move_the_root_but_a_request_cannot(tmp_path, monkeypatch):
    # The synced-Drive workflow: widening the boundary is an install-time act
    # (an environment variable), not something a request can do for itself.
    elsewhere = tmp_path / "Drive" / "Schedy"
    elsewhere.mkdir(parents=True)
    monkeypatch.setenv("SCHEDY_SAVES_ROOT", str(elsewhere))
    store = Store(str(tmp_path / "moved.sqlite"))
    with TestClient(create_app(store)) as c:
        out = c.put("/config", json={"saves_dir": str(elsewhere / "saves")})
        assert out.status_code == 200
        assert out.json()["saves_dir"] == str((elsewhere / "saves").resolve())
        # The DB's own folder is now outside the root, so it is refused too:
        # the root is the boundary, not "anywhere familiar".
        assert c.put("/config", json={"saves_dir": str(tmp_path)}).status_code == 400
    store.close()


def test_clear_skeleton_rows(client):
    client.post("/catalog/courses", json=_core("00540319", "dr_a"))
    client.app.state.store.set_setting("offered_rows", [{
        "course_number": "00540319", "event_type": "exercise", "group_code": "SE011",
        "name_he": "x", "name_en": "y", "day": 0, "start_min": 510, "end_min": 570,
        "room": "", "package": "", "row": 2,
    }])
    assert len(client.get("/skeleton/rows").json()) == 1
    assert client.delete("/skeleton/rows").status_code == 200
    assert client.get("/skeleton/rows").json() == []


def test_unoffered_course_persists_but_leaves_the_solve(client):
    client.post("/catalog/courses", json=_core("00540319", "dr_a"))
    client.post("/catalog/courses", json=_core("00540777", "dr_b"))
    solved = client.post("/solve", json={"time_limit_s": 10}).json()
    assert {s["course_number"] for s in solved["sessions"].values()} == {
        "00540319", "00540777"}

    # Take one out for the term — it stays in the catalog, with its reason.
    off = {**_core("00540777", "dr_b"), "offered": False,
           "skip_reason": "Prof. B sabbatical 2026"}
    assert client.post("/catalog/courses", json=off).status_code == 200
    stored = {c["number"]: c for c in client.get("/catalog/courses").json()}
    assert len(stored) == 2
    assert stored["00540777"]["offered"] is False
    assert stored["00540777"]["skip_reason"] == "Prof. B sabbatical 2026"

    solved = client.post("/solve", json={"time_limit_s": 10}).json()
    assert {s["course_number"] for s in solved["sessions"].values()} == {"00540319"}


def test_courses_stored_before_the_flag_existed_are_offered(client):
    # A row written by an older build has no "offered" key; it must read as
    # offered rather than silently dropping out of the semester.
    store = client.app.state.store
    payload = _core("00540319", "dr_a")
    payload.pop("offered", None)
    client.post("/catalog/courses", json=payload)
    assert store.list_courses()[0].offered is True
    solved = client.post("/solve", json={"time_limit_s": 10}).json()
    assert solved["sessions"]


def test_reset_requires_confirmation_then_wipes_everything(client):
    store = client.app.state.store
    client.post("/catalog/courses", json=_core("00540319", "dr_a"))
    client.put("/availability", json={"dr_a": [[0, 0]]})
    store.set_setting("saves_dir", "/somewhere/saves")

    # Unconfirmed resets are refused — nothing is touched.
    assert client.post("/reset").status_code == 400
    assert len(client.get("/catalog/courses").json()) == 1

    r = client.post("/reset", params={"confirm": "true"})
    assert r.status_code == 200
    assert r.json()["courses"] == 1
    assert client.get("/catalog/courses").json() == []
    assert client.get("/availability").json() == {}
    assert client.get("/skeleton/rows").json() == []
    # The saves folder is a machine preference, not planning data: it survives.
    assert store.get_setting("saves_dir") == "/somewhere/saves"


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


def test_skeleton_rows_edit_then_solve(client):
    client.post("/catalog/courses", json=_core("00540319", "dr_a"))
    client.app.state.store.set_setting("offered_rows", [
        {"course_number": "00540319", "event_type": "exercise", "group_code": "SE011",
         "name_he": "", "name_en": "", "day": 1, "start_min": 9 * 60 + 30,
         "end_min": 10 * 60 + 30, "room": "", "package": "", "row": 1, "pinned": True},
    ])
    assert client.get("/skeleton/rows").json()[0]["group_code"] == "SE011"

    # Planner corrects the row: move to Thu(4) 15:30 and rename the group.
    edited = [{
        "course_number": "00540319", "event_type": "exercise", "group_code": "SE099",
        "name_he": "", "name_en": "", "day": 4, "start_min": 15 * 60 + 30,
        "end_min": 16 * 60 + 30, "room": "", "package": "", "row": 1,
    }]
    out = client.put("/skeleton/rows", json={"rows": edited}).json()
    assert out["offered"][0]["pinned"] is True  # recomputed server-side
    assert client.get("/skeleton/rows").json()[0]["group_code"] == "SE099"

    r = client.post("/solve", json={"time_limit_s": 8}).json()
    sid = "00540319-ex-SE099"
    assert r["placements"][sid]["day"] == 4
    assert r["placements"][sid]["start_box"] == 7  # 15:30 -> box 7


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
