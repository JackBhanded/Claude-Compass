"""Tests for declination Phase 1: ledger append, the heuristic detector, the
transcript reader, and the read-only ``compass scan`` command.

Phase 1 records *evidence* but still changes nothing a Claude session reads —
these tests hold that line.
"""

from __future__ import annotations

import json
from pathlib import Path

from claude_compass.cli import main
from claude_compass.detector import scan_turns
from claude_compass.store import Facet, Obs, Store
from claude_compass.transcripts import read_user_turns, slug_for_path


def fresh(tmp_path) -> Store:
    s = Store(home=tmp_path / "cc")
    s.init()
    return s


def _obs(signal="CONTRADICT"):
    return Obs(ts="2026-05-22T00:00:00Z", session="s", signal=signal,
               strength="weak", source="heuristic")


# -- ledger append + bound + tally (the deferred Phase 0 behavior) -------- #

def test_add_observation_bounds_and_tallies():
    f = Facet(category="communication", text="Emoji: Sparingly")
    for _ in range(12):
        f.add_observation(_obs("CONTRADICT"), max_n=10)
    assert len(f.ledger) == 10                       # keeps only the most recent N
    assert f.ledger_summary.get("CONTRADICT") == 2   # the 2 trimmed rolled into the tally


def test_record_observations_attaches_by_id(tmp_path):
    s = fresh(tmp_path)
    s.add_facet("communication", "Emoji: Sparingly")
    fid = s.load()[0].id
    n = s.record_observations([(fid, _obs("SUGGEST_ALT"))])
    assert n == 1
    g = s.load()[0]
    assert len(g.ledger) == 1 and g.ledger[0].signal == "SUGGEST_ALT"
    # an unknown id is silently ignored, never invents a facet
    assert s.record_observations([("nope", _obs())]) == 0


# -- detector heuristics -------------------------------------------------- #

def test_scan_turns_maps_phrases():
    hits = scan_turns(["hey, be blunt with me", "please drop the emoji", "nothing here"])
    by_q = {h.question_id: h for h in hits}
    assert by_q["fb_bluntness"].signal == "SUGGEST_ALT"
    assert by_q["fb_bluntness"].suggests == "Just say it straight"
    assert by_q["comm_emoji"].suggests == "Never"
    # a plain sentence fires nothing
    assert not scan_turns(["just a normal message about the weather"])


# -- transcript reader ---------------------------------------------------- #

def test_slug_for_path():
    assert slug_for_path(r"C:\Users\Jack\Docs") == "C--Users-Jack-Docs"


def write_transcript(path: Path) -> None:
    records = [
        {"type": "user", "message": {"role": "user", "content": "hey be blunt with me"}},
        {"type": "assistant", "message": {"role": "assistant", "content": "sure"}},
        {"type": "user", "isMeta": True, "message": {"role": "user", "content": "<meta>"}},
        {"type": "user", "message": {"role": "user",
                                     "content": [{"type": "tool_result", "content": "x"}]}},
        {"type": "user", "message": {"role": "user", "content": "drop the emoji please"}},
        {"type": "summary", "summary": "..."},
    ]
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


def test_read_user_turns_filters_and_offsets(tmp_path):
    p = tmp_path / "t.jsonl"
    write_transcript(p)
    turns, offset = read_user_turns(p, since_line=0)
    assert turns == ["hey be blunt with me", "drop the emoji please"]  # meta + tool_result skipped
    assert offset == 6
    # a follow-up scan from the saved offset sees nothing new
    assert read_user_turns(p, since_line=offset) == ([], 6)


def test_read_user_turns_survives_garbage(tmp_path):
    p = tmp_path / "bad.jsonl"
    p.write_text('not json\n{"type":"user","message":{"role":"user","content":"be blunt"}}\n',
                 encoding="utf-8")
    turns, _ = read_user_turns(p)
    assert turns == ["be blunt"]   # malformed line skipped, never raised


# -- the scan command (read-only) ----------------------------------------- #

def _setup_store_and_transcript(tmp_path, monkeypatch):
    monkeypatch.setenv("COMPASS_HOME", str(tmp_path / "cc"))
    s = Store(tmp_path / "cc")
    s.init()
    s.add_facet("communication", "Emoji: Sparingly")        # comm_emoji -> suggest
    s.add_facet("feedback", "Bluntness: Honest but tactful")  # fb_bluntness -> auto
    p = tmp_path / "session.jsonl"
    write_transcript(p)
    return s, p


def test_scan_dry_run_records_nothing(tmp_path, monkeypatch, capsys):
    s, p = _setup_store_and_transcript(tmp_path, monkeypatch)
    assert main(["scan", "--file", str(p), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "SUGGEST_ALT" in out                      # it reported findings
    assert all(not f.ledger for f in s.load())       # ...but recorded nothing
    assert s.get_scan_offset(str(p)) == 0            # ...and didn't move the position


def test_scan_records_observations_and_advances(tmp_path, monkeypatch):
    s, p = _setup_store_and_transcript(tmp_path, monkeypatch)
    assert main(["scan", "--file", str(p)]) == 0
    by_text = {f.text: f for f in s.load()}
    assert len(by_text["Emoji: Sparingly"].ledger) == 1
    assert len(by_text["Bluntness: Honest but tactful"].ledger) == 1
    assert s.get_scan_offset(str(p)) == 6            # position advanced
    # re-running finds nothing new
    main(["scan", "--file", str(p)])
    assert len(s.load()[0].ledger) >= 1              # not double-counted


def test_scan_skips_fixed_facets(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("COMPASS_HOME", str(tmp_path / "cc"))
    s = Store(tmp_path / "cc")
    s.init()
    s.add_facet("feedback", "Bluntness: Honest but tactful")
    # user pins bluntness to fixed — declination must keep hands off
    facets = s.load()
    facets[0].mode = "fixed"
    s.save_facets(facets)
    p = tmp_path / "session.jsonl"
    write_transcript(p)
    main(["scan", "--file", str(p)])
    assert not s.load()[0].ledger, "a fixed facet must record no observations"


def test_scan_does_not_change_rendered_profile(tmp_path, monkeypatch):
    s, p = _setup_store_and_transcript(tmp_path, monkeypatch)
    before = s.render_profile()
    main(["scan", "--file", str(p)])
    assert s.render_profile() == before, "recording evidence must not touch what sessions read"
