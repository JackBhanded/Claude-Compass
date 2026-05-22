"""Tests for hookconfig.py — safely editing ~/.claude/settings.json."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from claude_compass.hookconfig import (
    HOOK_TAG,
    hook_command,
    install_live_hook,
    install_session_start_hook,
    live_hook_command,
    settings_path,
    uninstall_live_hook,
    uninstall_session_start_hook,
)

CMD = '"python" -m claude_compass hook'


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_install_into_empty_home(tmp_path):
    res = install_session_start_hook(tmp_path, command=CMD)
    assert res.status == "installed"
    groups = read(settings_path(tmp_path))["hooks"]["SessionStart"]
    assert any(HOOK_TAG in h["command"] for g in groups for h in g["hooks"])


def test_install_idempotent(tmp_path):
    install_session_start_hook(tmp_path, command=CMD)
    assert install_session_start_hook(tmp_path, command=CMD).status == "unchanged"
    data = read(settings_path(tmp_path))
    count = sum(1 for g in data["hooks"]["SessionStart"]
                for h in g["hooks"] if HOOK_TAG in h["command"])
    assert count == 1


def test_install_preserves_existing(tmp_path):
    sp = settings_path(tmp_path)
    sp.write_text(json.dumps({
        "model": "opus",
        "hooks": {"SessionStart": [
            {"hooks": [{"type": "command", "command": "echo hi"}]}]},
    }), encoding="utf-8")
    install_session_start_hook(tmp_path, command=CMD)
    data = read(sp)
    assert data["model"] == "opus"
    cmds = [h["command"] for g in data["hooks"]["SessionStart"] for h in g["hooks"]]
    assert "echo hi" in cmds and any(HOOK_TAG in c for c in cmds)


def test_install_refuses_invalid_json(tmp_path):
    sp = settings_path(tmp_path)
    sp.write_text("{ not json", encoding="utf-8")
    res = install_session_start_hook(tmp_path, command=CMD)
    assert res.status == "refused" and res.ok is False
    assert sp.read_text(encoding="utf-8") == "{ not json"


def test_uninstall_removes_only_ours(tmp_path):
    sp = settings_path(tmp_path)
    sp.write_text(json.dumps({"hooks": {"SessionStart": [
        {"hooks": [{"type": "command", "command": "echo hi"}]}]}}), encoding="utf-8")
    install_session_start_hook(tmp_path, command=CMD)
    assert uninstall_session_start_hook(tmp_path).status == "removed"
    cmds = [h["command"] for g in read(sp)["hooks"]["SessionStart"] for h in g["hooks"]]
    assert "echo hi" in cmds and not any(HOOK_TAG in c for c in cmds)


def test_uninstall_absent_graceful(tmp_path):
    assert uninstall_session_start_hook(tmp_path).status == "absent"


def test_hook_command_quotes_python():
    cmd = hook_command(python="/path with space/python")
    assert cmd.startswith('"/path with space/python"') and "claude_compass hook" in cmd


# -- live (UserPromptSubmit) hook ----------------------------------------- #

_LIVE = '"python" -m claude_compass hook-prompt'


def test_live_hook_coexists_with_session_start(tmp_path):
    install_session_start_hook(tmp_path, command=CMD)
    install_live_hook(tmp_path, command=_LIVE)
    data = read(settings_path(tmp_path))
    assert "SessionStart" in data["hooks"]
    assert "UserPromptSubmit" in data["hooks"]


def test_uninstall_live_leaves_session_start(tmp_path):
    install_session_start_hook(tmp_path, command=CMD)
    install_live_hook(tmp_path, command=_LIVE)
    assert uninstall_live_hook(tmp_path).status == "removed"
    data = read(settings_path(tmp_path))
    assert "UserPromptSubmit" not in data["hooks"]
    assert "SessionStart" in data["hooks"]      # the other hook is untouched


def test_live_idempotent(tmp_path):
    install_live_hook(tmp_path, command=_LIVE)
    assert install_live_hook(tmp_path, command=_LIVE).status == "unchanged"


def test_live_hook_command():
    assert "hook-prompt" in live_hook_command(python="py")
