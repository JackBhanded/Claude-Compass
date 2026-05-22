"""hookconfig.py — install/remove Claude Code hooks for Compass, safely.

Two hooks, both optional:
  * **SessionStart** runs ``compass hook`` once per session — re-syncs your
    profile and prints it as ``additionalContext`` (plus the occasional question).
  * **UserPromptSubmit** ("live mode") runs ``compass hook-prompt`` before *every*
    message, re-injecting your current profile — so edits take effect on your very
    next prompt, not only in new sessions.

``~/.claude/settings.json`` is strict JSON the user may have customised, so we
treat it as carefully as a memory file: refuse to write if it won't parse, back
it up first, write atomically, and detect our own hook (by event + tag) so
install is idempotent and uninstall removes only ours.
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
    "live_hook_command",
    "settings_path",
    "install_session_start_hook",
    "uninstall_session_start_hook",
    "install_live_hook",
    "uninstall_live_hook",
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


def live_hook_command(python: Optional[str] = None) -> str:
    py = python or sys.executable
    return f'"{py}" -m claude_compass hook-prompt'


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


# --------------------------------------------------------------------------- #
# Generic install/uninstall over a hook event (SessionStart / UserPromptSubmit)
# --------------------------------------------------------------------------- #

def _install_event_hook(claude_home: Path, event: str, command: str,
                        label: str) -> HookResult:
    path = settings_path(claude_home)
    data, err = _load_settings(path)
    if err:
        return HookResult(status="refused", path=path, message=err)

    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        return HookResult(status="refused", path=path,
                          message="The 'hooks' section of your settings.json "
                                  "isn't an object, so I left it alone.")
    arr = hooks.setdefault(event, [])
    if not isinstance(arr, list):
        return HookResult(status="refused", path=path,
                          message=f"Your settings.json has a '{event}' that isn't "
                                  "a list, so I left it alone to be safe.")

    for group in arr:
        if not isinstance(group, dict):
            continue
        for h in group.get("hooks", []):
            if isinstance(h, dict) and HOOK_TAG in str(h.get("command", "")):
                if h.get("command") == command:
                    return HookResult(status="unchanged", path=path,
                                      message=f"The {label} is already in place — "
                                              "you're all set.")
                h["command"] = command
                bak = write_text_atomic(path, _dump(data), backup=True)
                return HookResult(status="updated", path=path, backup_path=bak,
                                  message=f"Refreshed the {label} command (kept a "
                                          "backup of your old settings).")

    arr.append({"hooks": [{"type": "command", "command": command}]})
    bak = write_text_atomic(path, _dump(data), backup=path.exists())
    return HookResult(status="installed", path=path, backup_path=bak,
                      message=f"Installed the {label}. ")


def _uninstall_event_hook(claude_home: Path, event: str, label: str) -> HookResult:
    path = settings_path(claude_home)
    data, err = _load_settings(path)
    if err:
        return HookResult(status="refused", path=path, message=err)
    if not data:
        return HookResult(status="absent", path=path,
                          message="No settings.json yet — nothing to remove.")

    hooks = data.get("hooks")
    arr = hooks.get(event) if isinstance(hooks, dict) else None
    if not isinstance(arr, list):
        return HookResult(status="absent", path=path,
                          message=f"No {event} hooks here — nothing to remove.")

    removed = False
    new_groups = []
    for group in arr:
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
                          message=f"No Compass {label} found — nothing to remove.")

    if new_groups:
        hooks[event] = new_groups
    else:
        hooks.pop(event, None)
    if isinstance(hooks, dict) and not hooks:
        data.pop("hooks", None)

    bak = write_text_atomic(path, _dump(data), backup=True)
    return HookResult(status="removed", path=path, backup_path=bak,
                      message=f"Removed the Compass {label}. Your other settings "
                              "are untouched.")


# --------------------------------------------------------------------------- #
# Public wrappers
# --------------------------------------------------------------------------- #

def install_session_start_hook(claude_home: Path,
                               command: Optional[str] = None) -> HookResult:
    return _install_event_hook(claude_home, "SessionStart",
                               command or hook_command(),
                               "SessionStart hook")


def uninstall_session_start_hook(claude_home: Path) -> HookResult:
    return _uninstall_event_hook(claude_home, "SessionStart", "SessionStart hook")


def install_live_hook(claude_home: Path,
                      command: Optional[str] = None) -> HookResult:
    """UserPromptSubmit hook — re-injects your profile before every message, so
    edits take effect on your next prompt within the same session."""
    return _install_event_hook(claude_home, "UserPromptSubmit",
                               command or live_hook_command(),
                               "live (per-message) hook")


def uninstall_live_hook(claude_home: Path) -> HookResult:
    return _uninstall_event_hook(claude_home, "UserPromptSubmit",
                                 "live (per-message) hook")
