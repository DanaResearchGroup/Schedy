"""FastAPI app — thin orchestration over the engine + store.

Pipeline the planner drives: maintain the catalog, import & validate a skeleton,
solve, review/edit, export. Business logic stays in the engine modules; this
layer only wires HTTP to them.
"""

from __future__ import annotations

import os
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import tempfile

from fastapi import Body, FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from . import catalog as catalog_mod
from . import catalog_io
from . import coi_io
from . import uploads
from .catalog import Cadence
from .archive import Archive, contained
from .calendar_engine import (
    SemesterCalendar,
    lost_sessions,
    order_inversions,
    realize,
    teaching_days_by_template,
    week_anchor,
)
from .domain import (
    BOX_MINUTES, BOXES_PER_DAY, DAY_START_MIN, CourseLevel, Schedule, SessionType,
)
from .evaluator import evaluate
from .exporters import to_csv, to_pdf
from .freeze import freeze_violations, refusal
from .parser import parse_rows, parse_skeleton
from .solver import solve
from .store import Store, TermId, course_from_dict, course_to_dict
from .validator import ChecklistItem, find_missing


def _parse_availability(raw) -> dict[str, set[tuple[int, int]]]:
    """person -> {(day, box)}; raises on any other shape."""
    return {p: {(int(d), int(b)) for d, b in cells} for p, cells in (raw or {}).items()}


def _load_availability(store: Store) -> dict[str, set[tuple[int, int]]]:
    return _parse_availability(store.get_setting("availability", {}))


def _normalized_catalog(courses) -> list:
    """The catalog exactly as the store will keep it: string keys, each once.

    The store keys courses by number as text, so ``540002`` and ``"540002"``
    are one row and the last write wins. Validating a catalog that is not the
    one stored lets a duplicate or a numeric key slip past the freeze guard.
    """
    out, seen = [], set()
    for c in courses:
        if c.number is None or not str(c.number).strip():
            raise ValueError("a course has no number")
        c = replace(c, number=str(c.number))
        if c.number in seen:
            raise ValueError(f"duplicate course number {c.number}")
        seen.add(c.number)
        out.append(c)
    return out


def _stored_courses(store: Store, term: str | None = None) -> list:
    """The stored catalog with every number as text (legacy rows may be int)."""
    return [replace(c, number=str(c.number)) for c in store.list_courses(term)]


def _calendar_from_dict(raw: dict) -> SemesterCalendar:
    """Parse the stored calendar JSON (ISO date strings) into the engine type."""
    return SemesterCalendar(
        start=date.fromisoformat(raw["start"]),
        end=date.fromisoformat(raw["end"]),
        blocked_dates={date.fromisoformat(d) for d in raw.get("blocked_dates", [])},
        substitutions={
            date.fromisoformat(d): int(t)
            for d, t in (raw.get("substitutions") or {}).items()
        },
    )


def _stored_week_anchor(store: Store) -> int:
    """Weekday the stored semester actually starts teaching on (Sunday if unset).

    Order-sensitive rules rank days from here. A calendar that is missing or
    half-entered simply leaves the default Sunday-first week in place rather
    than blocking a solve.
    """
    raw = store.get_setting("calendar")
    if not raw:
        return 0
    try:
        return week_anchor(_calendar_from_dict(raw))
    except (KeyError, TypeError, ValueError):
        return 0


_KEEP = object()   # "leave this setting as stored"


def _baseline(store: Store) -> dict:
    """Every placement a write may not change: the published week, plus the
    graduate sessions kept as pins since an unpublish. A published pin wins."""
    return {**(store.get_setting("grad_pins") or {}),
            **(store.get_setting("published_schedule") or {})}


def _pins(store: Store) -> dict | None:
    return _baseline(store) or None


def _problem(store: Store):
    return catalog_mod.expand(
        store.list_courses(),
        offered_rows=store.get_setting("offered_rows") or None,
        availability=_load_availability(store),
        week_anchor=_stored_week_anchor(store),
        pins=_pins(store),
    )


def _schedule_from(problem, placements: dict) -> Schedule:
    """Rebuild a Schedule from stored placements, ignoring stale session ids."""
    known = {s.id for s in problem.sessions}
    sched = Schedule()
    for sid, p in placements.items():
        if sid in known:
            sched.place(sid, int(p["day"]), int(p["start_box"]), p["room_id"])
    return sched


def _published_missing(store: Store, problem) -> list[str]:
    """Published sessions the catalog no longer produces.

    A session that does not exist breaks no rule, so deleting a published course
    — or renaming an exercise group, which changes the session id — would drop it
    from the frozen schedule in silence. This is the only thing that says so.
    """
    pinned = store.get_setting("published_schedule") or {}
    if not pinned:
        return []
    have = {s.id for s in problem.sessions}
    return sorted(sid for sid in pinned if sid not in have)


def _published_conflicts(store: Store, problem) -> list[dict]:
    """Published sessions the university skeleton now wants somewhere else.

    A published pin overrides the skeleton's, because it is what the students
    were told. But the skeleton is the university moving a slot, and it only
    changes after publication when something real has changed — so the planner
    has to be told rather than have one quietly win.
    """
    pinned = store.get_setting("published_schedule") or {}
    rows = store.get_setting("offered_rows") or []
    if not pinned or not rows:
        return []
    skeleton = catalog_mod.offered_placements(rows)
    by_id = {s.id: s for s in problem.sessions}
    out: list[dict] = []
    for sid, p in pinned.items():
        s = by_id.get(sid)
        if s is None:
            continue  # already reported as missing
        # Same resolution the expansion uses, so the two cannot drift apart.
        want = catalog_mod.skeleton_slot(skeleton, s.course_number, s.type.value, s.group)
        if want[0] is not None and want != (int(p["day"]), int(p["start_box"])):
            out.append({"session_id": sid, "published": [int(p["day"]),
                                                         int(p["start_box"])],
                        "skeleton": [want[0], want[1]]})
    return sorted(out, key=lambda d: d["session_id"])


def _session_meta(problem, grad_pinned=frozenset()) -> dict:
    """Per-session metadata the grid needs to render readable, filterable blocks."""
    out: dict[str, dict] = {}
    for s in problem.sessions:
        out[s.id] = {
            "course_number": s.course_number,
            "type": s.type.value,
            "group": s.group,
            "length_boxes": s.length_boxes,
            "role": s.role.value,
            "cohorts": sorted(c.label for c in s.cohorts),
            "lecturers": list(s.lecturer_ids),
            "tas": list(s.ta_ids),
            "is_remote": s.is_remote,
            "fixed": s.is_fixed,
            "published": s.is_published and s.id not in grad_pinned,
            "grad_pinned": s.id in grad_pinned,
            "provisional": s.provisional,
            "level": s.level.value,
            "enrollment": s.expected_enrollment,
            "needs_farm": s.needs_computer_farm,
            "lab_group": s.lab_group,
        }
    return out


