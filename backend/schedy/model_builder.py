"""Model Builder — translate a Problem into a CP-SAT model.

Decision per session: a weekday (0..4), a starting academic-hour box, and a room.
Positions are expressed on a single absolute timeline of NUM_DAYS * BOXES_PER_DAY
boxes so that interval no-overlap constraints work in one dimension. A session's
start is constrained within its day, so intervals never cross a day boundary.

Hard constraints become no-overlap / forbidden-region constraints; soft
constraints become reified overlap booleans summed into the objective (the
weighted ladder). Lab cross-day satisfiability is intentionally left to the
Constraint Evaluator as a post-hoc check (best-effort philosophy) — it does not
linearise cleanly and the evaluator is the single source of truth anyway.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ortools.sat.python import cp_model

from .domain import (
    BOXES_PER_DAY,
    BOX_MINUTES,
    DAY_START_MIN,
    NUM_DAYS,
    CourseRole,
    DayInterval,
    Problem,
    Schedule,
    Session,
    SessionType,
)

HORIZON = NUM_DAYS * BOXES_PER_DAY


def _interval_to_abs_boxes(iv: DayInterval) -> tuple[int, int]:
    """Convert a minute-interval on a weekday to absolute [start_box, end_box)."""
    start_box = (iv.start_min - DAY_START_MIN) // BOX_MINUTES
    end_box = math.ceil((iv.end_min - DAY_START_MIN) / BOX_MINUTES)
    base = iv.day * BOXES_PER_DAY
    return base + max(0, start_box), base + max(0, end_box)


@dataclass
class _SessionVars:
    day: cp_model.IntVar
    start: cp_model.IntVar
    abs_start: cp_model.IntVar
    abs_end: cp_model.IntVar
    interval: cp_model.IntervalVar
    room: cp_model.IntVar
    room_candidates: list[int]


class ModelBuilder:
    def __init__(self, problem: Problem):
        self.problem = problem
        self.model = cp_model.CpModel()
        self.vars: dict[str, _SessionVars] = {}
        self.has_objective = False
        self._build()

    # ------------------------------------------------------------------ #
    def _candidate_rooms(self, s: Session) -> list[int]:
        rooms = self.problem.rooms
        cands = []
        for i, r in enumerate(rooms):
            if s.needs_computer_farm and not r.is_computer_farm:
                continue
            if s.expected_enrollment and s.expected_enrollment > r.capacity:
                continue
            cands.append(i)
        return cands or list(range(len(rooms)))  # never empty; evaluator flags misfits

    def _build(self) -> None:
        m = self.model
        for s in self.problem.sessions:
            L = s.length_boxes
            day = m.NewIntVar(0, NUM_DAYS - 1, f"day_{s.id}")
            start = m.NewIntVar(0, BOXES_PER_DAY - L, f"start_{s.id}")
            abs_start = m.NewIntVar(0, HORIZON - L, f"abs_{s.id}")
            m.Add(abs_start == day * BOXES_PER_DAY + start)
            abs_end = m.NewIntVar(0, HORIZON, f"absend_{s.id}")
            m.Add(abs_end == abs_start + L)
            interval = m.NewIntervalVar(abs_start, L, abs_end, f"iv_{s.id}")
            cands = self._candidate_rooms(s)
            room = m.NewIntVarFromDomain(
                cp_model.Domain.FromValues(cands), f"room_{s.id}")
            self.vars[s.id] = _SessionVars(
                day, start, abs_start, abs_end, interval, room, cands)

        self._hard_room()
        self._hard_cohort()
        self._hard_person()
        self._hard_same_course_ta()
        self._hard_fixed_events()
        self._hard_availability()
        self._objective()

    # ------------------------------------------------------------------ #
    # Hard constraints
    # ------------------------------------------------------------------ #
    def _hard_room(self) -> None:
        m = self.model
        rooms = self.problem.rooms
        per_room: dict[int, list[cp_model.IntervalVar]] = {i: [] for i in range(len(rooms))}
        for s in self.problem.sessions:
            v = self.vars[s.id]
            for ri in v.room_candidates:
                lit = m.NewBoolVar(f"in_{s.id}_room{ri}")
                m.Add(v.room == ri).OnlyEnforceIf(lit)
                m.Add(v.room != ri).OnlyEnforceIf(lit.Not())
                opt = m.NewOptionalIntervalVar(
                    v.abs_start, s.length_boxes, v.abs_end, lit, f"iv_{s.id}_r{ri}")
                per_room[ri].append(opt)
        # External courses pinned to a room become fixed obstacles in that room.
        for fe in self.problem.fixed_events:
            if fe.is_blackout or fe.room_id is None:
                continue
            ri = self._room_index(fe.room_id)
            if ri is None:
                continue
            b0, b1 = _interval_to_abs_boxes(fe.interval)
            per_room[ri].append(
                m.NewIntervalVar(b0, b1 - b0, b1, f"ext_room_{fe.id}"))
        for ri, ivs in per_room.items():
            if len(ivs) > 1:
                m.AddNoOverlap(ivs)

    def _hard_cohort(self) -> None:
        m = self.model
        per_cohort: dict[object, list[cp_model.IntervalVar]] = {}
        for s in self.problem.sessions:
            if s.role is CourseRole.ELECTIVE:
                continue  # electives handled softly
            for c in s.cohorts:
                per_cohort.setdefault(c, []).append(self.vars[s.id].interval)
        for fe in self.problem.fixed_events:
            if fe.is_blackout:
                continue
            b0, b1 = _interval_to_abs_boxes(fe.interval)
            for c in fe.cohorts:
                per_cohort.setdefault(c, []).append(
                    m.NewIntervalVar(b0, b1 - b0, b1, f"ext_co_{fe.id}_{c.label}"))
        for ivs in per_cohort.values():
            if len(ivs) > 1:
                m.AddNoOverlap(ivs)

    def _hard_person(self) -> None:
        m = self.model
        per_person: dict[str, list[cp_model.IntervalVar]] = {}
        for s in self.problem.sessions:
            for p in s.people:
                per_person.setdefault(p, []).append(self.vars[s.id].interval)
        for ivs in per_person.values():
            if len(ivs) > 1:
                m.AddNoOverlap(ivs)

    def _hard_same_course_ta(self) -> None:
        m = self.model
        per_course: dict[str, list[cp_model.IntervalVar]] = {}
        for s in self.problem.sessions:
            if s.type is SessionType.EXERCISE:
                per_course.setdefault(s.course_number, []).append(
                    self.vars[s.id].interval)
        for ivs in per_course.values():
            if len(ivs) > 1:
                m.AddNoOverlap(ivs)

    def _hard_fixed_events(self) -> None:
        """Blackout windows block every session."""
        m = self.model
        for fe in self.problem.fixed_events:
            if not fe.is_blackout:
                continue
            b0, b1 = _interval_to_abs_boxes(fe.interval)
            for s in self.problem.sessions:
                v = self.vars[s.id]
                before = m.NewBoolVar(f"bl_before_{s.id}_{fe.id}")
                after = m.NewBoolVar(f"bl_after_{s.id}_{fe.id}")
                m.Add(v.abs_end <= b0).OnlyEnforceIf(before)
                m.Add(v.abs_start >= b1).OnlyEnforceIf(after)
                m.AddBoolOr([before, after])

    def _hard_availability(self) -> None:
        m = self.model
        for s in self.problem.sessions:
            v = self.vars[s.id]
            forbidden_cells = set()
            for p in s.people:
                forbidden_cells |= self.problem.availability.get(p, set())
            for (d, box) in forbidden_cells:
                cell = d * BOXES_PER_DAY + box
                before = m.NewBoolVar(f"av_before_{s.id}_{d}_{box}")
                after = m.NewBoolVar(f"av_after_{s.id}_{d}_{box}")
                m.Add(v.abs_end <= cell).OnlyEnforceIf(before)
                m.Add(v.abs_start >= cell + 1).OnlyEnforceIf(after)
                m.AddBoolOr([before, after])

    # ------------------------------------------------------------------ #
    # Soft objective (weighted ladder)
    # ------------------------------------------------------------------ #
    def _overlap_bool(self, name: str, a: _SessionVars, b: _SessionVars) -> cp_model.IntVar:
        m = self.model
        b1 = m.NewBoolVar(name + "_b1")
        b2 = m.NewBoolVar(name + "_b2")
        m.Add(a.abs_start < b.abs_end).OnlyEnforceIf(b1)
        m.Add(a.abs_start >= b.abs_end).OnlyEnforceIf(b1.Not())
        m.Add(b.abs_start < a.abs_end).OnlyEnforceIf(b2)
        m.Add(b.abs_start >= a.abs_end).OnlyEnforceIf(b2.Not())
        ov = m.NewBoolVar(name)
        m.AddBoolAnd([b1, b2]).OnlyEnforceIf(ov)
        m.AddBoolOr([b1.Not(), b2.Not()]).OnlyEnforceIf(ov.Not())
        return ov

    def _objective(self) -> None:
        m = self.model
        w = self.problem.soft_weights
        terms = []
        sessions = self.problem.sessions

        for i in range(len(sessions)):
            for j in range(i + 1, len(sessions)):
                si, sj = sessions[i], sessions[j]
                ei, ej = si.role is CourseRole.ELECTIVE, sj.role is CourseRole.ELECTIVE
                if ei and ej:
                    ov = self._overlap_bool(f"ee_{si.id}_{sj.id}",
                                            self.vars[si.id], self.vars[sj.id])
                    terms.append((w.elective_vs_elective, ov))
                elif (ei or ej) and (si.cohorts & sj.cohorts):
                    ov = self._overlap_bool(f"ec_{si.id}_{sj.id}",
                                            self.vars[si.id], self.vars[sj.id])
                    terms.append((w.elective_vs_core, ov))

        # avoid Biology electives: elective vs each fixed biology interval
        for s in sessions:
            if s.role is not CourseRole.ELECTIVE:
                continue
            v = self.vars[s.id]
            for k, bio in enumerate(self.problem.biology_intervals):
                b0, b1 = _interval_to_abs_boxes(bio)
                hit = m.NewBoolVar(f"bio_{s.id}_{k}")
                before = m.NewBoolVar(f"bio_before_{s.id}_{k}")
                after = m.NewBoolVar(f"bio_after_{s.id}_{k}")
                m.Add(v.abs_end <= b0).OnlyEnforceIf(before)
                m.Add(v.abs_start >= b1).OnlyEnforceIf(after)
                m.AddBoolOr([before, after]).OnlyEnforceIf(hit.Not())
                m.Add(before == 0).OnlyEnforceIf(hit)
                m.Add(after == 0).OnlyEnforceIf(hit)
                terms.append((w.avoid_biology, hit))

        # zoom timing: remote sessions penalised in the middle of the day
        for s in sessions:
            if not s.is_remote:
                continue
            v = self.vars[s.id]
            mid = m.NewBoolVar(f"mid_{s.id}")
            # middle = start box in 2..6
            m.Add(v.start >= 2).OnlyEnforceIf(mid)
            m.Add(v.start <= 6).OnlyEnforceIf(mid)
            lo = m.NewBoolVar(f"lo_{s.id}")
            hi = m.NewBoolVar(f"hi_{s.id}")
            m.Add(v.start <= 1).OnlyEnforceIf(lo)
            m.Add(v.start >= 7).OnlyEnforceIf(hi)
            m.AddBoolOr([lo, hi, mid])
            m.AddBoolOr([lo.Not(), mid.Not()])
            m.AddBoolOr([hi.Not(), mid.Not()])
            terms.append((w.zoom_timing, mid))

        # lecture before exercise (low weight): per course, exercise vs lecture
        by_course: dict[str, dict[str, list[Session]]] = {}
        for s in sessions:
            if s.type in (SessionType.LECTURE, SessionType.EXERCISE):
                b = by_course.setdefault(s.course_number,
                                         {"lec": [], "ex": []})
                b["lec" if s.type is SessionType.LECTURE else "ex"].append(s)
        for course, parts in by_course.items():
            for lec in parts["lec"]:
                for ex in parts["ex"]:
                    lv, ev = self.vars[lec.id], self.vars[ex.id]
                    bad = m.NewBoolVar(f"lbe_{course}_{ex.id}_{lec.id}")
                    m.Add(ev.abs_start < lv.abs_start).OnlyEnforceIf(bad)
                    m.Add(ev.abs_start >= lv.abs_start).OnlyEnforceIf(bad.Not())
                    terms.append((w.lecture_before_exercise, bad))

        if terms:
            m.Minimize(sum(weight * var for weight, var in terms))
            self.has_objective = True

    # ------------------------------------------------------------------ #
    def _room_index(self, room_id: str) -> int | None:
        for i, r in enumerate(self.problem.rooms):
            if r.id == room_id:
                return i
        return None

    def extract(self, solver: cp_model.CpSolver) -> Schedule:
        sched = Schedule()
        for s in self.problem.sessions:
            v = self.vars[s.id]
            day = solver.Value(v.day)
            start = solver.Value(v.start)
            room = self.problem.rooms[solver.Value(v.room)].id
            sched.place(s.id, day, start, room)
        return sched
