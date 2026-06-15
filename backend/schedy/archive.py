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
        """Resolve an id to a file path, rejecting traversal / bad ids."""
        if not save_id or "/" in save_id or "\\" in save_id or save_id in (".", ".."):
            return None
        p = (self.root / f"{save_id}{EXT}")
        # Defence in depth: the resolved file must sit directly in root.
        try:
            if p.resolve().parent != self.root.resolve():
                return None
        except OSError:
            return None
        return p

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
