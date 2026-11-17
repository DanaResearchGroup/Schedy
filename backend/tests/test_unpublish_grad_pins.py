"""Un-publishing keeps the graduate-level placements as pins.

Every graduate-level session placed at un-publish stays where it is, as a hard
pin guarded like a published one until the planner releases it. A write that
would move or drop one, and a solve that cannot honour one, fail loudly (409).
Provenance is the course level, not bookkeeping, so retries, publish cycles and
legacy terms all behave the same.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import schedy.api as api_mod
from schedy.api import create_app
from schedy.solver import SolveResult
from schedy.store import Store

GRAD = "00580001-lec"
BIG = 100   # more than the room the grad course landed in


@pytest.fixture()
def client(tmp_path):
    store = Store(str(tmp_path / "gp.sqlite"))
    app = create_app(store)
    with TestClient(app) as c:
        c.store = store
        yield c
    store.close()


def _ug(number: str, **kw) -> dict:
    return {"number": number, "programs": ["ChemE"], "year": 2,
            "lecture_boxes": 2, "expected_enrollment": 30, **kw}


def _grad(number: str = "00580001", **kw) -> dict:
    return {"number": number, "programs": [], "year": 0, "lecture_boxes": 2,
            "expected_enrollment": 15, **kw}


def _term(client) -> str:
    return client.get("/terms/current").json()["id"]


def _appended_then_unpublished(client, **grad_kw) -> dict:
    """Publish a UG week, append one grad course, unpublish. Returns its slot."""
    slot = _appended_then_unpublished_setup(client, **grad_kw)
    assert client.delete(f"/terms/{_term(client)}/publish",
                         params={"confirm": True}).status_code == 200
    return slot


def _appended_then_unpublished_setup(client, **grad_kw) -> dict:
    """Publish a UG week and append one grad course. Returns its slot."""
    client.post("/catalog/courses", json=_ug("00540001"))
    assert client.post("/solve", json={"time_limit_s": 5}).json()["solved"]
    term = _term(client)
    assert client.post(f"/terms/{term}/publish", params={"confirm": True}).status_code == 200
    client.post("/catalog/courses", json=_grad(**grad_kw))
    r = client.post("/solve/grad", json={"time_limit_s": 10}).json()
    assert GRAD in r["appended"]
    return r["placements"][GRAD]


def _msg(r) -> str:
    """The solve refusal's message: a structured detail, or a plain string."""
    d = r.json()["detail"]
    return d["message"] if isinstance(d, dict) else d


def _csv_row(client, sid: str) -> str:
    body = client.get("/export/csv").text
    return next(line for line in body.splitlines() if sid in line)


# 1 ---------------------------------------------------------------------- #

def test_unpublishing_keeps_the_grad_placement_and_reports_it_pinned(client):
    client.post("/catalog/courses", json=_ug("00540001"))
    client.post("/solve", json={"time_limit_s": 5})
    term = _term(client)
    client.post(f"/terms/{term}/publish", params={"confirm": True})
    client.post("/catalog/courses", json=_grad())
    slot = client.post("/solve/grad", json={"time_limit_s": 10}).json()["placements"][GRAD]
    row_before = _csv_row(client, GRAD)

    r = client.delete(f"/terms/{term}/publish", params={"confirm": True})
    assert r.status_code == 200
    assert r.json()["grad_pinned"] == [GRAD]
    assert not r.json()["published"]

    assert client.get(f"/terms/{term}/grad-pins").json()["pinned"] == {GRAD: slot}
    assert _csv_row(client, GRAD) == row_before
    meta = client.post("/evaluate", json={"placements": client.store.get_setting(
        "last_schedule")}).json()["sessions"]
    assert meta[GRAD]["grad_pinned"] and not meta["00540001-lec"]["grad_pinned"]


def test_unpublishing_pins_by_level_even_without_any_bookkeeping(client):
    """A legacy term has no record of what phase 2 appended: level decides."""
    slot = _appended_then_unpublished_setup(client)
    client.store.set_setting("grad_appended", None)   # what an old term looks like
    term = _term(client)
    r = client.delete(f"/terms/{term}/publish", params={"confirm": True})
    assert r.json()["grad_pinned"] == [GRAD]
    assert client.get(f"/terms/{term}/grad-pins").json()["pinned"] == {GRAD: slot}


