"""hookconfig.py — install/remove the Claude Code SessionStart hook, safely.

The hook makes Compass automatic: each session start runs ``compass hook``, which
re-syncs your profile and prints it as ``additionalContext`` (and, now and then,
gently surfaces one calibration question).

``~/.claude/settings.json`` is strict JSON the user may have customised, so we
treat it as carefully as a memory file: refuse to write if it won't parse, back
it up first, write atomically, and detect our own hook so install is idempotent
and uninstall removes only ours. (Vendored from Lifejacket's hookconfig.)
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .safewrite import write_text_atomic

__all__ = [
    "HookResult",
    "hook_command",
    "settings_path",
    "install_session_start_hook",
    "uninstall_session_start_hook",
    "HOOK_TAG",
]

HOOK_TAG = "claude_compass"


@dataclass
class HookResult:
    status: str          # installed | updated | unchanged | removed | absent | refused
    path: Path
    backup_path: Optional[Path] = None
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.status != "refused"


def hook_command(python: Optional[str] = None) -> str:
    py = python or sys.executable
    return f'"{py}" -m claude_compass hook'


def settings_path(claude_home: Path) -> Path:
    return Path(claude_home) / "settings.json"


def _load_settings(path: Path):
    if not path.exists():
        return {}, None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"couldn't read {path} ({exc})"
    if not text.strip():
        return {}, None
    try:
        return json.loads(text), None
    except json.JSONDecodeError as exc:
        return None, (
            f"{path} isn't valid JSON ({exc}). I didn't touch it. You can add "
            "the hook by hand, or fix the JSON and re-run."
        )


def _dump(data) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def install_session_start_hook(
    claude_home: Path, command: Optional[str] = None
) -> HookResult:
    path = settings_path(claude_home)
    command = command or hook_command()
    data, err = _load_settings(path)
    if err:
        return HookResult(status="refused", path=path, message=err)

    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        return HookResult(status="refused", path=path,
                          message="The 'hooks' section of your settings.json "
                                  "isn't an object, so I left it alone.")
    session_start = hooks.setdefault("SessionStart", [])
    if not isinstance(session_start, list):
        return HookResult(status="refused", path=path,
                          message="Your settings.json has a 'SessionStart' that "
                                  "isn't a list, so I left it alone to be safe.")

    for group in session_start:
        if not isinstance(group, dict):
            continue
        for h in group.get("hooks", []):
            if isinstance(h, dict) and HOOK_TAG in str(h.get("command", "")):
                if h.get("command") == command:
                    return HookResult(status="unchanged", path=path,
                                      message="The SessionStart hook is already "
                                              "in place — you're all set.")
                h["command"] = command
                bak = write_text_atomic(path, _dump(data), backup=True)
                return HookResult(status="updated", path=path, backup_path=bak,
                                  message="Refreshed the SessionStart hook command "
                                          "(kept a backup of your old settings).")

    session_start.append({"hooks": [{"type": "command", "command": command}]})
    bak = write_text_atomic(path, _dump(data), backup=path.exists())
    return HookResult(status="installed", path=path, backup_path=bak,
                      message="Installed the SessionStart hook — Compass will now "
                              "keep your profile current automatically. ")


def uninstall_session_start_hook(claude_home: Path) -> HookResult:
    path = settings_path(claude_home)
    data, err = _load_settings(path)
    if err:
        return HookResult(status="refused", path=path, message=err)
    if not data:
        return HookResult(status="absent", path=path,
                          message="No settings.json yet — nothing to remove.")

    hooks = data.get("hooks")
    session_start = hooks.get("SessionStart") if isinstance(hooks, dict) else None
    if not isinstance(session_start, list):
        return HookResult(status="absent", path=path,
                          message="No SessionStart hooks here — nothing to remove.")

    removed = False
    new_groups = []
    for group in session_start:
        if not isinstance(group, dict):
            new_groups.append(group)
            continue
        kept = [h for h in group.get("hooks", [])
                if not (isinstance(h, dict) and HOOK_TAG in str(h.get("command", "")))]
        if len(kept) != len(group.get("hooks", [])):
            removed = True
        if kept:
            group = dict(group)
            group["hooks"] = kept
            new_groups.append(group)
    if not removed:
        return HookResult(status="absent", path=path,
                          message="No Compass hook found — nothing to remove.")

    if new_groups:
        hooks["SessionStart"] = new_groups
    else:
        hooks.pop("SessionStart", None)
    if isinstance(hooks, dict) and not hooks:
        data.pop("hooks", None)

    bak = write_text_atomic(path, _dump(data), backup=True)
    return HookResult(status="removed", path=path, backup_path=bak,
                      message="Removed the Compass SessionStart hook. Your other "
                              "settings are untouched.")
