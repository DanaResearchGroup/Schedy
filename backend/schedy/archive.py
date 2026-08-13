"""Saved-schedule archive — one self-contained JSON file per saved schedule.

A saved schedule ("good solution") is a frozen, self-contained scenario: the
placements plus a copy of the catalog, skeleton rows, availability and calendar
as they were when saved. That makes year-over-year work safe — freezing this
year's schedule, then editing the catalog for next year, never disturbs the
saved copy — and lets every saved alternative reload faithfully for comparison.

Files live in a user-chosen folder (see ``api`` for resolution), so the saves
are visible, portable and backup-friendly: copying the folder copies every
saved schedule. The module is deliberately filesystem-only and pure of any web
concerns, so it can be unit-tested in isolation.

Windows-proof by design: paths via ``pathlib``, UTF-8 files (Hebrew names round
-trip), filenames stripped of the Windows-forbidden set, and ids sanitised
against path traversal.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

EXT = ".schedy.json"
SCHEMA_VERSION = 1

# Characters not allowed in Windows filenames (plus control chars). Unicode
# letters — including Hebrew — are kept, since NTFS and ext4 both accept them.
_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _slug(name: str) -> str:
    """A filesystem-safe, human-readable stem derived from a display name."""
    s = _FORBIDDEN.sub("", name)
    s = re.sub(r"\s+", "-", s.strip())
    s = s.strip(". ")  # Windows rejects trailing dots/spaces
    return s[:60] or "schedule"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def contained(root: str | Path, candidate: str | Path) -> Path | None:
    """`candidate` as an absolute path under `root`, or None if it escapes.

    The saves folder is chosen by the planner over HTTP, so "which folder" is
    request data and cannot be trusted to stay where the app lives. This is the
    boundary: a relative candidate is read as relative to `root` — the only
    reading that cannot escape it — and an absolute one has to already be
    inside.

    Both sides are resolved first, so a symlink planted inside the root and
    pointing out of it is rejected on where it leads rather than accepted on
    where it sits. Comparison goes through `os.path.normcase`, because on
    Windows ``C:\\Users\\X`` and ``c:\\users\\x`` are one folder and a plain
    string compare would say otherwise. The separator is required after the
    root so that a sibling named ``Schedy-next-door`` cannot pass as ``Schedy``.

    The target need not exist: the planner is usually naming a folder to create.
    """
    try:
        base = Path(root).resolve()
        p = Path(candidate)
        p = p.resolve() if p.is_absolute() else (base / p).resolve()
    except (OSError, ValueError):  # unreadable, or a path the OS rejects outright
        return None
    b, c = os.path.normcase(str(base)), os.path.normcase(str(p))
    if c != b and not c.startswith(b + os.sep):
        return None
    return p


@dataclass(frozen=True)
class SavedMeta:
    """Lightweight listing entry — everything but the heavy payload."""

    id: str
    name: str
    created_at: str
    stats: dict
    note: str | None = None

    def as_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "created_at": self.created_at,
            "stats": self.stats, "note": self.note,
        }


class Archive:
    """A folder of saved schedules. The id of a save is its filename stem."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    # ---- internals -------------------------------------------------- #
    def _ensure_root(self) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root

    def _path_for(self, save_id: str) -> Path | None:
        """Resolve a save id to its file, or None if the folder holds no such save.

        The path comes from the folder's own listing rather than from joining
        the id onto the root. The id is only ever *compared* with a stem already
        found on disk, so nothing a caller can send — traversal, an absolute
        path, a Windows separator, a reserved device name — is able to name a
        file outside the folder. A deny-list would instead have to enumerate
        every such trick correctly, forever.
        """
        if not save_id:
            return None
        try:
            for p in self.root.glob(f"*{EXT}"):
                if p.name[: -len(EXT)] == save_id:
                    return p
        except OSError:  # folder gone or unreadable
            return None
        return None

    def _unique_stem(self, name: str, *, exclude: Path | None = None) -> str:
        base = _slug(name)
        stem, n = base, 1
        while True:
            candidate = self.root / f"{stem}{EXT}"
            if not candidate.exists() or candidate == exclude:
                return stem
            n += 1
            stem = f"{base}-{n}"

    # ---- operations ------------------------------------------------- #
    def save(self, name: str, payload: dict, stats: dict,
             note: str | None = None) -> SavedMeta:
        """Write a new self-contained save; returns its listing metadata."""
        self._ensure_root()
        stem = self._unique_stem(name)
        meta = SavedMeta(id=stem, name=name, created_at=_now_iso(),
                         stats=stats, note=note)
        doc = {
            "schema": SCHEMA_VERSION,
            "name": name, "created_at": meta.created_at,
            "note": note, "stats": stats, "payload": payload,
        }
        (self.root / f"{stem}{EXT}").write_text(
            json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        return meta

    def list(self) -> list[SavedMeta]:
        """All saves, newest first. Malformed files are skipped, not fatal."""
        if not self.root.exists():
            return []
        out: list[SavedMeta] = []
        for p in self.root.glob(f"*{EXT}"):
            try:
                doc = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            stem = p.name[: -len(EXT)]
            out.append(SavedMeta(
                id=stem, name=doc.get("name", stem),
                created_at=doc.get("created_at", ""),
                stats=doc.get("stats", {}), note=doc.get("note"),
            ))
        out.sort(key=lambda m: m.created_at, reverse=True)
        return out

    def get(self, save_id: str) -> dict | None:
        """The full document (incl. payload), or None if missing/invalid."""
        p = self._path_for(save_id)
        if not p or not p.exists():
            return None
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        doc["id"] = save_id
        return doc

    def delete(self, save_id: str) -> bool:
        p = self._path_for(save_id)
        if not p or not p.exists():
            return False
        p.unlink()
        return True

    def rename(self, save_id: str, name: str) -> SavedMeta | None:
        """Rename a save; the file is renamed too so the folder stays readable."""
        p = self._path_for(save_id)
        if not p or not p.exists():
            return None
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        doc["name"] = name
        new_stem = self._unique_stem(name, exclude=p)
        new_path = self.root / f"{new_stem}{EXT}"
        new_path.write_text(
            json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        if new_path != p:
            p.unlink()
        return SavedMeta(
            id=new_stem, name=name, created_at=doc.get("created_at", ""),
            stats=doc.get("stats", {}), note=doc.get("note"),
        )
