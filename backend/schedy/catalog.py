"""Catalog aggregate — the persistent department course model.

A `Course` holds the durable metadata the skeleton lacks (program, year, role,
session structure, room needs, external fixed placement). `expand` turns the
catalog into the solver's `Problem`: department courses become `Session`s, while
external courses become immovable `FixedEvent` walls.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .domain import (
    Cohort,
    CourseRole,
    FixedEvent,
    Problem,
    Program,
    Session,
    SessionType,
    SoftWeights,
    DayInterval,
    standing_blackouts,
)


@dataclass
class Course:
    number: str
    name_he: str = ""
    name_en: str = ""
    programs: list[Program] = field(default_factory=list)
    year: int = 1
    role: CourseRole = CourseRole.CORE

    lecture_boxes: int = 0
    num_exercise_groups: int = 0
    exercise_boxes: int = 1
    lab_boxes: int = 0
    lab_days: list[int] = field(default_factory=list)  # >1 => cross-day alternatives

    expected_enrollment: int = 0
    needs_computer_farm: bool = False
    is_remote: bool = False

    is_external: bool = False
    ext_day: int | None = None
    ext_start_min: int | None = None
    ext_end_min: int | None = None
    ext_room: str | None = None

    lecturer_ids: list[str] = field(default_factory=list)
    ta_ids: list[str] = field(default_factory=list)

    @property
    def cohorts(self) -> frozenset[Cohort]:
        return frozenset(Cohort(p, self.year) for p in self.programs)


def _course_sessions(c: Course) -> list[Session]:
    cohorts = c.cohorts
    out: list[Session] = []
    common = dict(
        course_number=c.number, cohorts=cohorts, role=c.role,
        expected_enrollment=c.expected_enrollment,
        needs_computer_farm=c.needs_computer_farm, is_remote=c.is_remote,
        lecturer_ids=tuple(c.lecturer_ids),
    )
    if c.lecture_boxes > 0:
        out.append(Session(id=f"{c.number}-lec", type=SessionType.LECTURE,
                           length_boxes=c.lecture_boxes, **common))
    for g in range(c.num_exercise_groups):
        out.append(Session(
            id=f"{c.number}-ex{g + 1}", type=SessionType.EXERCISE,
            length_boxes=c.exercise_boxes, group=f"G{g + 1}",
            ta_ids=tuple(c.ta_ids), **common))
    if c.lab_boxes > 0:
        days = c.lab_days or [None]
        lab_group = c.number if len(days) > 1 else None
        for i, _day in enumerate(days):
            out.append(Session(
                id=f"{c.number}-lab{i + 1}", type=SessionType.LAB,
                length_boxes=c.lab_boxes, lab_group=lab_group,
                ta_ids=tuple(c.ta_ids), **common))
    return out


def _external_event(c: Course) -> FixedEvent | None:
    if c.ext_day is None or c.ext_start_min is None or c.ext_end_min is None:
        return None
    return FixedEvent(
        id=f"ext-{c.number}", label=c.name_en or c.name_he or c.number,
        day=c.ext_day, start_min=c.ext_start_min, end_min=c.ext_end_min,
        cohorts=c.cohorts, room_id=c.ext_room, is_external_course=True,
    )


def expand(
    courses: list[Course],
    *,
    availability: dict[str, set[tuple[int, int]]] | None = None,
    soft_weights: SoftWeights | None = None,
    biology_intervals: list[DayInterval] | None = None,
    include_blackouts: bool = True,
) -> Problem:
    """Build a solver Problem from the catalog."""
    sessions: list[Session] = []
    fixed: list[FixedEvent] = list(standing_blackouts()) if include_blackouts else []
    for c in courses:
        if c.is_external:
            fe = _external_event(c)
            if fe:
                fixed.append(fe)
        else:
            sessions.extend(_course_sessions(c))
    return Problem(
        sessions=sessions,
        fixed_events=fixed,
        availability=availability or {},
        soft_weights=soft_weights or SoftWeights(),
        biology_intervals=biology_intervals or [],
    )
