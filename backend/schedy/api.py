"""FastAPI app — thin orchestration over the engine + store.

Pipeline the planner drives: maintain the catalog, import & validate a skeleton,
solve, review/edit, export. Business logic stays in the engine modules; this
layer only wires HTTP to them.
"""

from __future__ import annotations

import os
from datetime import date
from typing import Any

import tempfile

from fastapi import Body, FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from . import catalog as catalog_mod
from .archive import Archive
from .calendar_engine import (
    SemesterCalendar,
    lost_sessions,
    order_inversions,
    realize,
    teaching_days_by_template,
)
from .domain import BOX_MINUTES, BOXES_PER_DAY, DAY_START_MIN, Schedule, SessionType
from .evaluator import evaluate
from .exporters import to_csv, to_pdf
from .parser import parse_rows, parse_skeleton
from .solver import solve
from .store import Store, course_from_dict, course_to_dict
from .validator import ChecklistItem, find_missing


def _load_availability(store: Store) -> dict[str, set[tuple[int, int]]]:
    raw = store.get_setting("availability", {}) or {}
    return {p: {tuple(cell) for cell in cells} for p, cells in raw.items()}


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


def _problem(store: Store):
    return catalog_mod.expand(
        store.list_courses(),
        offered_rows=store.get_setting("offered_rows") or None,
        availability=_load_availability(store),
    )