def test_a_group_added_to_an_appended_course_is_pinned_too(client):
    client.post("/catalog/courses", json=_ug("00540001"))
    client.post("/solve", json={"time_limit_s": 5})
    term = _term(client)
    client.post(f"/terms/{term}/publish", params={"confirm": True})
    client.post("/catalog/courses", json=_grad())
    assert client.post("/solve/grad", json={"time_limit_s": 10}).json()["solved"]
    client.post("/catalog/courses", json=_grad(num_exercise_groups=1))
    r = client.post("/solve", json={"time_limit_s": 10}).json()
    assert r["solved"]
    ex = next(sid for sid in r["placements"] if sid.startswith("00580001") and sid != GRAD)
    out = client.delete(f"/terms/{term}/publish", params={"confirm": True}).json()
    assert out["grad_pinned"] == sorted([GRAD, ex])


# 2 ---------------------------------------------------------------------- #

def test_a_re_solve_after_unpublish_keeps_the_grad_slot(client):
    slot = _appended_then_unpublished(client)
    client.post("/catalog/courses", json=_ug("00540002"))
    r = client.post("/solve", json={"time_limit_s": 10})
    assert r.status_code == 200 and r.json()["solved"]
    assert r.json()["placements"][GRAD] == slot
    assert client.get("/export/csv").status_code == 200


# 3 ---------------------------------------------------------------------- #

def _make_pin_infeasible(client, slot: dict) -> None:
    client.put("/availability", json={"ghost": [[slot["day"], b] for b in range(10)]})
    got = next(c for c in client.get("/catalog/courses").json()
               if c["number"] == "00580001")
    client.post("/catalog/courses", json={**got, "lecturer_ids": ["ghost"]})


def test_a_re_solve_that_cannot_keep_a_grad_pin_fails_loudly_and_changes_nothing(client):
    slot = _appended_then_unpublished(client)
    stored = client.store.get_setting("last_schedule")
    _make_pin_infeasible(client, slot)

    r = client.post("/solve", json={"time_limit_s": 10})
    assert r.status_code == 409
    assert GRAD in _msg(r)
    assert "grad-pins" in _msg(r)
    assert client.store.get_setting("last_schedule") == stored
    assert GRAD in client.get(f"/terms/{_term(client)}/grad-pins").json()["pinned"]


def _stub_solve(monkeypatch, status):
    monkeypatch.setattr(api_mod, "solve",
                        lambda *a, **k: SolveResult(status, None, None, None))


def test_an_unknown_solve_names_all_pins_and_says_it_timed_out(client, monkeypatch):
    _appended_then_unpublished(client)
    stored = client.store.get_setting("last_schedule")
    _stub_solve(monkeypatch, "UNKNOWN")
    r = client.post("/solve", json={"time_limit_s": 1})
    assert r.status_code == 409
    d = _msg(r)
    assert GRAD in d and "time" in d and "infeasib" not in d
    assert client.store.get_setting("last_schedule") == stored


def test_a_proven_infeasible_solve_says_so(client, monkeypatch):
    _appended_then_unpublished(client)
    _stub_solve(monkeypatch, "INFEASIBLE")
    d = _msg(client.post("/solve", json={"time_limit_s": 1}))
    assert GRAD in d and "infeasib" in d


def test_an_invalid_model_is_not_reported_as_proven_infeasible(client, monkeypatch):
    _appended_then_unpublished(client)
    monkeypatch.setattr(
        api_mod, "solve",
        lambda *a, **k: SolveResult("MODEL_INVALID", None, None, None,
                                    detail="domain is empty"))
    d = _msg(client.post("/solve", json={"time_limit_s": 1}))
    assert "model is invalid" in d and "domain is empty" in d
    assert "infeasib" not in d


