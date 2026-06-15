"""Unit tests for the saved-schedule archive (file-per-save in a folder)."""

from __future__ import annotations

import json

from schedy.archive import EXT, Archive


def _payload():
    return {
        "placements": {"x-lec": {"day": 0, "start_box": 1, "room_id": "hall1"}},
        "courses": [{"number": "00540319"}],
        "offered_rows": None,
        "availability": {},
        "calendar": None,
    }


def test_save_writes_a_file_and_returns_meta(tmp_path):
    arc = Archive(tmp_path / "saves")
    meta = arc.save("2026 Spring", _payload(), {"sessions": 1, "hard": 0}, note="final")
    assert meta.id and meta.name == "2026 Spring"
    assert meta.created_at  # ISO timestamp present
    assert meta.stats["sessions"] == 1 and meta.note == "final"
    # exactly one save file landed in the chosen folder
    files = list((tmp_path / "saves").glob(f"*{EXT}"))
    assert len(files) == 1


def test_list_is_lightweight_and_get_has_payload(tmp_path):
    arc = Archive(tmp_path)
    arc.save("A", _payload(), {"sessions": 1})
    metas = arc.list()
    assert len(metas) == 1
    # listing must not carry the heavy payload
    assert not hasattr(metas[0], "payload")
    full = arc.get(metas[0].id)
    assert full["payload"]["courses"][0]["number"] == "00540319"


def test_self_contained_roundtrip(tmp_path):
    arc = Archive(tmp_path)
    p = _payload()
    meta = arc.save("scenario", p, {"sessions": 1})
    got = arc.get(meta.id)["payload"]
    assert got == p  # catalog + settings + placements travel together


def test_duplicate_names_get_distinct_ids(tmp_path):
    arc = Archive(tmp_path)
    a = arc.save("Same Name", _payload(), {})
    b = arc.save("Same Name", _payload(), {})
    assert a.id != b.id
    assert len(arc.list()) == 2


def test_hebrew_name_roundtrips(tmp_path):
    arc = Archive(tmp_path)
    meta = arc.save("סמסטר אביב 2026", _payload(), {})
    assert arc.get(meta.id)["name"] == "סמסטר אביב 2026"


def test_rename_changes_name_and_renames_file(tmp_path):
    arc = Archive(tmp_path)
    meta = arc.save("draft", _payload(), {})
    old_file = tmp_path / f"{meta.id}{EXT}"
    new = arc.rename(meta.id, "2026 final")
    assert new is not None and new.name == "2026 final"
    assert not old_file.exists()  # old file gone
    assert arc.get(new.id)["name"] == "2026 final"


def test_delete_removes_the_file(tmp_path):
    arc = Archive(tmp_path)
    meta = arc.save("x", _payload(), {})
    assert arc.delete(meta.id) is True
    assert arc.get(meta.id) is None
    assert arc.delete(meta.id) is False  # idempotent / missing


def test_unknown_id_and_traversal_are_rejected(tmp_path):
    arc = Archive(tmp_path)
    arc.save("real", _payload(), {})
    assert arc.get("does-not-exist") is None
    # path-traversal ids never resolve outside the folder
    assert arc.get("../secret") is None
    assert arc.get("..") is None
    assert arc.delete("../secret") is False


def test_forbidden_chars_stripped_from_filename(tmp_path):
    arc = Archive(tmp_path)
    meta = arc.save('a/b:c*?"<>|d', _payload(), {})
    fname = f"{meta.id}{EXT}"
    assert not any(ch in fname for ch in '/\\:*?"<>|')
    # display name is preserved verbatim even though the filename is sanitised
    assert arc.get(meta.id)["name"] == 'a/b:c*?"<>|d'


def test_malformed_file_is_skipped_not_fatal(tmp_path):
    arc = Archive(tmp_path)
    arc.save("ok", _payload(), {})
    (tmp_path / f"broken{EXT}").write_text("{not json", encoding="utf-8")
    metas = arc.list()  # must not raise
    assert [m.name for m in metas] == ["ok"]
    assert json.loads  # sanity: json imported
