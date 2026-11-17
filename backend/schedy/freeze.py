"""The one rule that keeps a published week frozen.

Publishing records where every frozen session sits. From then on, nothing that
persists a schedule or replaces the catalog may move one of them or make one
vanish; only an explicit unpublish lifts that. Every write path asks this
function, so the rule cannot drift between them.

Known gap: the published baseline stores only ``day``, ``start_box`` and
``room_id`` — not a session's duration or lecturers — so those cannot be
compared (see "Honest caveats" in docs/PRD.md).
"""

from __future__ import annotations

from .domain import Schedule


def freeze_violations(frozen: dict[str, dict], problem, schedule: Schedule
                      ) -> list[tuple[str, str]]:
    """Frozen sessions a candidate would lose or move, as ``(id, kind)`` pairs.

    ``missing``: the candidate catalog no longer produces the session, or the
    candidate schedule does not place it. ``moved``: placed somewhere else.
    """
    have = {s.id for s in problem.sessions}
    out: list[tuple[str, str]] = []
    for sid, pin in sorted(frozen.items()):
        placed = schedule.placements.get(sid)
        if sid not in have or placed is None:
            out.append((sid, "missing"))
        elif (placed.day, placed.start_box, placed.room_id) != (
                int(pin["day"]), int(pin["start_box"]), pin["room_id"]):
            out.append((sid, "moved"))
    return out


def refusal(violations: list[tuple[str, str]], what: str) -> str:
    """The 409 message: which sessions, and the only way out."""
    names = ", ".join(f"{sid} ({kind})" for sid, kind in violations)
    return (f"{what} would change published session(s): {names}; "
            "unpublish the term first")
