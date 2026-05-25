"""Tests for the Phase 0 declination data model + v1→v2 migration.

Phase 0 is invisible groundwork: the profile gains id / question_id / mode /
ledger fields and old profiles migrate, but **nothing a Claude session reads
changes**. These tests lock that promise in.
"""

from __future__ import annotations

import json
from pathlib import Path

from claude_compass.declination import (
    default_mode_for,
    is_risky,
    match_question_id,
)
from claude_compass.store import Facet, Obs, Store, PROFILE_VERSION


def fresh(tmp_path) -> Store:
    s = Store(home=tmp_path / "cc")
    s.init()
    return s


def write_v1_profile(home: Path, facets: list) -> None:
    """Write a pre-declination (v1) profile.json by hand — no id/mode fields."""
    home.mkdir(parents=True, exist_ok=True)
    (home / "profile.json").write_text(
        json.dumps({"version": 1, "facets": facets}, indent=2) + "\n",
        encoding="utf-8",
    )


# -- pure classification logic (declination.py) --------------------------- #

def test_question_id_matching():
    assert match_question_id("communication", "Tone: Warm and friendly") == "comm_tone"
    assert match_question_id("communication", "Address: Use my first name") == "comm_name"
    # free-text note (no "Label:" prefix) is unmappable
    assert match_question_id("other", "I like jazz") is None
    # a label that isn't in the bank for that category
    assert match_question_id("communication", "Nonsense: whatever") is None


def test_default_mode_derivation():
    assert default_mode_for("comm_length") == "fixed"        # context-dependent
    assert default_mode_for("wf_thoroughness") == "fixed"    # context-dependent
    assert default_mode_for("fmt_lists") == "suggest"        # mirror-prone
    assert default_mode_for("safe_secrets") == "suggest"     # guardrail/risky
    assert default_mode_for("comm_name") == "suggest"        # identity
    assert default_mode_for("comm_tone") == "auto"           # safe, learnable
    assert default_mode_for(None) == "suggest"               # unclassifiable → fail closed


def test_is_risky_fails_closed():
    assert is_risky(None) is True            # unmappable
    assert is_risky("safe_secrets") is True  # guardrail
    assert is_risky("comm_name") is True     # identity
    assert is_risky("comm_tone") is False    # safe


# -- migration (store.py) ------------------------------------------------- #

def test_migration_backfills_and_persists(tmp_path):
    home = tmp_path / "cc"
    write_v1_profile(home, [
        {"category": "communication", "text": "Tone: Warm and friendly",
         "source": "you", "approved": True},
        {"category": "communication", "text": "Answer length: Short and scannable",
         "source": "you", "approved": True},
        {"category": "other", "text": "I like jazz", "source": "you", "approved": True},
    ])
    facets = Store(home=home).load()
    by_text = {f.text: f for f in facets}

    # ids generated for every facet
    assert all(f.id for f in facets)
    # modes derived correctly
    assert by_text["Tone: Warm and friendly"].mode == "auto"
    assert by_text["Answer length: Short and scannable"].mode == "fixed"
    assert by_text["I like jazz"].mode == "suggest"        # unclassifiable → fail closed
    # question_ids matched (or None for free text)
    assert by_text["Tone: Warm and friendly"].question_id == "comm_tone"
    assert by_text["Answer length: Short and scannable"].question_id == "comm_length"
    assert by_text["I like jazz"].question_id is None

    # persisted at v2, with the new fields, plus a backup of the old file
    data = json.loads((home / "profile.json").read_text(encoding="utf-8"))
    assert data["version"] == PROFILE_VERSION == 2
    assert all("id" in it and "mode" in it for it in data["facets"])
    assert list(home.glob("profile.json.*.bak")), "migration should back up the v1 file"


def test_ids_stable_across_reload(tmp_path):
    home = tmp_path / "cc"
    write_v1_profile(home, [
        {"category": "feedback", "text": "Bluntness: Just say it straight",
         "source": "you", "approved": True},
    ])
    first = Store(home=home).load()[0].id      # migrates + persists
    second = Store(home=home).load()[0].id     # now v2 — must read the same id
    assert first == second, "ids must persist on migration, not regenerate per load"


def test_migration_preserves_user_mode(tmp_path):
    """A mode already on disk is a user choice — migration must never recompute
    it, even when the derived default would differ."""
    home = tmp_path / "cc"
    write_v1_profile(home, [
        # fmt_lists would derive to 'suggest', but the user pinned it to 'auto'
        {"category": "formatting", "text": "Lists vs prose: Bullet lists",
         "source": "you", "approved": True, "mode": "auto"},
    ])
    f = Store(home=home).load()[0]
    assert f.mode == "auto", "stored mode override must survive migration"
    assert f.question_id == "fmt_lists"  # still backfilled where it was missing


# -- new facets carry the metadata --------------------------------------- #

def test_add_facet_sets_question_id_and_mode(tmp_path):
    s = fresh(tmp_path)
    s.add_facet("communication", "Tone: Terse and to-the-point")
    f = s.load()[0]
    assert f.id and f.question_id == "comm_tone" and f.mode == "auto"


# -- serialization round-trip incl. ledger ------------------------------- #

def test_serialization_roundtrip_with_ledger(tmp_path):
    s = fresh(tmp_path)
    facet = Facet(category="workflow", text="Rhythm: Long deep-focus stretches",
                  question_id="wf_rhythm", mode="auto",
                  ledger=[Obs(ts="2026-05-22T00:00:00Z", session="abc",
                              signal="SUPPORT", strength="strong",
                              suggests=None, source="behavior")])
    s.save_facets([facet])
    g = s.load()[0]
    assert g.id == facet.id and g.question_id == "wf_rhythm" and g.mode == "auto"
    assert len(g.ledger) == 1
    o = g.ledger[0]
    assert o.signal == "SUPPORT" and o.strength == "strong" and o.source == "behavior"


def test_empty_ledger_omitted_from_json(tmp_path):
    s = fresh(tmp_path)
    s.add_facet("domains", "Platform: Windows")
    item = json.loads(s.profile_path.read_text(encoding="utf-8"))["facets"][0]
    assert "ledger" not in item, "empty ledgers should be omitted to keep profiles tidy"


# -- the zero-behavior-change guard --------------------------------------- #

def test_render_output_unchanged_by_v2_fields(tmp_path):
    """The injected block must be byte-identical regardless of id/mode/ledger —
    that is what keeps the safe-write hash stable and sessions unaffected."""
    s = fresh(tmp_path)
    s.add_facet("communication", "Tone: Warm and friendly")  # mode auto, has id
    s.add_facet("feedback", "Bluntness: Just say it straight")
    rendered = s.render_profile()

    # the human-facing facet text is present...
    assert "Tone: Warm and friendly" in rendered
    assert "Bluntness: Just say it straight" in rendered
    # ...and none of the v2 plumbing leaks into what a session reads
    for leak in ("mode", "question_id", "auto", "suggest", "fixed", "ledger",
                 s.load()[0].id):
        assert leak not in rendered, f"v2 field {leak!r} leaked into the injected profile"
