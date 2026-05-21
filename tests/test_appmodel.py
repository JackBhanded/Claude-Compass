"""Tests for appmodel.py — the GUI's brains, verified without any GUI."""

from __future__ import annotations

import pytest

from claude_compass.appmodel import (
    answer_question, approve, approve_all, build_snapshot, do_sync, forget,
    set_paused,
)
from claude_compass.safewrite import read_managed_block
from claude_compass.store import Store


def make_env(tmp_path):
    cc = tmp_path / "cc"
    ch = tmp_path / "dot-claude"
    ch.mkdir()
    s = Store(home=cc)
    s.init()
    return s, ch


def test_snapshot_basics(tmp_path):
    s, ch = make_env(tmp_path)
    s.add_facet("communication", "warm but concise", source="you")
    s.add_facet("expertise", "guessed senior", source="history")
    snap = build_snapshot(s, claude_home=ch)
    assert len(snap.facets) == 2
    assert snap.paused is False and snap.hook_on is False
    assert snap.next_question_id is not None
    assert any(not fv.approved for fv in snap.facets)        # the inferred one
    assert snap.surfaces and snap.surfaces[0].state == "never"


def test_snapshot_in_sync_after_sync(tmp_path):
    s, ch = make_env(tmp_path)
    s.add_facet("communication", "concise")
    do_sync(s, claude_home=ch)
    snap = build_snapshot(s, claude_home=ch)
    assert snap.surfaces[0].state == "in_sync"


def test_answer_question_adds_live_facet(tmp_path):
    s, ch = make_env(tmp_path)
    f = answer_question(s, "fb_bluntness", "be blunt")
    assert f is not None and f.approved is True
    assert any("be blunt" in fv.text for fv in build_snapshot(s, claude_home=ch).facets)


def test_approve_then_visible(tmp_path):
    s, ch = make_env(tmp_path)
    s.add_facet("peeves", "no over-explaining", source="history")
    snap = build_snapshot(s, claude_home=ch)
    idx = next(fv.index for fv in snap.facets if not fv.approved)
    assert approve(s, idx) is True
    do_sync(s, claude_home=ch)
    assert "no over-explaining" in read_managed_block(ch / "CLAUDE.md", "profile")


def test_forget_removes_everywhere(tmp_path):
    s, ch = make_env(tmp_path)
    answer_question(s, "comm_tone", "terse")
    do_sync(s, claude_home=ch)
    assert "terse" in read_managed_block(ch / "CLAUDE.md", "profile")
    assert forget(s, 1, claude_home=ch) is True
    block = read_managed_block(ch / "CLAUDE.md", "profile")
    assert block is None or "terse" not in block


def test_pause_kill_switch(tmp_path):
    s, ch = make_env(tmp_path)
    answer_question(s, "comm_tone", "concise")
    do_sync(s, claude_home=ch)
    cc = ch / "CLAUDE.md"
    assert "COMPASS:BEGIN" in cc.read_text(encoding="utf-8")
    set_paused(s, True, claude_home=ch)
    assert "COMPASS:BEGIN" not in cc.read_text(encoding="utf-8")
    set_paused(s, False, claude_home=ch)
    assert "concise" in read_managed_block(cc, "profile")
