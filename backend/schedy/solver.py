"""Solver Runner.

Runs the CP-SAT model and returns a best-effort result. The Constraint Evaluator
is the single source of truth for *all* rules, so the runner always evaluates the
extracted schedule and attaches the violation report — including any residual
hard issues (e.g. lab cross-day) the model does not linearise. This is the
"best-effort + editable + explanation" contract from the PRD.
"""

from __future__ import annotations

from dataclasses import dataclass

from ortools.sat.python import cp_model

from .domain import Problem, Schedule
from .evaluator import EvaluationResult, evaluate
from .model_builder import ModelBuilder


@dataclass
class SolveResult:
    status: str                       # OPTIMAL | FEASIBLE | INFEASIBLE | UNKNOWN
    schedule: Schedule | None
    evaluation: EvaluationResult | None
    objective: float | None

    @property
    def solved(self) -> bool:
        return self.schedule is not None


def solve(
    problem: Problem,
    time_limit_s: float = 10.0,
    workers: int = 8,
    max_repair_rounds: int = 3,
) -> SolveResult:
    """Best-effort solve with a guided-repair loop for lab cross-day satisfiability.

    Lab cross-day ("each cohort keeps >=1 clash-free day") is left out of the base
    model — it bloats it and rarely binds. If the evaluator flags it on the solved
    schedule, the offending lab groups get the constraint encoded natively and the
    model is re-solved. We loop until clean, no new groups appear, or the round cap
    is hit — then return the latest solved schedule (still flagged) as best-effort.
    """
    enforce: set[str] = set()
    last: SolveResult | None = None

    for _ in range(max_repair_rounds + 1):
        builder = ModelBuilder(problem, enforce_lab_groups=frozenset(enforce))
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit_s
        solver.parameters.num_search_workers = workers

        status = solver.Solve(builder.model)
        status_name = solver.StatusName(status)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            # Enforcing made it infeasible (no clash-free arrangement exists) —
            # fall back to the last solved, flagged best-effort schedule.
            return last or SolveResult(status_name, None, None, None)

        schedule = builder.extract(solver)
        evaluation = evaluate(problem, schedule)
        objective = solver.ObjectiveValue() if builder.has_objective else 0.0
        last = SolveResult(status_name, schedule, evaluation, objective)

        flagged = {
            g for v in evaluation.violations if v.kind == "lab_cross_day_unsatisfiable"
            for sid in v.session_ids
            for g in (problem.session(sid).lab_group,) if g
        }
        if not flagged - enforce:  # clean, or nothing new to enforce
            return last
        enforce |= flagged

    return last
