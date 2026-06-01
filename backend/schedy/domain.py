"""Core domain model for Schedy.

This module holds the value objects and aggregates every other module reasons
over. It deliberately contains no I/O — it is pure data plus small, total
helper functions, so it is trivially testable and stable.

Time model (per the PRD):
  * Teaching week = Sunday..Thursday (day indices 0..4).
  * Day runs 08:30..18:30, divided into ten 60-minute "academic-hour" boxes
    aligned to the :30 (box 0 = 08:30-09:30 ... box 9 = 17:30-18:30).
  * Department sessions are placed on this box grid. Fixed external courses and
    blackout windows are stored as arbitrary minute intervals (they need not
    align to the grid) and overlap is tested in minute space.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# --------------------------------------------------------------------------- #
# Time grid
# --------------------------------------------------------------------------- #

DAY_NAMES = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday")
NUM_DAYS = len(DAY_NAMES)

DAY_START_MIN = 8 * 60 + 30   # 08:30 -> 510
BOX_MINUTES = 60
BOXES_PER_DAY = 10            # 08:30 .. 18:30
DAY_END_MIN = DAY_START_MIN + BOXES_PER_DAY * BOX_MINUTES  # 18:30 -> 1110


def box_start_min(box: int) -> int:
    """Minute-of-day at which the given academic-hour box begins."""
    return DAY_START_MIN + box * BOX_MINUTES


def box_interval(box: int, length_boxes: int = 1) -> tuple[int, int]:
    """(start_min, end_min) for a run of `length_boxes` boxes starting at `box`."""
    start = box_start_min(box)
    return start, start + length_boxes * BOX_MINUTES


def minutes_to_hhmm(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def box_label(box: int) -> str:
    s, e = box_interval(box)
    return f"{minutes_to_hhmm(s)}-{minutes_to_hhmm(e)}"


# --------------------------------------------------------------------------- #
# Enumerations
# --------------------------------------------------------------------------- #

class Program(str, Enum):
    CHEME = "ChemE"
    BIOCHEME = "BioChemE"
    CHEME_CHEM = "ChemE-Chemistry"


class CourseRole(str, Enum):
    CORE = "core"
    ELECTIVE = "elective"
    REPLACEMENT = "replacement"
    LAB = "lab"


class SessionType(str, Enum):
    LECTURE = "lecture"
    EXERCISE = "exercise"
    LAB = "lab"


# --------------------------------------------------------------------------- #
# Value objects
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Cohort:
    """A teaching audience = (program, year). Set-valued per course."""
    program: Program
    year: int  # 1..4

    @property
    def label(self) -> str:
        return f"{self.program.value} Y{self.year}"


@dataclass(frozen=True)
class Room:
    id: str
    name: str
    capacity: int
    is_computer_farm: bool = False


# The department's fixed room inventory (PRD).
DEFAULT_ROOMS: tuple[Room, ...] = (
    Room("hall1", "Hall 1", 210),
    Room("room2", "Classroom 2 (computer farm)", 22, is_computer_farm=True),
    Room("room3", "Classroom 3", 50),
    Room("room4", "Classroom 4", 50),
    Room("room5", "Classroom 5", 50),
    Room("hall6", "Hall 6", 120),
)


@dataclass(frozen=True)
class DayInterval:
    """An interval within a single weekday, in minutes-of-day."""
    day: int
    start_min: int
    end_min: int

    def overlaps(self, other: "DayInterval") -> bool:
        return (
            self.day == other.day
            and self.start_min < other.end_min
            and other.start_min < self.end_min
        )


@dataclass(frozen=True)
class Placement:
    """The solver's decision for one session: a day, a starting box, a room."""
    day: int
    start_box: int
    room_id: str


# --------------------------------------------------------------------------- #
# Sessions (the things the solver places)
# --------------------------------------------------------------------------- #