def _session_meta(problem) -> dict:
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
            "enrollment": s.expected_enrollment,
            "needs_farm": s.needs_computer_farm,
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

    # ---- catalog ---------------------------------------------------- #
    @app.get("/catalog/courses")
    def list_courses() -> list[dict]:
        return [course_to_dict(c) for c in store.list_courses()]

    @app.post("/catalog/courses")
    def upsert_course(payload: dict = Body(...)) -> dict:
        try:
            course = course_from_dict(payload)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(400, f"invalid course: {exc}")
        store.upsert_course(course)
        return course_to_dict(course)

    @app.delete("/catalog/courses/{number}")
    def delete_course(number: str) -> dict:
        store.delete_course(number)
        return {"deleted": number}

    @app.post("/catalog/seed")
    def seed_catalog(force: bool = False) -> dict:
        """Load the illustrative demo catalog (first-run onboarding)."""
        from .sample_data import sample_courses
        existing = store.list_courses()
        if existing and not force:
            raise HTTPException(409, "catalog not empty; pass ?force=true to replace")
        for c in existing:
            store.delete_course(c.number)
        courses = sample_courses()
        for c in courses:
            store.upsert_course(c)
        return {"seeded": len(courses)}

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
                 "exercise_group": o.exercise_group}
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
        """Upload a Technion skeleton XLSX; parse it, filtered to catalog courses."""
        data = await file.read()
        relevant = {c.number for c in store.list_courses()} or None
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp.write(data)
            path = tmp.name
        try:
            offered = parse_skeleton(path, relevant)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(400, f"could not parse skeleton: {exc}")
        finally:
            os.unlink(path)
        store.set_setting("offered_rows", [
            {"course_number": s.course_number,
             "event_type": s.event_type.value if s.event_type else None,
             "group_code": s.group_code, "name_he": s.name_he, "name_en": s.name_en,
             "day": s.day, "start_min": s.start_min, "end_min": s.end_min,
             "room": s.room, "package": s.package, "row": s.row,
             "pinned": catalog_mod.pinnable(s.day, s.start_min)}
            for s in offered
        ])
        return {"count": len(offered), "offered": store.get_setting("offered_rows")}

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
        store.set_setting("offered_rows", norm)
        return {"count": len(norm), "offered": norm}

    @app.delete("/skeleton/rows")
    def clear_skeleton_rows() -> dict:
        """Remove all imported skeleton rows (a fresh import starts clean)."""
        store.set_setting("offered_rows", [])
        return {"count": 0, "offered": []}

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
        if not result.solved:
            return {"status": result.status, "solved": False,
                    "placements": {}, "violations": []}
        placements = {
            sid: {"day": p.day, "start_box": p.start_box, "room_id": p.room_id}
            for sid, p in result.schedule.placements.items()
        }
        store.set_setting("last_schedule", placements)
        return {
            "status": result.status, "solved": True,
            "objective": result.objective,
            "feasible": result.evaluation.is_feasible,
            "soft_penalty": result.evaluation.soft_penalty,
            "placements": placements,
            "sessions": _session_meta(problem),
            "violations": _violation_dicts(result.evaluation),
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
        known = {s.id for s in problem.sessions}
        sched = Schedule()
        for sid, p in placements_in.items():
            if sid in known:
                sched.place(sid, int(p["day"]), int(p["start_box"]), p["room_id"])
        store.set_setting("last_schedule", {
            sid: {"day": pl.day, "start_box": pl.start_box, "room_id": pl.room_id}
            for sid, pl in sched.placements.items()
        })
        evaluation = evaluate(problem, sched)
        return {
            "feasible": evaluation.is_feasible,
            "soft_penalty": evaluation.soft_penalty,
            "sessions": _session_meta(problem),
            "violations": _violation_dicts(evaluation),
        }

    # ---- saved schedules (archive) ---------------------------------- #
    def _saves_dir() -> str:
        """The managed folder for saved schedules — user-chosen, else default.

        Default sits beside the DB (``%APPDATA%\\Schedy\\saves`` on Windows,
        ``~/Schedy/saves`` on Unix); overridable via the UI or ``SCHEDY_SAVES``.
        """
        configured = store.get_setting("saves_dir")
        if configured:
            return configured
        env = os.environ.get("SCHEDY_SAVES")
        if env:
            return env
        db = getattr(store, "path", None) or os.environ.get("SCHEDY_DB", "schedy.sqlite")
        parent = os.path.dirname(os.path.abspath(db)) or "."
        return os.path.join(parent, "saves")

    def _archive() -> Archive:
        return Archive(_saves_dir())

    def _schedule_stats(placements: dict) -> dict:
        """At-a-glance numbers stored with a save, for comparison in the list."""
        problem = _problem(store)
        known = {s.id for s in problem.sessions}
        sched = Schedule()
        for sid, p in placements.items():
            if sid in known:
                sched.place(sid, int(p["day"]), int(p["start_box"]), p["room_id"])
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

    @app.get("/config")
    def get_config() -> dict:
        return {"saves_dir": _saves_dir()}

    @app.put("/config")
    def put_config(payload: dict = Body(...)) -> dict:
        path = (payload.get("saves_dir") or "").strip()
        if path:
            try:
                os.makedirs(path, exist_ok=True)
            except OSError as exc:  # noqa: BLE001
                raise HTTPException(400, f"cannot use that folder: {exc}")
            store.set_setting("saves_dir", path)
        else:
            store.set_setting("saves_dir", None)  # revert to default
        return {"saves_dir": _saves_dir()}

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
            note=(payload.get("note") or None))
        return meta.as_dict()

    @app.post("/schedules/{save_id}/load")
    def load_schedule(save_id: str) -> dict:
        doc = _archive().get(save_id)
        if not doc:
            raise HTTPException(404, "no such saved schedule")
        snap = doc.get("payload", {})
        # Replace the working state with the frozen scenario.
        for c in store.list_courses():
            store.delete_course(c.number)
        for cd in snap.get("courses", []):
            store.upsert_course(course_from_dict(cd))
        store.set_setting("offered_rows", snap.get("offered_rows"))
        store.set_setting("availability", snap.get("availability"))
        store.set_setting("calendar", snap.get("calendar"))
        placements = snap.get("placements") or {}
        store.set_setting("last_schedule", placements)
        # Return a render-ready schedule (same shape as /solve) so the UI can
        # paint it immediately.
        problem = _problem(store)
        known = {s.id for s in problem.sessions}
        sched = Schedule()
        for sid, p in placements.items():
            if sid in known:
                sched.place(sid, int(p["day"]), int(p["start_box"]), p["room_id"])
        ev = evaluate(problem, sched)
        return {
            "status": "LOADED", "solved": True,
            "feasible": ev.is_feasible, "soft_penalty": ev.soft_penalty,
            "placements": {
                sid: {"day": pl.day, "start_box": pl.start_box, "room_id": pl.room_id}
                for sid, pl in sched.placements.items()
            },
            "sessions": _session_meta(problem),
            "violations": _violation_dicts(ev),
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
        sched = Schedule()
        for sid, p in placements.items():
            sched.place(sid, p["day"], p["start_box"], p["room_id"])
        return _problem(store), sched

    @app.get("/export/csv")
    def export_csv() -> Response:
        problem, sched = _last_schedule()
        return Response(to_csv(problem, sched), media_type="text/csv")

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