def _fixed_event_dicts(problem) -> list[dict]:
    """Immovable walls (blackouts + external courses) snapped to the box grid."""
    import math
    out: list[dict] = []
    for fe in problem.fixed_events:
        start_box = max(0, (fe.start_min - DAY_START_MIN) // BOX_MINUTES)
        end_box = math.ceil((fe.end_min - DAY_START_MIN) / BOX_MINUTES)
        if start_box >= BOXES_PER_DAY:
            continue
        length = min(max(1, end_box - start_box), BOXES_PER_DAY - start_box)
        out.append({
            "id": fe.id, "label": fe.label, "day": fe.day,
            "start_box": int(start_box), "length_boxes": int(length),
            "kind": "blackout" if fe.is_blackout else "external",
            "cohorts": sorted(c.label for c in fe.cohorts),
            # Another faculty's graduate course owns no cohort of ours, so the
            # level is the only thing that ties it to our graduate courses —
            # the drag hint and the grid's audience filter both need it.
            "level": fe.level.value if fe.level else None,
        })
    return out


def _violation_dicts(evaluation) -> list[dict]:
    return [
        {"kind": v.kind, "severity": v.severity, "message": v.message,
         "session_ids": list(v.session_ids), "weight": v.weight}
        for v in evaluation.violations
    ] if evaluation else []


def create_app(store: Store | None = None) -> FastAPI:
    store = store or Store(os.environ.get("SCHEDY_DB", "schedy.sqlite"))
    app = FastAPI(title="Schedy", version="0.1.0")
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
    )
    app.state.store = store

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "courses": len(store.list_courses())}

    # ---- terms ------------------------------------------------------ #
    def _terms_body() -> dict:
        return {
            "terms": store.list_terms(),
            "current": store.current_term(),
            # Migration has to name a pre-term database before any UI exists, so
            # the name it chose is a guess the planner still has to confirm.
            "needs_naming": store.get_global("term_needs_naming"),
        }

    def _term_id(year, semester) -> TermId:
        try:
            return TermId(str(year or ""), str(semester or ""))
        except ValueError as exc:
            raise HTTPException(400, str(exc))

    def _term_row(term: str) -> dict:
        for row in store.list_terms():
            if row["id"] == term:
                return row
        raise HTTPException(404, f"no such term {term}")

    @app.get("/terms")
    def list_terms() -> dict:
        return _terms_body()

    @app.post("/terms")
    def create_term(payload: dict = Body(...)) -> dict:
        """Open a new academic year + semester, empty and not current.

        Creating does not switch: the planner opens next year's term long before
        they are ready to stop working on this one.
        """
        t = _term_id(payload.get("year"), payload.get("semester"))
        try:
            store.create_term(t.year, t.semester)
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        # Pre-fill availability from the same semester last year (PRD D6): a
        # lecturer's commitments are usually stable but not permanent, so the
        # new term gets its own editable copy rather than sharing one.
        previous = store.get_setting("availability", term=str(t.previous_year()))
        if previous:
            store.set_setting("availability", previous, term=str(t))
        return _term_row(str(t))

    @app.get("/terms/current")
    def get_current_term() -> dict:
        return _term_row(store.current_term())

    @app.put("/terms/current")
    def set_current_term(payload: dict = Body(...)) -> dict:
        """Switch which term every other route reads and writes.

        Single-planner app: this moves the whole session, not one request.
        """
        term = str(payload.get("term") or "")
        try:
            store.set_current_term(term)
        except KeyError:
            raise HTTPException(404, f"no such term {term}")
        return _term_row(term)

    # Declared after /terms/current on purpose: FastAPI matches in declaration
    # order, and "current" would otherwise be read as a term to rename.
    @app.put("/terms/{term}")
    def rename_term(term: str, payload: dict = Body(...)) -> dict:
        """Re-label a term, keeping its catalog and settings.

        This is how a guessed migration name gets corrected — and confirming the
        guess unchanged is a rename to itself, which clears the prompt.
        """
        t = _term_id(payload.get("year"), payload.get("semester"))
        try:
            new = store.rename_term(term, t.year, t.semester)
        except KeyError:
            raise HTTPException(404, f"no such term {term}")
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        return _term_row(new)

    # ---- rollover ---------------------------------------------------- #
    def _rollover_candidates(term: str) -> tuple[str, list[dict]]:
        """Graduate-level courses to stand in for this term's, and where from.

        Looks back one year at a time in the *same* semester, so the planner is
        comparing like with like. A biennial course that ran last year is listed
        but not due — this is its off year — while one that ran two years ago is
        both listed and due. Anything already in this term's catalog is settled
        and needs no stand-in.
        """
        here = TermId.parse(term)
        have = {c.number for c in store.list_courses(term)}
        seen: dict[str, dict] = {}
        source = str(here.previous_year())
        back = here
        for years in (1, 2):
            back = back.previous_year()
            for c in store.list_courses(str(back)):
                # `offered=False` means it did not run, so it is no evidence.
                if not c.is_grad_level or not c.offered or c.number in have:
                    continue
                if c.number in seen:
                    continue  # the more recent year already spoke for it
                due = c.cadence is Cadence.ANNUAL or years == 2
                seen[c.number] = {**course_to_dict(c), "last_run": str(back),
                                  "due": due}
        return source, [seen[n] for n in sorted(seen)]

    @app.get("/terms/current/rollover")
    def rollover_preview() -> dict:
        source, courses = _rollover_candidates(store.current_term())
        return {"source": source, "courses": courses}

    @app.post("/terms/current/rollover")
    def rollover_apply(payload: dict = Body(...)) -> dict:
        """Copy the chosen courses in as provisional stand-ins for phase 1.

        They are ordinary graduate courses as far as the solver is concerned —
        which is the point: they carry the hard non-overlap rule, so joint
        courses are genuinely pushed out of the hours being reserved.
        """
        _, courses = _rollover_candidates(store.current_term())
        by_number = {c["number"]: c for c in courses}
        wanted = [str(n) for n in payload.get("numbers", [])]
        unknown = [n for n in wanted if n not in by_number]
        if unknown:
            raise HTTPException(400, f"not available to roll over: {', '.join(unknown)}")
        for n in wanted:
            src = {k: v for k, v in by_number[n].items()
                   if k not in ("last_run", "due")}
            store.upsert_course(course_from_dict({**src, "provisional": True}))
        return {"added": wanted}

    # ---- publish / freeze ------------------------------------------- #
    def _open_term(term: str) -> dict:
        """The term to publish must be the one open — nothing else is readable.

        Every setting the freeze reads (the solved schedule, the catalog) is
        scoped to the current term, so publishing another one would freeze this
        one's week under that one's name.
        """
        row = store.get_term(term)
        if row is None:
            raise HTTPException(404, f"no such term {term}")
        if term != store.current_term():
            raise HTTPException(409, f"open {term} before publishing it")
        return row

    @app.post("/terms/{term}/publish")
    def publish_term(term: str, confirm: bool = False) -> dict:
        """Freeze the undergraduate and joint week, and stamp the term released.

        Graduate courses are deliberately left fluid: the department publishes
        the undergraduate timetable months before it knows which graduate courses
        will run, and phase 2 places those around what is frozen here (PRD D8).
        """
        row = _open_term(term)
        if not confirm:
            raise HTTPException(400, "publishing requires ?confirm=true")
        # A second publish would re-derive the pins from today's catalog and
        # silently unpin whatever has since become provisional or graduate.
        if row.get("published"):
            raise HTTPException(409, f"{term} is already published; unpublish first")

        placements = store.get_setting("last_schedule") or {}
        if not placements:
            raise HTTPException(409, "nothing to publish; POST /solve first")

        problem = _problem(store)
        by_id = {s.id: s for s in problem.sessions}
        # Graduate courses stay fluid for phase 2 — and so do provisional
        # stand-ins, whatever their level. Rollover copies in graduate-*level*
        # courses, so a joint stand-in is not GRAD and would otherwise be pinned
        # to a day, an hour and a room before anyone confirmed it runs. Phase 2
        # then refuses to start until the stand-ins are settled, leaving the
        # planner unpublishing a whole week to take back a guess.
        # Graduate courses kept as pins since an unpublish are the exception:
        # they already hold a slot, so publishing freezes the week as it stands.
        kept = store.get_setting("grad_pins") or {}
        # A held pin is never dropped, whatever the course's metadata says now:
        # the catalog guard refuses such edits, this keeps legacy stores safe.
        freeze = {sid: s for sid, s in by_id.items()
                  if sid in kept or (not s.provisional
                                     and s.level is not CourseLevel.GRAD)}

        # An unplaced session raises no violation, so it would be frozen out of
        # existence rather than frozen in place.
        unplaced = sorted(sid for sid in freeze if sid not in placements)
        if unplaced:
            raise HTTPException(
                409, f"unplaced session(s) cannot be published: {', '.join(unplaced)}")

        evaluation = evaluate(problem, _schedule_from(problem, placements))
        hard = [v for v in evaluation.violations if v.severity == "hard"]
        if hard:
            raise HTTPException(
                409, f"schedule has {len(hard)} hard conflict(s); fix them before "
                     "publishing")

        pinned = {sid: {"day": int(placements[sid]["day"]),
                        "start_box": int(placements[sid]["start_box"]),
                        "room_id": placements[sid]["room_id"]}
                  for sid in freeze}
        store.set_setting("published_schedule", pinned)
        store.set_setting("grad_pins", {})
        # An instant, not a day: a term can be published, released and published
        # again inside one afternoon, and a bare local date tells those apart
        # neither by time nor by order — nor says which clock it was read from.
        store.set_published(term, datetime.now(timezone.utc).isoformat(timespec="seconds"))
        return {**store.get_term(term), "frozen": len(pinned)}

    @app.delete("/terms/{term}/publish")
    def unpublish_term(term: str, confirm: bool = False) -> dict:
        """Release the freeze so the whole week can move again.

        Anything already handed to students then stops being a promise, so this
        is deliberately explicit rather than a side effect of editing.

        Graduate-level sessions placed at this moment are the exception to
        "everything moves": they stay where they are, as pins guarded like
        published ones, so the next solve places the undergraduate week around
        them or fails loudly (see ``run_solve``). The level decides, not any
        record of how a course got there, so retries and publish cycles agree.
        ``DELETE /terms/{term}/grad-pins`` releases them.
        """
        row = _open_term(term)
        if not confirm:
            raise HTTPException(400, "un-publishing requires ?confirm=true")
        if not row.get("published"):
            # Nothing is being released: deriving pins now would resurrect any
            # the planner explicitly let go of.
            kept = store.get_setting("grad_pins") or {}
            return {**row, "grad_pinned": sorted(kept)}
        placements = store.get_setting("last_schedule") or {}
        by_id = {s.id: s for s in _problem(store).sessions}
        derived = {sid: {"day": int(placements[sid]["day"]),
                         "start_box": int(placements[sid]["start_box"]),
                         "room_id": placements[sid]["room_id"]}
                   for sid, s in by_id.items()
                   if s.level is CourseLevel.GRAD and not s.provisional
                   and sid in placements}
        # Pins already held win: a retry must never shrink them.
        kept = {**derived, **(store.get_setting("grad_pins") or {})}
        store.set_setting("grad_pins", kept)
        store.set_setting("published_schedule", {})
        store.set_published(term, None)
        return {**store.get_term(term), "grad_pinned": sorted(kept)}

    @app.get("/terms/{term}/grad-pins")
    def get_grad_pins(term: str) -> dict:
        """Graduate placements kept as hard pins since the last unpublish."""
        _open_term(term)
        return {"pinned": store.get_setting("grad_pins") or {}}

    @app.delete("/terms/{term}/grad-pins")
    def release_grad_pins(term: str, confirm: bool = False) -> dict:
        """Let the next solve move the kept graduate courses."""
        _open_term(term)
        if not confirm:
            raise HTTPException(400, "releasing graduate pins requires ?confirm=true")
        released = sorted(store.get_setting("grad_pins") or {})
        store.set_setting("grad_pins", {})
        return {"released": released}

    def _meta(problem) -> dict:
        return _session_meta(problem, frozenset(store.get_setting("grad_pins") or {}))

    def _refuse_if_grad_pins_unfit(result, problem) -> None:
        """409 when graduate pins are held and the solve did not honour them all.

        Pins are hard, so a clean solve keeps every one. Anything else — no
        schedule (proven infeasible, or out of time) or a best-effort one with
        hard violations (a pinned room too small) — is refused rather than
        persisted. No extra solves: the one result already says what happened.
        """
        grad = store.get_setting("grad_pins") or {}
        published = store.get_setting("published_schedule") or {}
        grad = {sid for sid in grad if sid not in published}
        if not grad or (result.solved and result.evaluation.is_feasible):
            return
        term = store.current_term()
        hard = [v for v in (result.evaluation.violations if result.solved else [])
                if v.severity.lower() == "hard"]
        blamed = sorted({sid for v in hard for sid in v.session_ids} & grad)
        release = (f"release them with DELETE /terms/{term}/grad-pins?confirm=true "
                   "to let a solve move them")
        not_pins = ("; this is not caused by the graduate pins, so releasing them "
                    "will not fix it")
        if result.solved and blamed:
            msg = ("graduate session(s) cannot keep their slots: " + ", ".join(blamed)
                   + "; the best schedule found still breaks hard rules ("
                   + ", ".join(sorted({v.kind for v in hard})) + f"). Fix the clash, or {release}")
        elif result.solved:
            msg = ("the best schedule found breaks hard rules ("
                   + ", ".join(sorted({v.kind for v in hard})) + "); no pinned "
                   "graduate session appears in the listed violations, but a pin can "
                   "still crowd other courses (a shared lecturer or room). Fix the "
                   f"listed violations first; if that fails, {release}")
        elif result.status == "MODEL_INVALID":
            msg = (f"the model is invalid: {result.detail or 'no reason given'}"
                   + not_pins)
        elif result.status == "UNKNOWN":
            msg = ("graduate session(s) held as pins: " + ", ".join(sorted(grad))
                   + "; the solver ran out of time before finding any schedule")
        elif result.status == "INFEASIBLE":
            msg = ("graduate session(s) held as pins: " + ", ".join(sorted(grad))
                   + f"; the solver proved the week infeasible with them pinned. "
                   f"Fix the clash, or {release}")
        else:
            msg = f"the solver stopped with status {result.status}" + not_pins
        preview = ({sid: {"day": p.day, "start_box": p.start_box, "room_id": p.room_id}
                    for sid, p in result.schedule.placements.items()}
                   if result.solved else {})
        # Nothing is persisted: the preview only lets the planner see why.
        raise HTTPException(409, {"message": msg,
                                  "violations": _violation_dicts(result.evaluation)
                                  if result.solved else [],
                                  "preview": preview})

    def _candidate_problem(courses, offered_rows=_KEEP, availability=_KEEP):
        """The Problem the catalog would expand to if `courses` replaced it."""
        rows = (store.get_setting("offered_rows")
                if offered_rows is _KEEP else offered_rows)
        avail = (_load_availability(store) if availability is _KEEP
                 else _parse_availability(availability))
        return catalog_mod.expand(
            courses, offered_rows=rows or None,
            availability=avail,
            week_anchor=_stored_week_anchor(store),
            pins=_pins(store))

    def _refusal(bad, what: str) -> str:
        published = store.get_setting("published_schedule") or {}
        return refusal(bad, what, grad_only=[sid for sid, _ in bad
                                             if sid not in published],
                       term=store.current_term())

    def _refuse_if_unfrozen(what: str, problem, schedule: Schedule) -> None:
        """409 if the candidate would move or lose a published or grad-pinned session."""
        frozen = _baseline(store)
        bad = freeze_violations(frozen, problem, schedule) if frozen else []
        if bad:
            raise HTTPException(409, _refusal(bad, what))

    def _refuse_if_lost(problem, schedule: Schedule) -> None:
        frozen = _baseline(store)
        lost = [v for v in freeze_violations(frozen, problem, schedule)
                if v[1] == "missing"] if frozen else []
        if lost:
            raise HTTPException(409, _refusal(lost, "that schedule"))

    def _refuse_if_pins_drift(what: str, problem) -> None:
        """409 if a held graduate pin would stop being a confirmed graduate course.

        A pin only stays a pin while its session is graduate-level and not
        provisional; otherwise the next publish would silently drop it.
        """
        held = set(store.get_setting("grad_pins") or {}) - set(
            store.get_setting("published_schedule") or {})
        drifted = [(s.id, "no longer a confirmed graduate course")
                   for s in problem.sessions if s.id in held
                   and (s.provisional or s.level is not CourseLevel.GRAD)]
        if drifted:
            raise HTTPException(409, _refusal(drifted, what))

    def _refuse_if_catalog_loses_sessions(what: str, courses,
                                          offered_rows=_KEEP) -> None:
        """409 if replacing the catalog/skeleton would drop a published session.

        Only the session definitions are in question here, so the baseline
        stands in for the schedule: a stale `last_schedule` is not this write's
        doing.
        """
        frozen = _baseline(store)
        if not frozen:
            return
        problem = _candidate_problem(courses, offered_rows)
        _refuse_if_pins_drift(what, problem)
        sched = Schedule()
        for sid, pin in frozen.items():
            sched.place(sid, int(pin["day"]), int(pin["start_box"]), pin["room_id"])
        _refuse_if_unfrozen(what, problem, sched)

    # ---- reset ------------------------------------------------------ #
    @app.post("/reset")
    def reset_everything(confirm: bool = False) -> dict:
        """Erase the current term's catalog and settings — back to a first run.

        Scoped to the term in hand: other terms, and the department-wide faculty
        registry, are untouched. Irreversible, so it is gated twice: the UI asks
        the planner to approve, and the request itself must carry
        ``?confirm=true``. Saved schedule files on disk are left alone.
        """
        if not confirm:
            raise HTTPException(400, "reset requires ?confirm=true")
        cleared = store.reset(keep_settings=("saves_dir",))
        return {"reset": True, **cleared}

    # ---- catalog ---------------------------------------------------- #
    @app.get("/catalog/courses")
    def list_courses() -> list[dict]:
        return [course_to_dict(c) for c in store.list_courses()]

    @app.post("/catalog/courses")
    def upsert_course(payload: dict = Body(...)) -> dict:
        try:
            course = _normalized_catalog([course_from_dict(payload)])[0]
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(400, f"invalid course: {exc}")
        _refuse_if_catalog_loses_sessions(
            "that course change",
            [c for c in _stored_courses(store) if c.number != course.number] + [course])
        store.upsert_course(course)
        return course_to_dict(course)

    @app.delete("/catalog/courses/{number}")
    def delete_course(number: str) -> dict:
        _refuse_if_catalog_loses_sessions(
            "deleting that course",
            [c for c in _stored_courses(store) if c.number != number])
        store.delete_course(number)
        return {"deleted": number}

    @app.post("/catalog/seed")
    def seed_catalog(force: bool = False) -> dict:
        """Load the illustrative demo catalog (first-run onboarding)."""
        from .sample_data import sample_courses
        existing = store.list_courses()
        if existing and not force:
            raise HTTPException(409, "catalog not empty; pass ?force=true to replace")
        courses = sample_courses()
        _refuse_if_catalog_loses_sessions("seeding the demo catalog", courses)
        for c in existing:
            store.delete_course(c.number)
        for c in courses:
            store.upsert_course(c)
        return {"seeded": len(courses)}

    # ---- catalog file import/export -------------------------------- #
    def _csv_download(text: str, filename: str) -> Response:
        return Response(
            ("﻿" + text).encode("utf-8"),  # BOM so Excel renders Hebrew
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    @app.get("/catalog/export.csv")
    def export_catalog() -> Response:
        """Download the whole catalog as a CSV (versionable, Excel-editable)."""
        return _csv_download(catalog_io.to_csv(store.list_courses()), "schedy-catalog.csv")

    @app.get("/catalog/template.csv")
    def catalog_template() -> Response:
        """Download a documented example file showing the required format."""
        return _csv_download(catalog_io.template_csv(), "schedy-catalog-template.csv")

    @app.post("/catalog/import")
    async def import_catalog(file: UploadFile = File(...)) -> dict:
        """Load a catalog version from a CSV/Excel file, replacing the current one."""
        data = await file.read()
        name = file.filename or ""
        try:
            uploads.reject_legacy_xls(name)
            if uploads.is_excel(name):
                courses = catalog_io.from_xlsx_bytes(data)
            else:
                courses = catalog_io.from_csv(data.decode("utf-8-sig"))
            courses = _normalized_catalog(courses)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(400, f"could not parse catalog file: {exc}")
        if not courses:
            raise HTTPException(400, "no courses found in the file")
        _refuse_if_catalog_loses_sessions("that import", courses)
        for c in store.list_courses():
            store.delete_course(c.number)
        for c in courses:
            store.upsert_course(c)
        return {"imported": len(courses)}

    # ---- availability ---------------------------------------------- #
    @app.get("/availability")
    def get_availability() -> dict:
        """Stored unavailability: person -> list of [day, box] cells they can't teach."""
        return store.get_setting("availability", {}) or {}

    @app.put("/availability")
    def set_availability(payload: dict = Body(...)) -> dict:
        store.set_setting("availability", payload)
        return {"people": list(payload.keys())}

    # ---- semester calendar (dates overlay) ------------------------- #
    @app.get("/calendar")
    def get_calendar() -> dict:
        """Stored semester calendar (start/end/blocked_dates/substitutions)."""
        return store.get_setting("calendar", {}) or {}

    @app.put("/calendar")
    def set_calendar(payload: dict = Body(...)) -> dict:
        try:
            _calendar_from_dict(payload)  # validate it parses
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(400, f"invalid calendar: {exc}")
        store.set_setting("calendar", payload)
        return {"ok": True}

    @app.get("/calendar/analyze")
    def analyze_calendar() -> dict:
        """Realize the stored calendar and report deficits against the last solve."""
        raw = store.get_setting("calendar")
        if not raw:
            raise HTTPException(404, "no calendar set; PUT /calendar first")
        cal = _calendar_from_dict(raw)
        days = realize(cal)
        teaching = teaching_days_by_template(cal)

        lost: list = []
        inversions: list = []
        if store.get_setting("last_schedule"):
            problem, sched = _last_schedule()
            lost = lost_sessions(cal, sched, problem)
            inversions = order_inversions(cal, sched, problem)

        return {
            "total_days": len(days),
            "teaching_days": sum(1 for d in days if d.is_teaching),
            "weeks": (days[-1].week_index + 1) if days else 0,
            # Weekday the teaching week starts on — what ordering rules rank from.
            "week_anchor": week_anchor(cal),
            "template_counts": {t: len(ds) for t, ds in teaching.items()},
            "substituted_days": [
                {"date": d.date.isoformat(), "template": d.template}
                for d in days if d.substituted and d.is_teaching
            ],
            "blocked_count": sum(1 for d in days if not d.is_teaching and d.template is not None),
            "lost_sessions": [
                {"session_id": l.session_id, "course_number": l.course_number,
                 "weekday_template": l.weekday_template, "realized": l.realized,
                 "baseline": l.baseline, "deficit": l.deficit}
                for l in lost
            ],
            "order_inversions": [
                {"course_number": o.course_number, "week_index": o.week_index,
                 "lecture_date": o.lecture_date.isoformat(),
                 "exercise_date": o.exercise_date.isoformat(),
                 "exercise_group": o.exercise_group,
                 "cause": o.cause, "weeks": o.weeks,
                 "lecture_box": o.lecture_box,
                 "exercise_box": o.exercise_box}
                for o in inversions
            ],
        }

    # ---- skeleton import + validate -------------------------------- #
    @app.post("/skeleton/parse")
    def skeleton_parse(payload: dict = Body(...)) -> list[dict]:
        header = payload["header"]
        rows = payload["rows"]
        relevant = payload.get("relevant_course_numbers")
        offered = parse_rows(header, rows, set(relevant) if relevant else None)
        return [
            {"course_number": s.course_number, "event_type":
             s.event_type.value if s.event_type else None,
             "group_code": s.group_code, "day": s.day,
             "start_min": s.start_min, "end_min": s.end_min,
             "room": s.room, "row": s.row}
            for s in offered
        ]

    @app.post("/skeleton/upload")
    async def skeleton_upload(file: UploadFile = File(...)) -> dict:
        """Upload a Technion skeleton XLSX, filtered to our courses of interest.

        The university-wide file is thousands of rows; the interest list is the
        few dozen course numbers the department maintains by hand. Only those
        survive, and for each surviving row the whole record is kept.
        """
        data = await file.read()
        try:
            uploads.reject_legacy_xls(file.filename or "")
        except ValueError as exc:
            raise HTTPException(400, f"could not parse skeleton: {exc}")
        relevant = _interest_numbers()
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp.write(data)
            path = tmp.name
        try:
            # Parse the whole skeleton once; keep the full course-number set (for
            # the courses-of-interest check against the university-wide file),
            # then filter to the interest list for the rows that drive the solve.
            all_offered = parse_skeleton(path, None)
            offered = [s for s in all_offered if s.course_number in relevant]
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(400, f"could not parse skeleton: {exc}")
        finally:
            os.unlink(path)
        new_rows = [
            {"course_number": s.course_number,
             "event_type": s.event_type.value if s.event_type else None,
             "group_code": s.group_code, "name_he": s.name_he, "name_en": s.name_en,
             "day": s.day, "start_min": s.start_min, "end_min": s.end_min,
             "room": s.room, "package": s.package, "row": s.row,
             "faculty": s.faculty, "language": s.language, "person": s.person,
             "details": s.details,
             "pinned": catalog_mod.pinnable(s.day, s.start_min)}
            for s in offered
        ]
        _refuse_if_catalog_loses_sessions("that skeleton", _stored_courses(store), new_rows)
        store.set_setting("skeleton_course_numbers",
                          sorted({s.course_number for s in all_offered}))
        store.set_setting("offered_rows", new_rows)
        out = {"count": len(offered), "offered": store.get_setting("offered_rows")}
        if not relevant:
            # Not an error: the file parsed, and the university-wide course
            # numbers are stored so the checklist still works. There is simply
            # nothing yet that says which of them we care about.
            out["warning"] = "no_courses_of_interest"
        return out

    @app.get("/skeleton/rows")
    def get_skeleton_rows() -> list[dict]:
        """The stored (possibly hand-edited) offered rows that drive the solve."""
        return store.get_setting("offered_rows") or []

    @app.put("/skeleton/rows")
    def put_skeleton_rows(payload: dict = Body(...)) -> dict:
        """Persist hand-edited offered rows; pin status is recomputed server-side."""
        rows = payload.get("rows", [])
        norm = []
        for r in rows:
            day = r.get("day")
            day = int(day) if day is not None and day != "" else None
            start = r.get("start_min")
            start = int(start) if start is not None and start != "" else None
            norm.append({**r, "day": day, "start_min": start,
                         "pinned": catalog_mod.pinnable(day, start)})
        _refuse_if_catalog_loses_sessions("those skeleton rows",
                                          _stored_courses(store), norm)
        store.set_setting("offered_rows", norm)
        return {"count": len(norm), "offered": norm}

    @app.delete("/skeleton/rows")
    def clear_skeleton_rows() -> dict:
        """Remove all imported skeleton rows (a fresh import starts clean)."""
        _refuse_if_catalog_loses_sessions("clearing the skeleton",
                                          _stored_courses(store), [])
        store.set_setting("offered_rows", [])
        store.set_setting("skeleton_course_numbers", None)
        return {"count": 0, "offered": []}

    @app.get("/skeleton/course-numbers")
    def skeleton_course_numbers() -> dict:
        """Every course number in the imported (university-wide) skeleton.

        Powers the courses-of-interest check, which must see the full file —
        not the catalog-filtered subset that drives the solve.
        """
        nums = store.get_setting("skeleton_course_numbers")
        return {"imported": nums is not None, "numbers": nums or []}

    @app.get("/people")
    def get_people() -> list[dict]:
        """The faculty registry: canonical lecturers & TAs (name + kind)."""
        return store.get_setting("people") or []

    @app.put("/people")
    def put_people(payload: dict = Body(...)) -> list[dict]:
        import re
        out: list[dict] = []
        used: set[str] = set()
        for it in payload.get("items", []):
            name = str(it.get("name", "")).strip()
            kind = it.get("kind") if it.get("kind") in ("faculty", "grad") else "faculty"
            pid = str(it.get("id", "")).strip() or re.sub(r"\s+", "-", name.lower()).strip("-")
            if not pid:
                continue  # nothing to key on
            base, n = pid, 2
            while pid in used:
                pid, n = f"{base}-{n}", n + 1
            used.add(pid)
            out.append({"id": pid, "name": name or pid, "kind": kind})
        store.set_setting("people", out)
        return out

    @app.post("/people/import-from-catalog")
    def import_people_from_catalog() -> list[dict]:
        """Seed/merge the registry from staff already named on courses."""
        by_id = {p["id"]: p for p in (store.get_setting("people") or [])}
        for c in store.list_courses():
            for lid in c.lecturer_ids:
                by_id.setdefault(lid, {"id": lid, "name": lid, "kind": "faculty"})
            for tid in c.ta_ids:
                by_id.setdefault(tid, {"id": tid, "name": tid, "kind": "grad"})
        merged = list(by_id.values())
        store.set_setting("people", merged)
        return merged

    # ---- courses of interest --------------------------------------- #
    # The hand-maintained list of course numbers the department cares about. It
    # is what filters the university-wide skeleton on import, so it is a real
    # input file — importable, exportable, and templated like the catalog.
    def _interest_numbers() -> set[str]:
        return {it["number"] for it in (store.get_setting("courses_of_interest") or [])
                if it.get("number")}

    @app.get("/courses-of-interest")
    def get_courses_of_interest() -> list[dict]:
        """Our course numbers; the filter applied to the skeleton on import."""
        return store.get_setting("courses_of_interest") or []

    @app.put("/courses-of-interest")
    def put_courses_of_interest(payload: dict = Body(...)) -> list[dict]:
        items = []
        for it in payload.get("items", []):
            number = coi_io.normalize_number(it.get("number", ""))
            if number:
                items.append({"number": number, "name": str(it.get("name", "")).strip()})
        store.set_setting("courses_of_interest", items)
        return items

    @app.get("/courses-of-interest/export.csv")
    def export_courses_of_interest() -> Response:
        """Download the current list, to version it or carry it to next year."""
        return _csv_download(
            coi_io.to_csv(store.get_setting("courses_of_interest") or []),
            "schedy-courses-of-interest.csv")

    @app.get("/courses-of-interest/template.csv")
    def courses_of_interest_template() -> Response:
        """Download a documented example file showing the expected format."""
        return _csv_download(coi_io.template_csv(),
                             "schedy-courses-of-interest-template.csv")

    @app.post("/courses-of-interest/import")
    async def import_courses_of_interest(file: UploadFile = File(...)) -> list[dict]:
        """Load the list from a CSV/Excel file, replacing the current one."""
        data = await file.read()
        try:
            items = coi_io.from_upload(data, file.filename or "")
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(400, f"could not parse courses-of-interest file: {exc}")
        if not items:
            raise HTTPException(400, "no course numbers found in the file")
        store.set_setting("courses_of_interest", items)
        return items

    @app.post("/skeleton/validate")
    def skeleton_validate(payload: dict = Body(...)) -> dict:
        offered = parse_rows(payload["header"], payload["rows"])
        checklist = [
            ChecklistItem(
                course_number=item["course_number"],
                event_type=SessionType(item["event_type"]),
                group_code=item.get("group_code"),
                label=item.get("label", ""),
            )
            for item in payload.get("checklist", [])
        ]
        missing = find_missing(checklist, offered)
        return {"missing": [m.describe() for m in missing], "ok": not missing}

    # ---- solve ------------------------------------------------------ #
    @app.post("/solve")
    def run_solve(payload: dict = Body(default={})) -> dict:
        time_limit = float(payload.get("time_limit_s", 10))
        problem = _problem(store)
        result = solve(problem, time_limit_s=time_limit)
        _refuse_if_grad_pins_unfit(result, problem)
        if not result.solved:
            return {"status": result.status, "solved": False,
                    "placements": {}, "violations": [],
                    "published_missing": _published_missing(store, problem),
                    "published_conflicts": _published_conflicts(store, problem)}
        placements = {
            sid: {"day": p.day, "start_box": p.start_box, "room_id": p.room_id}
            for sid, p in result.schedule.placements.items()
        }
        _refuse_if_unfrozen("that solve", problem, result.schedule)
        store.set_setting("last_schedule", placements)
        return {
            "status": result.status, "solved": True,
            "objective": result.objective,
            "feasible": result.evaluation.is_feasible,
            "soft_penalty": result.evaluation.soft_penalty,
            "placements": placements,
            "sessions": _meta(problem),
            "violations": _violation_dicts(result.evaluation),
            "published_missing": _published_missing(store, problem),
            "published_conflicts": _published_conflicts(store, problem),
        }

    @app.post("/solve/grad")
    def run_solve_grad(payload: dict = Body(default={})) -> dict:
        """Phase 2 — append graduate courses to a published week.

        The freeze does the work: published sessions are pinned to their day,
        hour and room, so the only degrees of freedom left are the graduate
        courses. What this route adds is the refusal to run before publication,
        and the guarantee that a failed solve changes nothing — the published
        week is a promise already made, and a graduate course that will not fit
        is the planner's problem, not a reason to unpick it.
        """
        term = store.get_term(store.current_term()) or {}
        if not term.get("published"):
            raise HTTPException(409, "publish the term before appending graduate "
                                     "courses")

        # Phase 2 is where last year's guesses become this year's facts. A
        # provisional course held its hours through phase 1 on purpose, but
        # finalising around one would schedule a course nobody has confirmed is
        # running — and print it on the graduate timetable.
        unconfirmed = sorted(c.number for c in store.list_courses() if c.provisional)
        if unconfirmed:
            raise HTTPException(
                409, "confirm or remove the provisional course(s) first: "
                     + ", ".join(unconfirmed))

        problem = _problem(store)
        result = solve(problem, time_limit_s=float(payload.get("time_limit_s", 10)))
        if not result.solved:
            return {"status": result.status, "solved": False, "placements": {},
                    "violations": [], "appended": []}

        placements = {
            sid: {"day": p.day, "start_box": p.start_box, "room_id": p.room_id}
            for sid, p in result.schedule.placements.items()
        }
        frozen = store.get_setting("published_schedule") or {}
        _refuse_if_unfrozen("that solve", problem, result.schedule)
        store.set_setting("last_schedule", placements)
        return {
            "status": result.status, "solved": True,
            "objective": result.objective,
            "feasible": result.evaluation.is_feasible,
            "soft_penalty": result.evaluation.soft_penalty,
            "placements": placements,
            "sessions": _meta(problem),
            "violations": _violation_dicts(result.evaluation),
            "published_missing": _published_missing(store, problem),
            "published_conflicts": _published_conflicts(store, problem),
            "appended": sorted(sid for sid in placements if sid not in frozen),
        }

    @app.get("/fixed-events")
    def fixed_events() -> list[dict]:
        """The immovable walls (blackouts + external courses) the grid overlays."""
        return _fixed_event_dicts(_problem(store))

    # ---- live re-validation (the editor backstop) ------------------- #
    @app.post("/evaluate")
    def run_evaluate(payload: dict = Body(...)) -> dict:
        """Re-validate a hand-edited schedule without re-solving.

        Powers the interactive grid: every drag-drop posts the updated placements
        and gets fresh violations back. The edited schedule is persisted so the
        exports reflect manual changes.
        """
        placements_in = payload.get("placements", {})
        problem = _problem(store)
        sched = _schedule_from(problem, placements_in)
        evaluation = evaluate(problem, sched)
        # Evaluate first, and refuse to persist an edit that breaks the freeze.
        # The exports read `last_schedule`, so persisting such an edit would put
        # a published session somewhere the students were never told about.
        breaks_freeze = any(v.kind in ("published_moved", "room_pin_broken")
                            for v in evaluation.violations)
        # Moving a session is answered with the violation (the grid shows it);
        # losing one is a malformed edit and is refused outright.
        _refuse_if_lost(problem, sched)
        if not breaks_freeze:
            store.set_setting("last_schedule", {
                sid: {"day": pl.day, "start_box": pl.start_box, "room_id": pl.room_id}
                for sid, pl in sched.placements.items()
            })
        return {
            "feasible": evaluation.is_feasible,
            "soft_penalty": evaluation.soft_penalty,
            "sessions": _meta(problem),
            "violations": _violation_dicts(evaluation),
        }

    # ---- saved schedules (archive) ---------------------------------- #
    def _app_dir() -> str:
        """The folder the database lives in — where Schedy keeps its own data."""
        db = getattr(store, "path", None) or os.environ.get("SCHEDY_DB", "schedy.sqlite")
        return os.path.dirname(os.path.abspath(db)) or "."

    def _saves_root() -> str:
        """The one folder saved schedules may live under.

        Deliberately not settable over HTTP: it is the boundary the HTTP-settable
        folder is checked against, so a request that could move it would be no
        boundary at all. An operator who keeps saves elsewhere — a synced Drive
        folder — sets ``SCHEDY_SAVES_ROOT`` once, at install time.
        """
        return (os.environ.get("SCHEDY_SAVES_ROOT")
                or os.environ.get("SCHEDY_SAVES")
                or _app_dir())

    def _default_saves_dir() -> tuple[str, str | None]:
        """Where saves go when the planner has not chosen a folder, and any
        default that had to be refused.

        ``saves`` inside the root: beside the DB (``%APPDATA%\\Schedy\\saves`` on
        Windows, ``~/Schedy/saves`` on Unix) unless the operator moved the root
        with ``SCHEDY_SAVES_ROOT``. ``SCHEDY_SAVES`` wins when it names a folder.

        Defaults get the same containment check as a chosen folder: when
        ``SCHEDY_SAVES_ROOT`` is set it is authoritative, so a ``SCHEDY_SAVES``
        outside it, or a ``<root>/saves`` that is a symlink leading out, is
        refused and reported, and the root itself stands in. The result is
        always absolute, so it round-trips through the UI unchanged.
        """
        root = _saves_root()
        env = os.environ.get("SCHEDY_SAVES")
        rejected = None
        if env:
            ok = contained(root, os.path.abspath(env))
            if ok is not None:
                return str(ok), None
            rejected = env
        ok = contained(root, "saves")
        if ok is not None:
            return str(ok), rejected
        return str(Path(root).resolve()), rejected or os.path.join(root, "saves")

    def _configured_saves_dir() -> tuple[str, str | None]:
        """The folder in use, and any stored value that had to be refused.

        A stored folder outside the root — set before this boundary existed, or
        by editing the database — is not quietly obeyed. Neither is it quietly
        dropped: the rejected value is reported so the planner is told why their
        saves are not where they left them, rather than finding them gone.
        """
        configured = store.get_setting("saves_dir")
        if configured:
            ok = contained(_saves_root(), configured)
            if ok is not None:
                return str(ok), None
            return _default_saves_dir()[0], configured
        return _default_saves_dir()

    def _saves_dir() -> str:
        return _configured_saves_dir()[0]

    def _archive() -> Archive:
        return Archive(_saves_dir())

    def _schedule_stats(placements: dict) -> dict:
        """At-a-glance numbers stored with a save, for comparison in the list."""
        problem = _problem(store)
        sched = _schedule_from(problem, placements)
        ev = evaluate(problem, sched)
        return {
            "sessions": len(sched.placements),
            "hard": len([v for v in ev.violations if v.severity == "hard"]),
            "soft_penalty": ev.soft_penalty,
        }

    def _current_snapshot() -> dict:
        """A self-contained freeze of the working state: catalog + settings + plan."""
        return {
            "placements": store.get_setting("last_schedule") or {},
            "courses": [course_to_dict(c) for c in store.list_courses()],
            "offered_rows": store.get_setting("offered_rows"),
            "availability": store.get_setting("availability"),
            "calendar": store.get_setting("calendar"),
        }

    def _config_body() -> dict:
        current, rejected = _configured_saves_dir()
        return {
            "saves_dir": current,
            # The boundary is reported so the planner is told where saves may
            # go, instead of discovering it by being refused.
            "saves_root": str(Path(_saves_root()).resolve()),
            "rejected_saves_dir": rejected,
        }

    @app.get("/config")
    def get_config() -> dict:
        return _config_body()

    @app.put("/config")
    def put_config(payload: dict = Body(...)) -> dict:
        path = (payload.get("saves_dir") or "").strip()
        if path:
            root = _saves_root()
            target = contained(root, path)
            if target is None:
                # Refused before the filesystem is touched: a rejected request
                # must not leave a folder behind on its way out.
                raise HTTPException(
                    400, f"the saves folder must sit under {Path(root).resolve()}")
            try:
                target.mkdir(parents=True, exist_ok=True)
            except OSError as exc:  # noqa: BLE001
                raise HTTPException(400, f"cannot use that folder: {exc}")
            store.set_setting("saves_dir", str(target))
        else:
            store.set_setting("saves_dir", None)  # revert to default
        return _config_body()

    @app.get("/schedules")
    def list_schedules() -> list[dict]:
        return [m.as_dict() for m in _archive().list()]

    @app.post("/schedules")
    def save_schedule(payload: dict = Body(...)) -> dict:
        name = (payload.get("name") or "").strip()
        if not name:
            raise HTTPException(400, "a name is required")
        placements = store.get_setting("last_schedule")
        if not placements:
            raise HTTPException(400, "nothing to save; solve first")
        meta = _archive().save(
            name, _current_snapshot(), _schedule_stats(placements),
            note=(payload.get("note") or None), term=store.current_term())
        return meta.as_dict()

    @app.post("/schedules/{save_id}/load")
    def load_schedule(save_id: str, confirm: bool = False) -> dict:
        doc = _archive().get(save_id)
        if not doc:
            raise HTTPException(404, "no such saved schedule")
        # Saves live in one folder shared by every term, and a save carries a
        # whole catalog. Dropping last year's into this year by accident would
        # replace a semester's work with the wrong semester's.
        saved_term = doc.get("term")
        if saved_term and saved_term != store.current_term() and not confirm:
            raise HTTPException(
                409, f"that schedule belongs to {saved_term}, not "
                     f"{store.current_term()}; pass ?confirm=true to load it anyway")
        snap = doc.get("payload", {})
        # Parse and expand the whole candidate first: nothing is replaced until
        # it is known to be valid and to keep every published session in place.
        try:
            courses = _normalized_catalog(
                course_from_dict(cd) for cd in snap.get("courses", []))
            candidate = _candidate_problem(
                courses, snap.get("offered_rows"), snap.get("availability"))
            placements = snap.get("placements") or {}
            for pl in placements.values():
                candidate.room(pl["room_id"])
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(400, f"that saved schedule is invalid: {exc}")
        _refuse_if_pins_drift("loading that schedule", candidate)
        _refuse_if_unfrozen("loading that schedule",
                            candidate, _schedule_from(candidate, placements))
        # Replace the working state with the frozen scenario, and build the
        # response before committing: if anything fails, nothing was replaced.
        try:
            with store.transaction():
                for c in store.list_courses():
                    store.delete_course(c.number)
                for c in courses:
                    store.upsert_course(c)
                store.set_setting("offered_rows", snap.get("offered_rows"))
                store.set_setting("availability", snap.get("availability"))
                store.set_setting("calendar", snap.get("calendar"))
                store.set_setting("last_schedule", placements)
                # Return a render-ready schedule (same shape as /solve) so the
                # UI can paint it immediately.
                problem = _problem(store)
                sched = _schedule_from(problem, placements)
                ev = evaluate(problem, sched)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(400, f"that saved schedule is invalid: {exc}")
        return {
            "status": "LOADED", "solved": True,
            "feasible": ev.is_feasible, "soft_penalty": ev.soft_penalty,
            "placements": {
                sid: {"day": pl.day, "start_box": pl.start_box, "room_id": pl.room_id}
                for sid, pl in sched.placements.items()
            },
            "sessions": _meta(problem),
            "violations": _violation_dicts(ev),
        }

    @app.get("/schedules/compare")
    def compare_schedules(a: str, b: str) -> dict:
        """Diff two saved schedules: which sessions moved, were added or removed.

        Each save is self-contained, so sessions are rebuilt from that save's own
        catalog to label them (and resolve Hebrew names) accurately.
        """
        arc = _archive()
        da, db = arc.get(a), arc.get(b)
        if not da or not db:
            raise HTTPException(404, "no such saved schedule")

        def info(doc):
            payload = doc.get("payload", {})
            courses = [course_from_dict(c) for c in payload.get("courses", [])]
            prob = catalog_mod.expand(courses, offered_rows=payload.get("offered_rows") or None)
            sess = {s.id: s for s in prob.sessions}
            names = {c.number: (c.name_he or c.name_en or "") for c in courses}
            return payload.get("placements") or {}, sess, names

        pa, sa, na = info(da)
        pb, sb, nb = info(db)
        changes = []
        moved = added = removed = 0
        for sid in sorted(set(pa) | set(pb)):
            x, y = pa.get(sid), pb.get(sid)
            s = sa.get(sid) or sb.get(sid)
            course_number = s.course_number if s else sid.split("-")[0]
            if x and y:
                if (x.get("day"), x.get("start_box"), x.get("room_id")) == \
                   (y.get("day"), y.get("start_box"), y.get("room_id")):
                    continue  # unchanged
                status, moved = "moved", moved + 1
            elif x:
                status, removed = "removed", removed + 1
            else:
                status, added = "added", added + 1
            changes.append({
                "session_id": sid, "course_number": course_number,
                "name": na.get(course_number) or nb.get(course_number) or "",
                "type": s.type.value if s else "", "group": s.group if s else None,
                "a": x, "b": y, "status": status,
            })
        total = len(set(pa) | set(pb))
        return {
            "a": {"id": da["id"], "name": da["name"], "stats": da.get("stats", {})},
            "b": {"id": db["id"], "name": db["name"], "stats": db.get("stats", {})},
            "summary": {"moved": moved, "added": added, "removed": removed,
                        "unchanged": total - len(changes)},
            "changes": changes,
        }

    @app.put("/schedules/{save_id}")
    def rename_schedule(save_id: str, payload: dict = Body(...)) -> dict:
        name = (payload.get("name") or "").strip()
        if not name:
            raise HTTPException(400, "a name is required")
        meta = _archive().rename(save_id, name)
        if not meta:
            raise HTTPException(404, "no such saved schedule")
        return meta.as_dict()

    @app.delete("/schedules/{save_id}")
    def delete_schedule(save_id: str) -> dict:
        if not _archive().delete(save_id):
            raise HTTPException(404, "no such saved schedule")
        return {"deleted": save_id}

    # ---- export ----------------------------------------------------- #
    def _last_schedule() -> tuple[Any, Schedule]:
        placements = store.get_setting("last_schedule")
        if not placements:
            raise HTTPException(404, "no solved schedule yet; POST /solve first")
        problem = _problem(store)
        return problem, _schedule_from(problem, placements)

    @app.get("/export/csv")
    def export_csv() -> Response:
        problem, sched = _last_schedule()
        # Prepend a UTF-8 BOM so Excel (esp. on Windows) renders the Hebrew
        # course names correctly, and offer it as a named download.
        body = ("﻿" + to_csv(problem, sched)).encode("utf-8")
        return Response(
            body, media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=schedy-schedule.csv"},
        )

    @app.get("/export/pdf")
    def export_pdf(layout: str = "cohort") -> Response:
        """PDF export. layout='cohort' (default) = one weekly grid page per
        cohort; layout='flat' = a single assignments table."""
        problem, sched = _last_schedule()
        names = {c.number: (c.name_he or c.name_en) for c in store.list_courses()}
        layout = layout if layout in ("cohort", "flat") else "cohort"
        return Response(
            to_pdf(problem, sched, course_names=names, layout=layout),
            media_type="application/pdf",
        )

    # ---- serve the built frontend (single-process / packaged mode) -- #
    # When a built SPA is present, serve it at "/" so the planner runs one
    # process and opens a browser — no Node at runtime (see docs/windows.md).
    # Mounted last, so the API routes above take precedence.
    static_dir = os.environ.get("SCHEDY_STATIC")
    if not static_dir:
        guess = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
        static_dir = guess if os.path.isdir(guess) else None
    if static_dir and os.path.isdir(static_dir):
        from fastapi.staticfiles import StaticFiles
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="spa")

    return app
