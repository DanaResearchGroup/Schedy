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
from schedy.domain import CourseLevel, Program
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
    assert client.delete(f"/terms/{term}/publish").status_code == 400


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

def test_solve_reports_a_published_session_the_catalog_no_longer_has(client):
    # Deleting a published course drops it from the frozen schedule silently —
    # nothing else would say so, because a session that does not exist raises no
    # violation.
    client.post("/catalog/courses", json=_course("00540001"))
    client.post("/catalog/courses", json=_course("00540002"))
    _solve(client)
    _publish(client, confirm=True)

    client.delete("/catalog/courses/00540002")
    r = client.post("/solve", json={"time_limit_s": 5}).json()
    assert r["published_missing"] == ["00540002-lec"]


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
