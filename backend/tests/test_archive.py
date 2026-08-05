"""Unit tests for the saved-schedule archive (file-per-save in a folder)."""

from __future__ import annotations

import json
import os

import pytest

from schedy.archive import EXT, Archive, contained


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


def test_an_id_can_only_ever_name_a_file_in_the_folder(tmp_path):
    """The id is matched against the folder's listing, never joined onto it.

    Stated as a property rather than a list of bad strings: a deny-list only
    rejects the traversals someone thought of, and the three below — an absolute
    path, a Windows separator, a reserved device name — are ones a `..` check
    alone would hand straight to the filesystem.
    """
    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / f"secret{EXT}"
    secret.write_text('{"name": "secret"}', encoding="utf-8")
    arc = Archive(tmp_path / "saves")
    arc.save("real", _payload(), {})

    for hostile in ("../outside/secret", "..\\outside\\secret", str(outside / "secret"),
                    "CON", "", ".", "real/../../outside/secret"):
        got = arc.get(hostile)
        deleted = arc.delete(hostile)
        renamed = arc.rename(hostile, "renamed")
        assert (got, deleted, renamed) == (None, False, None), hostile

    # ...and the one real save is still reachable, the outsider untouched.
    assert arc.get("real")["name"] == "real"
    assert secret.exists()


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


# ---- the folder itself ---------------------------------------------------- #

def test_contained_accepts_the_root_and_what_sits_under_it(tmp_path):
    root = tmp_path / "Schedy"
    root.mkdir()
    assert contained(root, str(root)) == root.resolve()
    assert contained(root, str(root / "saves")) == (root / "saves").resolve()
    assert contained(root, str(root / "a" / "b")) == (root / "a" / "b").resolve()
    # A relative folder is read as relative to the root, which is the only
    # reading that cannot escape it.
    assert contained(root, "saves-2026") == (root / "saves-2026").resolve()
    # The target need not exist yet — the planner is naming a folder to create.
    assert contained(root, str(root / "not-there")) is not None


def test_contained_rejects_anything_outside_the_root(tmp_path):
    root = tmp_path / "Schedy"
    root.mkdir()
    for outside in (str(tmp_path), str(tmp_path / "elsewhere"),
                    str(root) + "-next-door",  # prefix match is not containment
                    str(root / ".." / "elsewhere")):
        assert contained(root, outside) is None, outside


def test_contained_follows_symlinks_out_of_the_root(tmp_path):
    """A link inside the root pointing out of it is still outside the root.

    Resolving before comparing is what makes this hold; comparing the literal
    path would accept the link and write the planner's saves anywhere.
    """
    root = tmp_path / "Schedy"
    root.mkdir()
    (tmp_path / "elsewhere").mkdir()
    try:
        (root / "escape").symlink_to(tmp_path / "elsewhere", target_is_directory=True)
    except (OSError, NotImplementedError):  # Windows without developer mode
        pytest.skip("symlinks not available")
    assert contained(root, str(root / "escape")) is None


def test_contained_holds_when_the_case_differs(tmp_path):
    """Windows folder names are case-insensitive; a plain compare is not.

    On a case-sensitive filesystem these genuinely are different folders and
    the rejection is correct, so the test asserts only that the call is decided
    rather than crashing — the point is that `normcase` drives it either way.
    """
    root = tmp_path / "Schedy"
    root.mkdir()
    got = contained(root, str(tmp_path / "schedy" / "saves"))
    expected = (tmp_path / "schedy" / "saves").resolve() if os.name == "nt" else None
    assert got == expected


# ---- a save belongs to a term ------------------------------------------ #

def test_a_save_records_the_term_it_came_from(tmp_path):
    a = Archive(tmp_path)
    meta = a.save("winter plan", {"courses": []}, {"sessions": 1}, term="2026-27-winter")
    assert meta.term == "2026-27-winter"
    assert a.list()[0].term == "2026-27-winter"


def test_a_save_written_before_terms_existed_reports_no_term(tmp_path):
    # It predates the concept; guessing one would be inventing a fact.
    a = Archive(tmp_path)
    a.save("old plan", {"courses": []}, {})
    assert a.list()[0].term is None
