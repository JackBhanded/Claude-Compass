"""Tests for the CLI — drives main() with env-isolated home dirs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from claude_compass.cli import main
from claude_compass.safewrite import read_managed_block
from claude_compass.store import Store


@pytest.fixture
def env(tmp_path, monkeypatch):
    cc = tmp_path / "cc"
    ch = tmp_path / "dot-claude"
    ch.mkdir()
    monkeypatch.setenv("COMPASS_HOME", str(cc))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(ch))
    return {"cc": cc, "ch": ch}


def test_init(env, capsys):
    assert main(["init"]) == 0
    assert (env["cc"] / "profile.json").exists()


def test_ask_then_answer_creates_and_syncs(env, capsys):
    main(["init"])
    main(["ask"])
    out = capsys.readouterr().out
    # grab the question id the CLI suggested
    assert "answer" in out
    main(["answer", "comm_tone", "warm but concise"])
    main(["sync"])
    capsys.readouterr()
    cc = env["ch"] / "CLAUDE.md"
    assert "warm but concise" in read_managed_block(cc, "profile")


def test_show_lists_with_pending(env, capsys):
    main(["init"])
    main(["answer", "fb_bluntness", "be blunt"])
    capsys.readouterr()
    # add an inferred (pending) facet directly
    Store(home=env["cc"]).add_facet("expertise", "guessed senior", source="history")
    main(["show"])
    out = capsys.readouterr().out
    assert "be blunt" in out
    assert "pending review" in out


def test_forget_deletes_everywhere(env, capsys):
    main(["init"])
    main(["answer", "comm_tone", "terse please"])
    main(["sync"])
    cc = env["ch"] / "CLAUDE.md"
    assert "terse please" in read_managed_block(cc, "profile")
    capsys.readouterr()
    # forget the only facet (index 1)
    assert main(["forget", "1"]) == 0
    # gone from the store AND from CLAUDE.md (delete == gone everywhere)
    block = read_managed_block(cc, "profile")
    assert block is None or "terse please" not in block


def test_approve_promotes_pending(env, capsys):
    main(["init"])
    s = Store(home=env["cc"])
    s.add_facet("peeves", "don't over-explain", source="history")
    capsys.readouterr()
    assert main(["approve", "--all"]) == 0
    main(["sync"])
    cc = env["ch"] / "CLAUDE.md"
    assert "don't over-explain" in read_managed_block(cc, "profile")


def test_pause_and_resume_killswitch(env, capsys):
    main(["init"])
    main(["answer", "comm_tone", "concise"])
    main(["sync"])
    cc = env["ch"] / "CLAUDE.md"
    assert "COMPASS:BEGIN" in cc.read_text(encoding="utf-8")
    capsys.readouterr()
    assert main(["pause"]) == 0
    assert "COMPASS:BEGIN" not in cc.read_text(encoding="utf-8")
    assert main(["resume"]) == 0
    assert "concise" in read_managed_block(cc, "profile")


def test_status_runs(env, capsys):
    main(["init"])
    main(["answer", "comm_tone", "warm"])
    main(["sync"])
    capsys.readouterr()
    assert main(["status"]) == 0
    out = capsys.readouterr().out
    assert "status" in out.lower() and "Profile" in out


def test_hook_emits_valid_json_with_profile(env, capsys):
    main(["init"])
    main(["answer", "comm_tone", "warm but concise"])
    capsys.readouterr()
    assert main(["hook"]) == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "warm but concise" in payload["hookSpecificOutput"]["additionalContext"]


def test_hook_paused_emits_empty(env, capsys):
    main(["init"])
    main(["answer", "comm_tone", "warm"])
    main(["pause"])
    capsys.readouterr()
    assert main(["hook"]) == 0
    payload = json.loads(capsys.readouterr().out.strip())
    # paused -> no profile leaked into the session context
    assert "warm" not in payload["hookSpecificOutput"]["additionalContext"]


def test_install_and_uninstall_hook(env, capsys):
    main(["init"])
    assert main(["install-hook"]) == 0
    sp = env["ch"] / "settings.json"
    assert "claude_compass" in sp.read_text(encoding="utf-8")
    assert main(["uninstall-hook"]) == 0
    assert "claude_compass" not in sp.read_text(encoding="utf-8")


def test_no_command_prints_help(env, capsys):
    assert main([]) == 0
    assert "compass" in capsys.readouterr().out.lower()
