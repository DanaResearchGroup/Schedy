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


def solve(problem: Problem, time_limit_s: float = 10.0, workers: int = 8) -> SolveResult:
    builder = ModelBuilder(problem)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_search_workers = workers

    status = solver.Solve(builder.model)
    status_name = solver.StatusName(status)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        schedule = builder.extract(solver)
        evaluation = evaluate(problem, schedule)
        objective = solver.ObjectiveValue() if builder.has_objective else 0.0
        return SolveResult(status_name, schedule, evaluation, objective)

    return SolveResult(status_name, None, None, None)