def test_a_real_invalid_model_says_invalid(client):
    _appended_then_unpublished(client)
    got = next(c for c in client.get("/catalog/courses").json()
               if c["number"] == "00580001")
    client.post("/catalog/courses", json={**got, "lecture_boxes": 11})
    r = client.post("/solve", json={"time_limit_s": 5})
    assert r.status_code == 409
    assert "infeasib" not in _msg(r)


def test_a_solve_never_runs_extra_solves_to_diagnose(client, monkeypatch):
    _appended_then_unpublished(client)
    calls = []
    def fake(*a, **k):
        calls.append(1)
        return SolveResult("UNKNOWN", None, None, None)
    monkeypatch.setattr(api_mod, "solve", fake)
    client.post("/solve", json={"time_limit_s": 1})
    assert len(calls) == 1


def _pin_into_small_room(client, room: str = "room3") -> None:
    """Move the held grad pin into a 50-seat room, whatever the solver chose."""
    for key in ("grad_pins", "last_schedule"):
        cur = client.store.get_setting(key)
        cur[GRAD] = {**cur[GRAD], "room_id": room}
        client.store.set_setting(key, cur)


def test_a_pinned_room_that_is_too_small_fails_instead_of_persisting_a_violation(client):
    _appended_then_unpublished(client)
    _pin_into_small_room(client)
    stored = client.store.get_setting("last_schedule")
    before = client.get("/export/csv").content
    client.post("/catalog/courses", json=_grad(expected_enrollment=BIG))
    r = client.post("/solve", json={"time_limit_s": 10})
    assert r.status_code == 409
    assert GRAD in _msg(r)
    assert client.store.get_setting("last_schedule") == stored
    assert client.get("/export/csv").content == before


def test_an_unrelated_hard_failure_is_diagnosed_not_blamed_on_the_grad_pin(client):
    _appended_then_unpublished(client)
    stored = client.store.get_setting("last_schedule")
    before = client.get("/export/csv").content
    client.post("/catalog/courses", json=_ug("00540009", expected_enrollment=1000))
    r = client.post("/solve", json={"time_limit_s": 10})
    assert r.status_code == 409
    d = r.json()["detail"]
    assert isinstance(d, dict)
    assert "no pinned graduate session appears in the listed violations" in d["message"]
    assert "not caused by the graduate pins" not in d["message"]
    assert GRAD not in d["message"].split(";")[0]
    kinds = {v["kind"] for v in d["violations"]}
    assert "capacity_exceeded" in kinds
    assert any(sid.startswith("00540009") for v in d["violations"]
               for sid in v["session_ids"])
    assert {"kind", "severity", "message", "session_ids"} <= set(d["violations"][0])
    assert any(sid.startswith("00540009") for sid in d["preview"])
    assert client.store.get_setting("last_schedule") == stored
    assert client.get("/export/csv").content == before


# 4 ---------------------------------------------------------------------- #

def test_releasing_needs_confirmation(client):
    _appended_then_unpublished(client)
    assert client.delete(f"/terms/{_term(client)}/grad-pins").status_code == 400
    assert client.get(f"/terms/{_term(client)}/grad-pins").json()["pinned"]


def test_a_release_lets_the_re_solve_move_the_grad_course(client):
    slot = _appended_then_unpublished(client)
    _make_pin_infeasible(client, slot)
    term = _term(client)

    r = client.delete(f"/terms/{term}/grad-pins", params={"confirm": True})
    assert r.status_code == 200 and r.json()["released"] == [GRAD]
    assert client.get(f"/terms/{term}/grad-pins").json()["pinned"] == {}

    s = client.post("/solve", json={"time_limit_s": 10})
    assert s.status_code == 200 and s.json()["solved"]
    moved = s.json()["placements"][GRAD]
    assert (moved["day"], moved["start_box"]) != (slot["day"], slot["start_box"])


# 5 ---------------------------------------------------------------------- #

