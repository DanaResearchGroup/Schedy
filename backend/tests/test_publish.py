"""Publishing a term: freezing the undergraduate schedule so phase 2 can append.

The department releases the undergraduate timetable months before it knows which
graduate courses will run. Publishing is what makes that safe — everything the
students have already been told stays exactly where it was, while graduate
courses are placed around it later.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from schedy.catalog import Course, expand
from schedy.domain import Program
from schedy.api import create_app
from schedy.store import Store


@pytest.fixture()
def client(tmp_path):
    store = Store(str(tmp_path / "pub.sqlite"))
    app = create_app(store)
    with TestClient(app) as c:
        c.store = store
        yield c
    store.close()


def _course(number: str, **kw) -> dict:
    return {"number": number, "programs": ["ChemE"], "year": 2,
            "lecture_boxes": 2, "expected_enrollment": 30, **kw}


def _solve(client) -> dict:
    r = client.post("/solve", json={"time_limit_s": 5})
    assert r.status_code == 200 and r.json()["solved"], r.text
    return r.json()["placements"]


def _publish(client, **params):
    term = client.get("/terms/current").json()["id"]
    return client.post(f"/terms/{term}/publish", params=params)


# ---- expand() honours published pins ---------------------------------- #

def test_a_published_pin_fixes_day_box_and_room():
    # All three: pinning the hour alone lets a later solve move the room, and
    # students would arrive where the course no longer is.
    c = Course(number="00540001", programs=[Program.CHEME], year=2, lecture_boxes=2)
    problem = expand([c], pins={"00540001-lec": {"day": 1, "start_box": 3,
                                                 "room_id": "hall6"}})
    lec = next(s for s in problem.sessions if s.id == "00540001-lec")
    assert (lec.fixed_day, lec.fixed_box, lec.fixed_room) == (1, 3, "hall6")


def test_a_pin_for_a_session_that_no_longer_exists_is_ignored():
    # The planner may edit the catalog after publishing; a stale pin must not
    # crash the expansion.
    c = Course(number="00540001", programs=[Program.CHEME], year=2, lecture_boxes=2)
    problem = expand([c], pins={"00549999-lec": {"day": 0, "start_box": 0,
                                                 "room_id": "hall6"}})
    assert [s.id for s in problem.sessions] == ["00540001-lec"]


def test_unpinned_sessions_stay_free():
    c = Course(number="00540001", programs=[Program.CHEME], year=2, lecture_boxes=2)
    lec = expand([c], pins={}).sessions[0]
    assert not lec.is_fixed


def test_a_pin_marks_the_session_published():
    c = Course(number="00540001", programs=[Program.CHEME], year=2, lecture_boxes=2)
    lec = expand([c], pins={"00540001-lec": {"day": 1, "start_box": 3,
                                             "room_id": "hall6"}}).sessions[0]
    assert lec.is_published


def test_a_skeleton_anchor_is_not_a_publication():
    # A skeleton anchor is the university's timetable, which the planner may
    # override in the editor. A publication is what the students were told.
    c = Course(number="00540001", programs=[Program.CHEME], year=2, lecture_boxes=2)
    rows = [{"course_number": "00540001", "event_type": "lecture", "day": 1,
             "start_min": 510, "end_min": 630, "group_code": None}]
    lec = expand([c], offered_rows=rows).sessions[0]
    assert lec.fixed_day == 1 and not lec.is_published


# ---- moving what was published ----------------------------------------- #

def test_dragging_a_published_session_off_its_slot_is_a_hard_violation(client):
    client.post("/catalog/courses", json=_course("00540001"))
    placements = _solve(client)
    _publish(client, confirm=True)

    p = placements["00540001-lec"]
    moved = {"00540001-lec": {**p, "day": (p["day"] + 1) % 5}}
    r = client.post("/evaluate", json={"placements": moved}).json()
    hard = [v for v in r["violations"] if v["severity"] == "hard"]
    assert [v["kind"] for v in hard] == ["published_moved"]


def test_dragging_a_skeleton_anchored_session_stays_a_soft_notice(client):
    # Unchanged behaviour: the anchor constrains the solver, not the planner.
    client.post("/catalog/courses", json=_course("00540001"))
    client.store.set_setting("offered_rows", [
        {"course_number": "00540001", "event_type": "lecture", "day": 1,
         "start_min": 510, "end_min": 630, "group_code": None}])
    placements = _solve(client)

    p = placements["00540001-lec"]
    moved = {"00540001-lec": {**p, "day": (p["day"] + 1) % 5}}
    r = client.post("/evaluate", json={"placements": moved}).json()
    kinds = {v["kind"]: v["severity"] for v in r["violations"]}
    assert kinds.get("fixed_placement") == "soft"
    assert "published_moved" not in kinds


def test_the_grid_is_told_which_sessions_are_published(client):
    client.post("/catalog/courses", json=_course("00540001"))
    client.post("/catalog/courses", json=_course("00580001"))       # grad
    _solve(client)
    _publish(client, confirm=True)

    meta = client.post("/evaluate", json={
        "placements": client.store.get_setting("last_schedule")}).json()["sessions"]
    assert meta["00540001-lec"]["published"] is True
    assert meta["00580001-lec"]["published"] is False


# ---- what publishing refuses ------------------------------------------ #

def test_publishing_without_a_solved_schedule_is_a_409(client):
    client.post("/catalog/courses", json=_course("00540001"))
    assert _publish(client, confirm=True).status_code == 409


def test_publishing_needs_confirmation(client):
    client.post("/catalog/courses", json=_course("00540001"))
    _solve(client)
    assert _publish(client).status_code == 400


def test_publishing_a_term_that_is_not_open_is_a_409(client):
    client.post("/catalog/courses", json=_course("00540001"))
    _solve(client)
    client.post("/terms", json={"year": "2099-00", "semester": "spring"})
    r = client.post("/terms/2099-00-spring/publish", params={"confirm": True})
    assert r.status_code == 409


def test_publishing_an_unknown_term_is_a_404(client):
    r = client.post("/terms/2050-51-spring/publish", params={"confirm": True})
    assert r.status_code == 404


def test_refuses_to_freeze_a_schedule_with_hard_conflicts(client):
    # Freezing a broken schedule would make the breakage permanent.
    client.post("/catalog/courses", json=_course("00540001"))
    placements = _solve(client)
    sid = next(iter(placements))
    bad = dict(placements)
    # A 30-student course in the 22-seat computer farm: capacity_exceeded.
    bad[sid] = {**bad[sid], "day": 2, "start_box": 4, "room_id": "room2"}
    client.store.set_setting("last_schedule", bad)
    r = _publish(client, confirm=True)
    assert r.status_code == 409
    assert "hard" in r.text.lower()


def test_refuses_to_publish_while_an_undergraduate_session_is_unplaced(client):
    # An unplaced session raises no violation of its own, so it would silently
    # vanish from a frozen schedule.
    client.post("/catalog/courses", json=_course("00540001"))
    client.post("/catalog/courses", json=_course("00540002"))
    placements = _solve(client)
    placements.pop(next(iter(placements)))
    client.store.set_setting("last_schedule", placements)
    r = _publish(client, confirm=True)
    assert r.status_code == 409
    assert "unplaced" in r.text.lower()


# ---- what publishing does --------------------------------------------- #

def test_publishing_stamps_the_term(client):
    client.post("/catalog/courses", json=_course("00540001"))
    _solve(client)
    assert _publish(client, confirm=True).status_code == 200
    assert client.get("/terms/current").json()["published"]


def test_a_provisional_stand_in_is_not_frozen_by_publishing(client):
    """A stand-in is a guess, and publishing is a promise to students.

    Rollover copies in *graduate-level* courses, which includes joint ones, so a
    provisional joint course is not GRAD and would otherwise be pinned to a day,
    an hour and a room before anyone confirmed it runs. Phase 2 then refuses to
    start until the provisional courses are settled, leaving the planner having
    to unpublish the whole week to undo a placeholder.
    """
    client.post("/catalog/courses", json=_course("00540001"))
    client.post("/catalog/courses", json=_course(
        "00560001", level="joint", role="elective", provisional=True))
    _solve(client)
    assert _publish(client, confirm=True).status_code == 200
    pinned = client.app.state.store.get_setting("published_schedule")
    assert "00540001-lec" in pinned          # the real course is frozen
    assert "00560001-lec" not in pinned      # the placeholder is not


def test_an_unplaced_provisional_course_does_not_block_publishing(client):
    # It is not going into the published week, so it has no say over whether
    # that week can be published.
    client.post("/catalog/courses", json=_course("00540001"))
    client.post("/catalog/courses", json=_course(
        "00560001", level="joint", role="elective", provisional=True))
    placements = _solve(client)
    del placements["00560001-lec"]
    client.app.state.store.set_setting("last_schedule", placements)
    assert _publish(client, confirm=True).status_code == 200


def test_the_publication_stamp_is_an_instant_not_a_day(client):
    # Two publishes on one day have to be tellable apart, and the record has to
    # sort — a bare local date loses both, and the timezone with them.
    client.post("/catalog/courses", json=_course("00540001"))
    _solve(client)
    _publish(client, confirm=True)
    stamp = client.get("/terms/current").json()["published"]
    parsed = datetime.fromisoformat(stamp)
    assert parsed.tzinfo is not None, "an instant with no timezone is not an instant"
    assert (datetime.now(timezone.utc) - parsed).total_seconds() < 120


def test_published_sessions_survive_a_re_solve_unchanged(client):
    client.post("/catalog/courses", json=_course("00540001"))
    client.post("/catalog/courses", json=_course("00540002"))
    before = _solve(client)
    _publish(client, confirm=True)
    after = _solve(client)
    for sid, p in before.items():
        assert after[sid] == p, f"{sid} moved after publishing"


def test_publishing_freezes_undergraduate_and_joint_but_not_graduate(client):
    client.post("/catalog/courses", json=_course("00540001"))              # ug
    client.post("/catalog/courses", json=_course("00560001"))              # joint
    client.post("/catalog/courses", json=_course("00580001"))              # grad
    _solve(client)
    _publish(client, confirm=True)

    pinned = client.store.get_setting("published_schedule")
    assert set(pinned) == {"00540001-lec", "00560001-lec"}


def test_graduate_courses_stay_fluid_after_publishing(client):
    client.post("/catalog/courses", json=_course("00580001"))
    _solve(client)
    _publish(client, confirm=True)
    grad = next(s for s in _sessions(client) if s["course_number"] == "00580001")
    assert not grad["fixed"]


def _sessions(client) -> list[dict]:
    r = client.post("/evaluate", json={"placements":
                                       client.store.get_setting("last_schedule")})
    return list(r.json()["sessions"].values())


def test_publishing_is_visible_in_the_term_list(client):
    client.post("/catalog/courses", json=_course("00540001"))
    _solve(client)
    _publish(client, confirm=True)
    term = next(t for t in client.get("/terms").json()["terms"])
    assert term["published"]


# ---- un-publishing ----------------------------------------------------- #

def test_unpublishing_needs_confirmation(client):
    client.post("/catalog/courses", json=_course("00540001"))
    _solve(client)
    _publish(client, confirm=True)
    term = client.get("/terms/current").json()["id"]
    r = client.delete(f"/terms/{term}/publish")
    assert r.status_code == 400


def test_unpublishing_clears_the_stamp_and_the_pins(client):
    client.post("/catalog/courses", json=_course("00540001"))
    _solve(client)
    _publish(client, confirm=True)
    term = client.get("/terms/current").json()["id"]

    r = client.delete(f"/terms/{term}/publish", params={"confirm": True})
    assert r.status_code == 200
    assert client.get("/terms/current").json()["published"] is None
    assert not client.store.get_setting("published_schedule")


# ---- a pin the catalog has outgrown ------------------------------------ #

def test_solve_reports_nothing_missing_when_the_catalog_is_intact(client):
    client.post("/catalog/courses", json=_course("00540001"))
    _solve(client)
    _publish(client, confirm=True)
    assert client.post("/solve", json={"time_limit_s": 5}).json()["published_missing"] == []


def test_a_term_that_was_never_published_reports_nothing_missing(client):
    client.post("/catalog/courses", json=_course("00540001"))
    assert client.post("/solve", json={"time_limit_s": 5}).json()["published_missing"] == []


# ---- the university moves a slot after publication --------------------- #

def _skeleton_row(number: str, day: int, start_min: int) -> dict:
    return {"course_number": number, "event_type": "lecture", "day": day,
            "start_min": start_min, "end_min": start_min + 120, "group_code": None}


def test_a_skeleton_reimported_onto_a_published_slot_is_reported(client):
    # The published pin wins — it is what the students were told — but a
    # university that has moved the hour is not something to resolve in silence.
    client.post("/catalog/courses", json=_course("00540001"))
    _solve(client)
    _publish(client, confirm=True)
    pin = client.store.get_setting("published_schedule")["00540001-lec"]

    moved_day = (pin["day"] + 1) % 5
    client.store.set_setting("offered_rows", [_skeleton_row("00540001", moved_day, 510)])

    r = client.post("/solve", json={"time_limit_s": 5}).json()
    assert r["published_conflicts"] == [
        {"session_id": "00540001-lec", "published": [pin["day"], pin["start_box"]],
         "skeleton": [moved_day, 0]},
    ]
    # …and the published placement is the one that actually holds.
    assert r["placements"]["00540001-lec"]["day"] == pin["day"]


def test_a_skeleton_that_agrees_with_the_published_slot_is_no_conflict(client):
    client.post("/catalog/courses", json=_course("00540001"))
    _solve(client)
    _publish(client, confirm=True)
    pin = client.store.get_setting("published_schedule")["00540001-lec"]

    client.store.set_setting("offered_rows", [
        _skeleton_row("00540001", pin["day"], 510 + 60 * pin["start_box"])])
    assert client.post("/solve", json={"time_limit_s": 5}).json()["published_conflicts"] == []


# ---- reset ------------------------------------------------------------ #

def test_resetting_a_term_unpublishes_it(client):
    # Reset deletes the frozen placements, so a term still calling itself
    # published would be claiming it about nothing.
    client.post("/catalog/courses", json=_course("00540001"))
    _solve(client)
    _publish(client, confirm=True)

    client.post("/reset", params={"confirm": True})
    assert client.get("/terms/current").json()["published"] is None


# ---- publishing is per term ------------------------------------------- #

def test_publishing_one_term_leaves_another_unpublished(client):
    client.post("/catalog/courses", json=_course("00540001"))
    _solve(client)
    _publish(client, confirm=True)

    client.post("/terms", json={"year": "2099-00", "semester": "spring"})
    client.put("/terms/current", json={"term": "2099-00-spring"})
    assert client.get("/terms/current").json()["published"] is None
    assert not client.store.get_setting("published_schedule")


def test_the_level_of_a_course_decides_whether_it_freezes(client):
    # A graduate course from another faculty numbers however that faculty likes,
    # so the manual level — not the prefix — is what publishing must read.
    client.post("/catalog/courses", json=_course("12345678", level="grad"))
    _solve(client)
    _publish(client, confirm=True)
    assert client.store.get_setting("published_schedule") == {}


# ---- a save belongs to a term ------------------------------------------ #

def test_a_save_is_listed_with_its_term(client, tmp_path):
    client.put("/config", json={"saves_dir": str(tmp_path / "saves")})
    client.post("/catalog/courses", json=_course("00540001"))
    _solve(client)
    client.post("/schedules", json={"name": "plan"})

    here = client.get("/terms/current").json()["id"]
    assert client.get("/schedules").json()[0]["term"] == here


def test_loading_a_save_from_another_term_needs_confirmation(client, tmp_path):
    # The save carries a whole catalog; dropping last year's into this year by
    # accident would replace a semester's work with the wrong semester's.
    client.put("/config", json={"saves_dir": str(tmp_path / "saves")})
    client.post("/catalog/courses", json=_course("00540001"))
    _solve(client)
    save_id = client.post("/schedules", json={"name": "plan"}).json()["id"]

    client.post("/terms", json={"year": "2099-00", "semester": "spring"})
    client.put("/terms/current", json={"term": "2099-00-spring"})

    r = client.post(f"/schedules/{save_id}/load")
    assert r.status_code == 409
    assert client.get("/catalog/courses").json() == []      # nothing replaced

    r = client.post(f"/schedules/{save_id}/load", params={"confirm": True})
    assert r.status_code == 200
    assert len(client.get("/catalog/courses").json()) == 1


def test_loading_a_save_from_this_term_needs_no_confirmation(client, tmp_path):
    client.put("/config", json={"saves_dir": str(tmp_path / "saves")})
    client.post("/catalog/courses", json=_course("00540001"))
    _solve(client)
    save_id = client.post("/schedules", json={"name": "plan"}).json()["id"]
    assert client.post(f"/schedules/{save_id}/load").status_code == 200


def test_loading_a_save_that_predates_terms_needs_no_confirmation(client, tmp_path):
    # It belongs to no term, so it contradicts none.
    import json as _json
    saves = tmp_path / "saves"
    saves.mkdir()
    client.put("/config", json={"saves_dir": str(saves)})
    (saves / "old.schedy.json").write_text(_json.dumps({
        "schema": 1, "name": "old", "created_at": "2020-01-01T00:00:00",
        "stats": {}, "payload": {"courses": [], "placements": {}}}))
    assert client.post("/schedules/old/load").status_code == 200


# ---- found in adversarial review (spar round 1) ------------------------ #

def test_an_edit_that_breaks_a_publication_is_not_persisted(client):
    # /evaluate persists so exports reflect manual edits. An edit that breaks the
    # freeze must not be the one it persists — the exports are what the students
    # were given.
    client.post("/catalog/courses", json=_course("00540001"))
    placements = _solve(client)
    _publish(client, confirm=True)
    before = client.store.get_setting("last_schedule")

    p = placements["00540001-lec"]
    moved = {"00540001-lec": {**p, "day": (p["day"] + 1) % 5}}
    r = client.post("/evaluate", json={"placements": moved}).json()

    assert "published_moved" in [v["kind"] for v in r["violations"]]
    assert client.store.get_setting("last_schedule") == before   # unchanged


def test_a_legal_edit_is_still_persisted(client):
    client.post("/catalog/courses", json=_course("00540001"))
    client.post("/catalog/courses", json=_course("00580001"))        # grad, fluid
    _solve(client)
    _publish(client, confirm=True)

    placements = dict(client.store.get_setting("last_schedule"))
    g = placements["00580001-lec"]
    placements["00580001-lec"] = {**g, "day": (g["day"] + 1) % 5}
    client.post("/evaluate", json={"placements": placements})
    assert client.store.get_setting("last_schedule") == placements


# ---- loading a save must not move what was published ------------------ #

def _save_moved_variant(client, tmp_path):
    """Save a snapshot whose lecture sits a day off, then restore the real one."""
    client.put("/config", json={"saves_dir": str(tmp_path / "saves")})
    client.post("/catalog/courses", json=_course("00540001"))
    placements = _solve(client)
    p = placements["00540001-lec"]
    moved = {"00540001-lec": {**p, "day": (p["day"] + 1) % 5}}
    client.post("/evaluate", json={"placements": moved})
    save_id = client.post("/schedules", json={"name": "moved"}).json()["id"]
    client.post("/evaluate", json={"placements": placements})    # back to the real one
    return save_id


def test_loading_a_save_that_moves_a_published_session_is_refused(client, tmp_path):
    save_id = _save_moved_variant(client, tmp_path)
    _publish(client, confirm=True)
    before = client.get("/export/csv").content

    r = client.post(f"/schedules/{save_id}/load")

    assert r.status_code == 409, r.text
    assert "published" in r.json()["detail"]
    assert client.get("/export/csv").content == before       # nothing persisted


def test_loading_a_save_that_agrees_with_the_published_schedule_still_works(
        client, tmp_path):
    client.put("/config", json={"saves_dir": str(tmp_path / "saves")})
    client.post("/catalog/courses", json=_course("00540001"))
    _solve(client)
    save_id = client.post("/schedules", json={"name": "same"}).json()["id"]
    _publish(client, confirm=True)

    r = client.post(f"/schedules/{save_id}/load")

    assert r.status_code == 200, r.text
    assert r.json()["feasible"] is True


# ---- finding 1: a save that drops a published session -------------------- #

def _published_two(client, tmp_path):
    client.put("/config", json={"saves_dir": str(tmp_path / "saves")})
    client.post("/catalog/courses", json=_course("00540001"))
    client.post("/catalog/courses", json=_course("00540002"))
    _solve(client)


def _snapshot_save(client, tmp_path, name, edit):
    """Save the current state, then rewrite the saved JSON with `edit(payload)`."""
    import json
    save_id = client.post("/schedules", json={"name": name}).json()["id"]
    path = next((tmp_path / "saves").glob(f"*{save_id}*"))
    doc = json.loads(path.read_text(encoding="utf-8"))
    edit(doc["payload"])
    path.write_text(json.dumps(doc), encoding="utf-8")
    return save_id


def _drop_placement(p):
    del p["placements"]["00540002-lec"]


def _drop_course(p):
    p["courses"] = [c for c in p["courses"] if c["number"] != "00540002"]


def _drop_both(p):
    _drop_placement(p)
    _drop_course(p)


@pytest.mark.parametrize("edit", [_drop_placement, _drop_course, _drop_both])
def test_loading_a_save_that_drops_a_published_session_is_refused(
        client, tmp_path, edit):
    _published_two(client, tmp_path)
    save_id = _snapshot_save(client, tmp_path, "drops", edit)
    _publish(client, confirm=True)
    before = client.get("/export/csv").content

    r = client.post(f"/schedules/{save_id}/load")

    assert r.status_code == 409, r.text
    assert "00540002-lec" in r.json()["detail"]
    assert "unpublish the term first" in r.json()["detail"]
    assert client.get("/export/csv").content == before
    assert len(client.get("/catalog/courses").json()) == 2


# ---- finding 4: an invalid save must not half-replace the catalog ---------- #

def test_loading_an_invalid_save_leaves_the_catalog_untouched(client, tmp_path):
    _published_two(client, tmp_path)
    def corrupt(p):
        p["courses"][1] = {"number": "00540002", "lecture_boxes": "not a number"}
    save_id = _snapshot_save(client, tmp_path, "bad", corrupt)
    before = client.get("/catalog/courses").json()

    r = client.post(f"/schedules/{save_id}/load")

    assert r.status_code == 400, r.text
    assert client.get("/catalog/courses").json() == before


# ---- finding 2: every other write path ----------------------------------- #

def _published_pair(client):
    client.post("/catalog/courses", json=_course("00540001"))
    client.post("/catalog/courses", json=_course("00540002"))
    placements = _solve(client)
    assert _publish(client, confirm=True).status_code == 200
    return placements


def test_evaluate_refuses_a_schedule_that_omits_a_published_session(client):
    placements = _published_pair(client)
    before = client.get("/export/csv").content
    partial = {k: v for k, v in placements.items() if k != "00540002-lec"}

    r = client.post("/evaluate", json={"placements": partial})

    assert r.status_code == 409, r.text
    assert "00540002-lec" in r.json()["detail"]
    assert "unpublish the term first" in r.json()["detail"]
    assert client.get("/export/csv").content == before


@pytest.mark.parametrize("path", ["/solve", "/solve/grad"])
def test_solve_refuses_when_a_published_session_has_no_definition(client, path):
    # A legacy state: the baseline names a session the catalog no longer makes.
    _published_pair(client)
    frozen = client.store.get_setting("published_schedule")
    client.store.set_setting("published_schedule", {
        **frozen, "00549999-lec": {"day": 0, "start_box": 0, "room_id": "hall6"}})
    before = client.get("/export/csv").content

    r = client.post(path, json={"time_limit_s": 5})

    assert r.status_code == 409, r.text
    assert "00549999-lec" in r.json()["detail"]
    assert "unpublish the term first" in r.json()["detail"]
    assert client.get("/export/csv").content == before


def test_catalog_paths_refuse_to_drop_a_published_course(client):
    _published_pair(client)
    before = client.get("/export/csv").content
    keep = client.get("/catalog/export.csv").content.decode("utf-8-sig")
    header, *rows = keep.strip().splitlines()
    only_first = "\n".join([header, rows[0]])

    attempts = [
        client.delete("/catalog/courses/00540002"),
        client.post("/catalog/courses", json=_course("00540002", lecture_boxes=0)),
        client.post("/catalog/seed", params={"force": True}),
        client.post("/catalog/import",
                    files={"file": ("c.csv", only_first.encode("utf-8"), "text/csv")}),
    ]

    for r in attempts:
        assert r.status_code == 409, r.text
        assert "unpublish the term first" in r.json()["detail"]
    assert len(client.get("/catalog/courses").json()) == 2
    assert client.get("/export/csv").content == before


def test_catalog_edit_that_keeps_every_published_session_still_works(client):
    _published_pair(client)
    r = client.post("/catalog/courses", json=_course("00540003"))
    assert r.status_code == 200, r.text


def test_skeleton_edits_that_rename_a_published_exercise_group_are_refused(client):
    # Renaming a group changes the session id, which would drop it from the week.
    client.post("/catalog/courses", json=_course("00540001", num_exercise_groups=1))
    ex = {"course_number": "00540001", "event_type": "exercise", "group_code": "11",
          "day": None, "start_min": None, "end_min": None}
    assert client.put("/skeleton/rows", json={"rows": [ex]}).status_code == 200
    _solve(client)
    _publish(client, confirm=True)
    assert "00540001-ex-11" in client.store.get_setting("published_schedule")
    before = client.get("/export/csv").content

    renamed = client.put("/skeleton/rows", json={"rows": [{**ex, "group_code": "12"}]})
    cleared = client.delete("/skeleton/rows")

    for r in (renamed, cleared):
        assert r.status_code == 409, r.text
        assert "00540001-ex-11" in r.json()["detail"]
        assert "unpublish the term first" in r.json()["detail"]
    assert client.get("/skeleton/rows").json()[0]["group_code"] == "11"
    assert client.get("/export/csv").content == before


# ---- round 3: course keys, restore atomicity, republishing ---------------- #

def _csv_of(client, rows_edit):
    text = client.get("/catalog/export.csv").content.decode("utf-8-sig")
    header, *rows = text.strip().splitlines()
    return "\n".join([header, *rows_edit(rows)]).encode("utf-8")


def test_a_catalog_with_duplicate_course_numbers_is_refused(client):
    _published_pair(client)
    before = client.get("/export/csv").content
    catalog = client.get("/catalog/export.csv").content

    def dup_dropping(rows):
        # Same number twice; the later copy is not offered, which would silently
        # drop a published session if the last one won.
        later = [r for r in rows if "00540002" in r][0]
        return [*rows, later.replace(",True,", ",False,", 1)]

    r = client.post("/catalog/import", files={"file": (
        "c.csv", _csv_of(client, dup_dropping), "text/csv")})

    assert r.status_code == 400, r.text
    assert "duplicate" in r.json()["detail"].lower()
    assert client.get("/catalog/export.csv").content == catalog
    assert client.get("/export/csv").content == before


def test_a_numeric_course_key_cannot_slip_past_the_freeze_guard(client):
    client.post("/catalog/courses", json=_course("12345678"))
    client.post("/catalog/courses", json=_course("00540002"))
    _solve(client)
    assert _publish(client, confirm=True).status_code == 200
    before = client.get("/export/csv").content
    catalog = client.get("/catalog/courses").json()

    r = client.post("/catalog/courses", json=_course(12345678, lecture_boxes=0))

    assert r.status_code == 409, r.text
    assert client.get("/catalog/courses").json() == catalog
    assert client.get("/export/csv").content == before


def test_a_snapshot_with_duplicate_course_numbers_is_refused(client, tmp_path):
    _published_two(client, tmp_path)

    def dup(p):
        p["courses"].append({**p["courses"][1], "lecture_boxes": 0})
    save_id = _snapshot_save(client, tmp_path, "dup", dup)
    _publish(client, confirm=True)
    before = client.get("/export/csv").content
    catalog = client.get("/catalog/courses").json()

    r = client.post(f"/schedules/{save_id}/load")

    assert r.status_code == 400, r.text
    assert client.get("/catalog/courses").json() == catalog
    assert client.get("/export/csv").content == before


def _null_number(p):
    p["courses"].insert(0, {"number": None})


def _bad_availability(p):
    p["availability"] = 42


def _unknown_room(p):
    sid = next(iter(p["placements"]))
    p["placements"][sid]["room_id"] = "no-such-room"


@pytest.mark.parametrize("edit", [_null_number, _bad_availability, _unknown_room])
@pytest.mark.parametrize("published", [False, True])
def test_a_bad_snapshot_is_refused_and_changes_nothing(
        client, tmp_path, edit, published):
    _published_two(client, tmp_path)
    save_id = _snapshot_save(client, tmp_path, "bad", edit)
    if published:
        _publish(client, confirm=True)
    before = client.get("/export/csv").content
    catalog = client.get("/catalog/courses").json()
    avail = client.get("/availability").json()

    r = client.post(f"/schedules/{save_id}/load")

    assert 400 <= r.status_code < 500, r.text
    assert client.get("/catalog/courses").json() == catalog
    assert client.get("/availability").json() == avail
    after = client.get("/export/csv")
    assert after.status_code == 200
    assert after.content == before


def test_a_failure_mid_restore_rolls_the_store_back(client):
    client.post("/catalog/courses", json=_course("00540001"))
    store = client.store
    with pytest.raises(RuntimeError):
        with store.transaction():
            store.delete_course("00540001")
            store.set_setting("availability", {"x": []})
            raise RuntimeError("boom")
    assert [c.number for c in store.list_courses()] == ["00540001"]
    assert store.get_setting("availability") is None


def _legacy_numeric_catalog(client):
    """A row stored with an int number, as older versions left it."""
    client.store.upsert_course(Course(number=12345678, programs=[Program.CHEME],
                                      year=2, lecture_boxes=2,
                                      expected_enrollment=30))
    client.post("/catalog/courses", json=_course("00540002"))
    _solve(client)
    assert _publish(client, confirm=True).status_code == 200


def test_a_legacy_numeric_row_cannot_be_upserted_past_the_freeze(client):
    _legacy_numeric_catalog(client)
    before = client.get("/export/csv").content

    r = client.post("/catalog/courses", json=_course("12345678", lecture_boxes=0))

    assert r.status_code == 409, r.text
    assert client.get("/export/csv").content == before


def test_a_legacy_numeric_row_cannot_be_deleted_past_the_freeze(client):
    _legacy_numeric_catalog(client)
    before = client.get("/export/csv").content

    r = client.delete("/catalog/courses/12345678")

    assert r.status_code == 409, r.text
    assert client.get("/export/csv").content == before


def test_loading_ignores_the_current_availability_it_is_replacing(client, tmp_path):
    client.put("/config", json={"saves_dir": str(tmp_path / "saves")})
    client.post("/catalog/courses", json=_course("00540001"))
    _solve(client)
    save_id = client.post("/schedules", json={"name": "ok"}).json()["id"]
    # Accepted by the API but unparseable: it must not poison a valid save.
    client.put("/availability", json={"alice": [["bad", 0]]})

    r = client.post(f"/schedules/{save_id}/load")

    assert r.status_code == 200, r.text


def test_publishing_an_already_published_term_is_refused(client):
    _published_pair(client)
    pins = client.store.get_setting("published_schedule")
    # Mark a frozen course provisional: a re-publish would silently unpin it.
    r = client.post("/catalog/courses", json=_course("00540002", provisional=True))
    assert r.status_code in (200, 409), r.text

    again = _publish(client, confirm=True)

    assert again.status_code == 409, again.text
    assert "unpublish" in again.json()["detail"]
    assert client.store.get_setting("published_schedule") == pins
