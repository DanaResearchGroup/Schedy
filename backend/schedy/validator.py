"""Skeleton Validator (pure).

Checks an imported skeleton against the planner's user-defined, persistent
checklist of must-exist items: specific lectures of specific courses, and
specific dedicated exercise groups (e.g. "HEDVA 13"). Returns the items that are
missing so the planner can chase them up before solving.
"""

from __future__ import annotations

from dataclasses import dataclass

from .domain import SessionType
from .parser import OfferedSession


@dataclass(frozen=True)
class ChecklistItem:
    course_number: str
    event_type: SessionType
    group_code: str | None = None   # None = "any session of this type"
    label: str = ""                 # human description for the report

    def describe(self) -> str:
        if self.label:
            return self.label
        grp = f" group {self.group_code}" if self.group_code else ""
        return f"{self.course_number} {self.event_type.value}{grp}"


def _matches(item: ChecklistItem, s: OfferedSession) -> bool:
    if s.course_number != item.course_number:
        return False
    if s.event_type is not item.event_type:
        return False
    if item.group_code is None:
        return True
    needle = item.group_code.strip().lower()
    haystacks = [
        (s.group_code or "").lower(),
        s.package.lower(),
        s.person.lower(),
    ]
    return any(needle in h for h in haystacks)


def find_missing(
    checklist: list[ChecklistItem], offered: list[OfferedSession]
) -> list[ChecklistItem]:
    """Return checklist items with no matching offered session."""
    return [item for item in checklist if not any(_matches(item, s) for s in offered)]