def test_publishing_again_freezes_the_current_week_including_grad(client):
    slot = _appended_then_unpublished(client)
    client.post("/catalog/courses", json=_ug("00540002"))
    placements = client.post("/solve", json={"time_limit_s": 10}).json()["placements"]
    term = _term(client)

    r = client.post(f"/terms/{term}/publish", params={"confirm": True})
    assert r.status_code == 200
    frozen = client.store.get_setting("published_schedule")
    assert frozen[GRAD] == slot
    assert frozen == {sid: p for sid, p in placements.items()}
    assert client.get(f"/terms/{term}/grad-pins").json()["pinned"] == {}


# 6 -- every guard sees the pins -------------------------------------------- #

def _refused(client, r, before) -> None:
    assert r.status_code == 409, r.text
    assert "grad-pins" in r.json()["detail"] and GRAD in r.json()["detail"]
    assert "unpublish" not in r.json()["detail"]
    assert client.get("/export/csv").content == before


def test_evaluate_refuses_to_drop_a_grad_pinned_session(client):
    _appended_then_unpublished(client)
    before = client.get("/export/csv").content
    mine = {sid: p for sid, p in client.store.get_setting("last_schedule").items()
            if sid != GRAD}
    _refused(client, client.post("/evaluate", json={"placements": mine}), before)


def test_evaluate_refuses_to_move_a_grad_pinned_session(client):
    slot = _appended_then_unpublished(client)
    before = client.get("/export/csv").content
    moved = dict(client.store.get_setting("last_schedule"))
    moved[GRAD] = {**slot, "start_box": (slot["start_box"] + 3) % 8}
    r = client.post("/evaluate", json={"placements": moved})
    assert client.get("/export/csv").content == before
    assert any(v["kind"] == "published_moved" for v in r.json()["violations"]) \
        or r.status_code == 409


def test_deleting_the_course_of_a_grad_pin_is_refused(client):
    _appended_then_unpublished(client)
    before = client.get("/export/csv").content
    _refused(client, client.delete("/catalog/courses/00580001"), before)
    assert client.post("/solve", json={"time_limit_s": 10}).json()["placements"][GRAD]


def test_disabling_the_course_of_a_grad_pin_is_refused(client):
    _appended_then_unpublished(client)
    before = client.get("/export/csv").content
    got = next(c for c in client.get("/catalog/courses").json()
               if c["number"] == "00580001")
    _refused(client, client.post("/catalog/courses", json={**got, "offered": False}),
             before)


def _snapshot_save(client, tmp_path, name, edit):
    """Save the current state, then rewrite the saved JSON with `edit(payload)`."""
    import json
    save_id = client.post("/schedules", json={"name": name}).json()["id"]
    path = next((tmp_path / "saves").glob(f"*{save_id}*"))
    doc = json.loads(path.read_text(encoding="utf-8"))
    edit(doc["payload"])
    path.write_text(json.dumps(doc), encoding="utf-8")
    return save_id


def test_loading_a_snapshot_that_moves_a_grad_pin_is_refused(client, tmp_path):
    client.put("/config", json={"saves_dir": str(tmp_path / "saves")})
    slot = _appended_then_unpublished(client)

    def move(payload):
        payload["placements"][GRAD] = {**slot, "start_box": (slot["start_box"] + 3) % 8}
    save_id = _snapshot_save(client, tmp_path, "moved", move)
    before = client.get("/export/csv").content
    _refused(client, client.post(f"/schedules/{save_id}/load"), before)


def test_loading_a_snapshot_that_lacks_a_grad_pin_is_refused(client, tmp_path):
    client.put("/config", json={"saves_dir": str(tmp_path / "saves")})
    _appended_then_unpublished(client)
    save_id = _snapshot_save(client, tmp_path, "lacks",
                             lambda p: p["placements"].pop(GRAD))
    before = client.get("/export/csv").content
    _refused(client, client.post(f"/schedules/{save_id}/load"), before)


# 7 -- retries and cycles keep the pins ------------------------------------- #

def test_a_repeated_unpublish_keeps_the_pins(client):
    slot = _appended_then_unpublished(client)
    term = _term(client)
    r = client.delete(f"/terms/{term}/publish", params={"confirm": True})
    assert r.status_code == 200
    assert client.get(f"/terms/{term}/grad-pins").json()["pinned"] == {GRAD: slot}