@dataclass
class Session:
    """A concrete department teaching event to be scheduled.

    A course expands into one or more sessions: a lecture, N exercise groups,
    and/or lab offerings. Each session carries the cohorts it serves so the
    Constraint Evaluator can detect student clashes.
    """
    id: str
    course_number: str
    type: SessionType
    length_boxes: int
    cohorts: frozenset[Cohort]
    group: str | None = None                 # e.g. "SE011" exercise/lab group
    lecturer_ids: tuple[str, ...] = ()
    ta_ids: tuple[str, ...] = ()
    needs_computer_farm: bool = False
    is_remote: bool = False                  # Zoom-only -> prefer morning/late
    expected_enrollment: int = 0
    role: CourseRole = CourseRole.CORE
    # For multi-day labs: the id of the alternative-group this session belongs
    # to. Sessions sharing a lab_group are day-alternatives; each served cohort
    # must keep >=1 attainable alternative (cross-day satisfiability).
    lab_group: str | None = None

    @property
    def people(self) -> tuple[str, ...]:
        return self.lecturer_ids + self.ta_ids

    def interval(self, placement: Placement) -> DayInterval:
        start, end = box_interval(placement.start_box, self.length_boxes)
        return DayInterval(placement.day, start, end)

    def cells(self, placement: Placement) -> frozenset[tuple[int, int]]:
        """The (day, box) grid cells this session occupies when placed."""
        return frozenset(
            (placement.day, placement.start_box + i)
            for i in range(self.length_boxes)
        )


# --------------------------------------------------------------------------- #
# Fixed events (immovable walls): external courses + blackout windows
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class FixedEvent:
    """An immovable occupancy the solver schedules around.

    Two flavours:
      * External course  -> blocks its `cohorts` (and optionally a `room_id`).
      * Blackout window  -> `is_blackout=True`, blocks every cohort and room.
    """
    id: str
    label: str
    day: int
    start_min: int
    end_min: int
    cohorts: frozenset[Cohort] = frozenset()
    room_id: str | None = None
    is_blackout: bool = False
    is_external_course: bool = False

    @property
    def interval(self) -> DayInterval:
        return DayInterval(self.day, self.start_min, self.end_min)


# Standing departmental blackout windows (PRD).
def standing_blackouts() -> list[FixedEvent]:
    wed = DAY_NAMES.index("Wednesday")
    mon = DAY_NAMES.index("Monday")
    return [
        FixedEvent(
            id="blackout-wed-afternoon",
            label="Wed Afternoon (free time)",
            day=wed, start_min=12 * 60 + 30, end_min=14 * 60 + 30,
            is_blackout=True,
        ),
        FixedEvent(
            id="blackout-mon-seminar",
            label="Departmental Seminar",
            day=mon, start_min=13 * 60 + 30, end_min=14 * 60 + 30,
            is_blackout=True,
        ),
    ]


# --------------------------------------------------------------------------- #
# Soft-constraint weights (the tunable ladder, heaviest -> lightest)
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class SoftWeights:
    elective_vs_core: int = 1000
    elective_vs_elective: int = 500
    avoid_biology: int = 200
    zoom_timing: int = 100
    lecture_before_exercise: int = 50


# --------------------------------------------------------------------------- #
# Problem + Schedule aggregates
# --------------------------------------------------------------------------- #

@dataclass
class Problem:
    """Everything needed to evaluate or solve one semester's department schedule."""
    rooms: list[Room] = field(default_factory=lambda: list(DEFAULT_ROOMS))
    sessions: list[Session] = field(default_factory=list)
    fixed_events: list[FixedEvent] = field(default_factory=list)
    # person_id -> set of (day, box) the person is UNAVAILABLE.
    availability: dict[str, set[tuple[int, int]]] = field(default_factory=dict)
    soft_weights: SoftWeights = field(default_factory=SoftWeights)
    # Course numbers offered by the Biology department this semester (their
    # electives, to soft-avoid). Stored as DayIntervals of those offerings.
    biology_intervals: list[DayInterval] = field(default_factory=list)

    def room(self, room_id: str) -> Room:
        for r in self.rooms:
            if r.id == room_id:
                return r
        raise KeyError(f"unknown room {room_id!r}")

    def session(self, session_id: str) -> Session:
        for s in self.sessions:
            if s.id == session_id:
                return s
        raise KeyError(f"unknown session {session_id!r}")

    def lab_alternatives(self) -> dict[str, list[Session]]:
        """Map lab_group id -> the sessions that are its day-alternatives."""
        groups: dict[str, list[Session]] = {}
        for s in self.sessions:
            if s.lab_group:
                groups.setdefault(s.lab_group, []).append(s)
        return groups


@dataclass
class Schedule:
    """A set of placements for the department's sessions."""
    placements: dict[str, Placement] = field(default_factory=dict)

    def place(self, session_id: str, day: int, start_box: int, room_id: str) -> None:
        self.placements[session_id] = Placement(day, start_box, room_id)
