"""Tests for store.py — the profile store + render."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from claude_compass.store import (
    Facet,
    Store,
    StoreError,
    default_home,
)


def fresh(tmp_path) -> Store:
    s = Store(home=tmp_path / "cc")
    s.init()
    return s


# -- init / lifecycle ----------------------------------------------------- #

def test_init_creates_store(tmp_path):
    s = Store(home=tmp_path / "cc")
    assert not s.exists()
    s.init()
    assert s.exists() and s.profile_path.exists() and s.backups_dir.exists()


def test_init_idempotent_keeps_data(tmp_path):
    s = fresh(tmp_path)
    s.add_facet("communication", "wants terse answers")
    s.init()
    assert [f.text for f in s.load()] == ["wants terse answers"]


def test_load_empty_when_uninitialised(tmp_path):
    assert Store(home=tmp_path / "nope").load() == []


# -- add / remove / dedupe ------------------------------------------------ #

def test_add_and_load(tmp_path):
    s = fresh(tmp_path)
    s.add_facet("feedback", "be blunt, skip the praise")
    facets = s.load()
    assert len(facets) == 1
    assert facets[0].category == "feedback"
    assert facets[0].source == "you"


def test_add_dedupes(tmp_path):
    s = fresh(tmp_path)
    s.add_facet("communication", "Warm but concise")
    s.add_facet("communication", "warm but concise")  # case-insensitive dupe
    assert len(s.load()) == 1


def test_empty_facet_rejected(tmp_path):
    s = fresh(tmp_path)
    with pytest.raises(StoreError):
        s.add_facet("other", "   ")


def test_unknown_category_normalised_to_other(tmp_path):
    s = fresh(tmp_path)
    s.add_facet("nonsense", "something")
    assert s.ordered_facets()[0].normalised_category() == "other"


def test_edit_facet_endorses_it(tmp_path):
    s = fresh(tmp_path)
    s.add_facet("peeves", "inferred guess", source="history")  # pending
    f = s.edit_facet(1, "my corrected note")
    assert f is not None and f.text == "my corrected note"
    assert f.approved is True and f.source == "you"   # editing = endorsing
    assert [x.text for x in s.load()] == ["my corrected note"]


def test_edit_facet_bad_input(tmp_path):
    s = fresh(tmp_path)
    s.add_facet("communication", "x")
    assert s.edit_facet(99, "y") is None     # out of range
    assert s.edit_facet(1, "   ") is None     # empty


def test_remove_by_index(tmp_path):
    s = fresh(tmp_path)
    s.add_facet("communication", "a comms note")
    s.add_facet("feedback", "a feedback note")
    ordered = s.ordered_facets()
    # communication sorts before feedback, so index 1 is the comms note.
    assert ordered[0].category == "communication"
    assert s.remove_facet(1) is True
    remaining = [f.category for f in s.load()]
    assert remaining == ["feedback"]
    assert s.remove_facet(99) is False


# -- persistence / corruption -------------------------------------------- #

def test_round_trip(tmp_path):
    s = fresh(tmp_path)
    s.add_facet("workflow", "ship, feel, refine")
    s2 = Store(home=s.home)
    assert [f.text for f in s2.load()] == ["ship, feel, refine"]


def test_valid_json_with_version(tmp_path):
    s = fresh(tmp_path)
    s.add_facet("domains", "python, powershell")
    data = json.loads(s.profile_path.read_text(encoding="utf-8"))
    assert data["version"] >= 1 and isinstance(data["facets"], list)


def test_corrupt_profile_raises_friendly(tmp_path):
    s = fresh(tmp_path)
    s.profile_path.write_text("{not json", encoding="utf-8")
    with pytest.raises(StoreError):
        s.load()


# -- render --------------------------------------------------------------- #

def test_render_groups_by_category_in_order(tmp_path):
    s = fresh(tmp_path)
    s.add_facet("peeves", "don't over-format with bullets")
    s.add_facet("communication", "warm but concise")
    text = s.render_profile()
    # communication comes before peeves in FACET_CATEGORIES order.
    assert text.index("Communication style") < text.index("Pet peeves")
    assert "warm but concise" in text
    assert "don't over-format" in text


def test_render_deterministic(tmp_path):
    s = fresh(tmp_path)
    s.add_facet("communication", "b note")
    s.add_facet("communication", "a note")
    assert s.render_profile() == s.render_profile()
    # alphabetical within a category
    t = s.render_profile()
    assert t.index("a note") < t.index("b note")


def test_render_empty_has_placeholder(tmp_path):
    s = fresh(tmp_path)
    assert "no profile yet" in s.render_profile()


def test_write_profile_md(tmp_path):
    s = fresh(tmp_path)
    s.add_facet("expertise", "10 years backend, new to React")
    p = s.write_profile_md()
    assert p.exists() and "new to React" in p.read_text(encoding="utf-8")


# -- manifest / activity log --------------------------------------------- #

def test_record_sync_round_trips(tmp_path):
    s = fresh(tmp_path)
    s.record_sync("claude-code:user", path="/x/CLAUDE.md",
                  status="updated", profile_hash="abc")
    entry = s.load_manifest()["surfaces"]["claude-code:user"]
    assert entry["status"] == "updated" and entry["profile_hash"] == "abc"


def test_activity_log(tmp_path):
    s = fresh(tmp_path)
    assert s.read_recent_events() == []
    s.log_event("first")
    s.log_event("second")
    events = s.read_recent_events()
    assert len(events) == 2 and "first" in events[0]


# -- home override -------------------------------------------------------- #

def test_default_home_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("COMPASS_HOME", str(tmp_path / "custom"))
    assert default_home() == Path(tmp_path / "custom")


def test_default_home_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv("COMPASS_HOME", raising=False)
    assert default_home().name == ".claude-compass"
