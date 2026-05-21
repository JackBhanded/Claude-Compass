"""Tests for the trust + control layer:
- the approval gate (inferred facets never injected until approved)
- the pause kill-switch (removes the block from every surface)
"""

from __future__ import annotations

import pytest

from claude_compass.safewrite import SyncStatus, read_managed_block
from claude_compass.store import Store
from claude_compass.sync import sync_all


def make_store(tmp_path) -> Store:
    s = Store(home=tmp_path / "cc")
    s.init()
    return s


def make_claude_home(tmp_path):
    ch = tmp_path / "dot-claude"
    ch.mkdir()
    return ch


# -- approval gate -------------------------------------------------------- #

def test_you_facets_approved_inferred_pending(tmp_path):
    s = make_store(tmp_path)
    s.add_facet("communication", "warm but concise", source="you")
    s.add_facet("expertise", "10y backend (guessed)", source="history")
    assert len(s.approved_facets()) == 1
    assert len(s.pending_facets()) == 1
    assert s.pending_facets()[0].source == "history"


def test_pending_facet_not_rendered_or_injected(tmp_path):
    s = make_store(tmp_path)
    ch = make_claude_home(tmp_path)
    s.add_facet("communication", "warm but concise", source="you")
    s.add_facet("peeves", "INFERRED THING", source="history")
    # Not in the rendered profile...
    assert "INFERRED THING" not in s.render_profile()
    assert "warm but concise" in s.render_profile()
    # ...and not injected into CLAUDE.md.
    sync_all(s, claude_home=ch)
    block = read_managed_block(ch / "CLAUDE.md", "profile")
    assert "INFERRED THING" not in block
    assert "warm but concise" in block


def test_approve_promotes_into_profile(tmp_path):
    s = make_store(tmp_path)
    s.add_facet("communication", "a known fact", source="you")
    s.add_facet("peeves", "inferred guess", source="history")
    # 'communication' sorts before 'peeves'; pending is index 2.
    ordered = s.ordered_facets()
    idx = next(i for i, f in enumerate(ordered, 1) if not f.approved)
    assert s.approve_facet(idx) is True
    assert "inferred guess" in s.render_profile()
    assert s.pending_facets() == []


def test_approve_all(tmp_path):
    s = make_store(tmp_path)
    s.add_facet("workflow", "g1", source="history")
    s.add_facet("domains", "g2", source="history")
    assert s.approve_all() == 2
    assert len(s.approved_facets()) == 2


# -- pause kill-switch ---------------------------------------------------- #

def test_pause_removes_block_resume_restores(tmp_path):
    s = make_store(tmp_path)
    ch = make_claude_home(tmp_path)
    s.add_facet("communication", "warm but concise")
    sync_all(s, claude_home=ch)
    cc = ch / "CLAUDE.md"
    assert "COMPASS:BEGIN" in cc.read_text(encoding="utf-8")

    # Pause -> next sync pulls the block out of CLAUDE.md entirely.
    s.set_paused(True)
    assert s.is_paused() is True
    sync_all(s, claude_home=ch)
    assert "COMPASS:BEGIN" not in cc.read_text(encoding="utf-8")
    # The profile data itself is untouched in the store.
    assert any(f.text == "warm but concise" for f in s.load())

    # Resume -> the block comes back on the next sync.
    s.set_paused(False)
    sync_all(s, claude_home=ch)
    assert "warm but concise" in read_managed_block(cc, "profile")


def test_pause_preserves_user_content_and_foreign_blocks(tmp_path):
    s = make_store(tmp_path)
    ch = make_claude_home(tmp_path)
    cc = ch / "CLAUDE.md"
    lj = ("<!-- LIFEJACKET:BEGIN id=projects v=1 -->\n- **Meter**\n"
          "<!-- LIFEJACKET:END id=projects v=1 sha256=" + ("0" * 64) + " -->\n")
    cc.write_text("# Mine\n\n" + lj + "\nkeep\n", encoding="utf-8")
    s.add_facet("communication", "concise")
    sync_all(s, claude_home=ch)
    s.set_paused(True)
    sync_all(s, claude_home=ch)
    text = cc.read_text(encoding="utf-8")
    assert "COMPASS:BEGIN" not in text   # ours pulled
    assert "LIFEJACKET:BEGIN" in text    # Lifejacket's untouched
    assert "Meter" in text and "keep" in text  # user + foreign content safe


def test_state_survives_reload(tmp_path):
    s = make_store(tmp_path)
    s.set_paused(True)
    assert Store(home=s.home).is_paused() is True
