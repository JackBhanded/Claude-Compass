"""Tests for surfaces.py + sync.py — discovery and end-to-end profile sync."""

from __future__ import annotations

import pytest

from claude_compass.safewrite import SyncStatus, read_managed_block
from claude_compass.store import Store
from claude_compass.surfaces import discover_surfaces, load_extra_surfaces
from claude_compass.sync import preview_all, profile_fingerprint, sync_all


def make_store(tmp_path) -> Store:
    s = Store(home=tmp_path / "cc")
    s.init()
    s.add_facet("communication", "warm but concise")
    s.add_facet("feedback", "be blunt, skip the praise")
    return s


def make_claude_home(tmp_path):
    ch = tmp_path / "dot-claude"
    ch.mkdir()
    return ch


# -- discovery ------------------------------------------------------------ #

def test_discovers_user_surface(tmp_path):
    ch = make_claude_home(tmp_path)
    surfaces = discover_surfaces(claude_home=ch)
    assert len(surfaces) == 1 and surfaces[0].key == "claude-code:user"
    assert surfaces[0].exists is False


def test_no_surface_when_absent(tmp_path):
    assert discover_surfaces(claude_home=tmp_path / "nope") == []


def test_extra_surfaces_config(tmp_path):
    home = tmp_path / "cc"
    home.mkdir()
    (home / "surfaces.json").write_text('{"paths": ["~/a.md", ""]}', encoding="utf-8")
    assert len(load_extra_surfaces(home)) == 1


# -- fingerprint ---------------------------------------------------------- #

def test_fingerprint_eol_immune():
    assert profile_fingerprint("a\nb") == profile_fingerprint("a\r\nb\n")


# -- end to end ----------------------------------------------------------- #

def test_sync_creates_block(tmp_path):
    s = make_store(tmp_path)
    ch = make_claude_home(tmp_path)
    reports = sync_all(s, claude_home=ch)
    assert len(reports) == 1 and reports[0].result.status == SyncStatus.CREATED
    text = (ch / "CLAUDE.md").read_text(encoding="utf-8")
    assert "COMPASS:BEGIN" in text and "warm but concise" in text


def test_sync_idempotent(tmp_path):
    s = make_store(tmp_path)
    ch = make_claude_home(tmp_path)
    sync_all(s, claude_home=ch)
    cc = ch / "CLAUDE.md"
    m1 = cc.stat().st_mtime_ns
    reports = sync_all(s, claude_home=ch)
    assert reports[0].result.status == SyncStatus.UNCHANGED
    assert cc.stat().st_mtime_ns == m1


def test_sync_updates_when_profile_changes(tmp_path):
    s = make_store(tmp_path)
    ch = make_claude_home(tmp_path)
    sync_all(s, claude_home=ch)
    s.add_facet("workflow", "ship, feel, refine")
    reports = sync_all(s, claude_home=ch)
    assert reports[0].result.status == SyncStatus.UPDATED
    assert "ship, feel, refine" in read_managed_block(ch / "CLAUDE.md", "profile")


def test_dry_run_writes_nothing(tmp_path):
    s = make_store(tmp_path)
    ch = make_claude_home(tmp_path)
    reports = preview_all(s, claude_home=ch)
    assert reports[0].result.status == SyncStatus.CREATED
    assert not (ch / "CLAUDE.md").exists()
    assert s.load_manifest()["surfaces"] == {}


def test_sync_preserves_user_content(tmp_path):
    s = make_store(tmp_path)
    ch = make_claude_home(tmp_path)
    cc = ch / "CLAUDE.md"
    cc.write_text("# My own notes\n\nkeep me\n", encoding="utf-8")
    sync_all(s, claude_home=ch)
    text = cc.read_text(encoding="utf-8")
    assert "keep me" in text and "COMPASS:BEGIN" in text


def test_sync_records_manifest_and_log(tmp_path):
    s = make_store(tmp_path)
    ch = make_claude_home(tmp_path)
    sync_all(s, claude_home=ch)
    entry = s.load_manifest()["surfaces"]["claude-code:user"]
    assert entry["status"] == "created" and len(entry["profile_hash"]) == 64
    assert any("sync" in e for e in s.read_recent_events())


def test_handedit_not_clobbered(tmp_path):
    s = make_store(tmp_path)
    ch = make_claude_home(tmp_path)
    sync_all(s, claude_home=ch)
    cc = ch / "CLAUDE.md"
    cc.write_text(cc.read_text(encoding="utf-8").replace(
        "warm but concise", "MY HAND EDIT"), encoding="utf-8")
    reports = sync_all(s, claude_home=ch)
    assert reports[0].result.status == SyncStatus.TAMPERED
    assert "MY HAND EDIT" in cc.read_text(encoding="utf-8")


# -- the key cross-tool guarantee, end to end ----------------------------- #

def test_coexists_with_lifejacket_block_through_sync(tmp_path):
    s = make_store(tmp_path)
    ch = make_claude_home(tmp_path)
    cc = ch / "CLAUDE.md"
    # Pretend Lifejacket already wrote its projects block + the user has notes.
    lj = ("<!-- LIFEJACKET:BEGIN id=projects v=1 -->\n"
          "- **Claude Meter** - shipped\n"
          "<!-- LIFEJACKET:END id=projects v=1 sha256=" + ("0" * 64) + " -->\n")
    cc.write_text("# Notes\n\n" + lj + "\nmine\n", encoding="utf-8")

    sync_all(s, claude_home=ch)            # Compass adds its profile block
    s.add_facet("workflow", "iterates fast")
    sync_all(s, claude_home=ch)            # ...and updates it

    text = cc.read_text(encoding="utf-8")
    assert "Claude Meter" in text          # Lifejacket's block untouched
    assert "LIFEJACKET:BEGIN" in text
    assert "mine" in text                  # user content untouched
    assert "iterates fast" in read_managed_block(cc, "profile")