def test_publish_then_unpublish_again_keeps_the_pins(client):
    slot = _appended_then_unpublished(client)
    term = _term(client)
    client.post(f"/terms/{term}/publish", params={"confirm": True})
    assert client.get(f"/terms/{term}/grad-pins").json()["pinned"] == {}
    r = client.delete(f"/terms/{term}/publish", params={"confirm": True})
    assert r.json()["grad_pinned"] == [GRAD]
    assert client.get(f"/terms/{term}/grad-pins").json()["pinned"] == {GRAD: slot}


# 8 -- a held pin survives metadata edits and retries ------------------------- #

def test_marking_a_pinned_course_provisional_is_refused_until_released(client):
    _appended_then_unpublished(client)
    term = _term(client)
    before = client.get("/export/csv").content
    got = next(c for c in client.get("/catalog/courses").json()
               if c["number"] == "00580001")
    r = client.post("/catalog/courses", json={**got, "provisional": True})
    assert r.status_code == 409
    assert "grad-pins" in r.json()["detail"] and GRAD in r.json()["detail"]
    assert client.get("/export/csv").content == before
    assert GRAD in client.get(f"/terms/{term}/grad-pins").json()["pinned"]
    # After an explicit release the same edit is fine.
    client.delete(f"/terms/{term}/grad-pins", params={"confirm": True})
    assert client.post("/catalog/courses",
                       json={**got, "provisional": True}).status_code == 200


def test_changing_a_pinned_course_out_of_the_grad_level_is_refused(client):
    _appended_then_unpublished(client)
    got = next(c for c in client.get("/catalog/courses").json()
               if c["number"] == "00580001")
    r = client.post("/catalog/courses", json={**got, "level": "ug"})
    assert r.status_code == 409 and "grad-pins" in r.json()["detail"]


def test_publish_keeps_every_held_pin_even_if_metadata_drifted(client):
    """Belt and braces: a pin whose course is no longer grad/provisional-clean."""
    slot = _appended_then_unpublished(client)
    term = _term(client)
    # Bypass the API guard, as a legacy store or direct edit would.
    got = next(c for c in client.store.list_courses() if c.number == "00580001")
    got.provisional = True
    client.store.upsert_course(got)
    r = client.post(f"/terms/{term}/publish", params={"confirm": True})
    assert r.status_code == 200
    assert client.store.get_setting("published_schedule")[GRAD] == slot


def test_unpublishing_an_unpublished_term_does_not_recreate_released_pins(client):
    _appended_then_unpublished(client)
    term = _term(client)
    client.delete(f"/terms/{term}/grad-pins", params={"confirm": True})
    r = client.delete(f"/terms/{term}/publish", params={"confirm": True})
    assert r.status_code == 200
    assert r.json()["grad_pinned"] == []
    assert client.get(f"/terms/{term}/grad-pins").json()["pinned"] == {}


def test_loading_a_snapshot_that_reintroduces_provisional_is_refused(client, tmp_path):
    client.put("/config", json={"saves_dir": str(tmp_path / "saves")})
    _appended_then_unpublished(client)

    def provisional(payload):
        for c in payload["courses"]:
            if c["number"] == "00580001":
                c["provisional"] = True
    save_id = _snapshot_save(client, tmp_path, "prov", provisional)
    before = client.get("/export/csv").content
    _refused(client, client.post(f"/schedules/{save_id}/load"), before)
    assert client.store.get_setting("grad_pins")


def test_loading_a_snapshot_that_changes_a_pin_level_is_refused(client, tmp_path):
    client.put("/config", json={"saves_dir": str(tmp_path / "saves")})
    _appended_then_unpublished(client)

    def ungrad(payload):
        for c in payload["courses"]:
            if c["number"] == "00580001":
                c["level"] = "ug"
    save_id = _snapshot_save(client, tmp_path, "lvl", ungrad)
    before = client.get("/export/csv").content
    _refused(client, client.post(f"/schedules/{save_id}/load"), before)
