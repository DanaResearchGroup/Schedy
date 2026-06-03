"""FastAPI app — thin orchestration over the engine + store.

Pipeline the planner drives: maintain the catalog, import & validate a skeleton,
solve, review/edit, export. Business logic stays in the engine modules; this
layer only wires HTTP to them.
"""

from __future__ import annotations

import os
from typing import Any

import tempfile

from fastapi import Body, FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from . import catalog as catalog_mod
from .domain import Schedule, SessionType
from .evaluator import evaluate
from .exporters import to_csv, to_pdf
from .parser import parse_rows, parse_skeleton
from .solver import solve
from .store import Store, course_from_dict, course_to_dict
from .validator import ChecklistItem, find_missing


def _load_availability(store: Store) -> dict[str, set[tuple[int, int]]]:
    raw = store.get_setting("availability", {}) or {}
    return {p: {tuple(cell) for cell in cells} for p, cells in raw.items()}


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
        }
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

    # ---- availability ---------------------------------------------- #
    @app.put("/availability")
    def set_availability(payload: dict = Body(...)) -> dict:
        store.set_setting("availability", payload)
        return {"people": list(payload.keys())}

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
             "room": s.room, "package": s.package, "row": s.row}
            for s in offered
        ])
        return {"count": len(offered), "offered": store.get_setting("offered_rows")}

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
    def export_pdf() -> Response:
        problem, sched = _last_schedule()
        return Response(to_pdf(problem, sched), media_type="application/pdf")

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
