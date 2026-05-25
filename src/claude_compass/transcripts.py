"""transcripts.py — read the user's *local* Claude Code transcripts.

Claude Code writes one JSONL file per session under
``~/.claude/projects/<slug>/<session-uuid>.jsonl`` (the slug is the working
directory with every non-alphanumeric character turned into ``-``). Each line is
one event record with a ``type`` and, for messages, a ``message: {role, content}``.

For declination we only care about **genuinely typed user turns**:

    type == "user"  and  message.role == "user"  and  content is a *string*

When ``content`` is a list (tool results), it's machinery, not the user
speaking — we skip it. Everything stays on the local disk; nothing is uploaded
here. Verified against real transcripts on 2026-05-22.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Optional, Tuple

__all__ = ["default_projects_dir", "slug_for_path", "find_latest_transcript",
           "read_user_turns"]


def default_projects_dir() -> Path:
    return Path.home() / ".claude" / "projects"


def slug_for_path(path: str) -> str:
    """Claude Code's project-folder slug: every non-alphanumeric char → '-'.
    E.g. ``C:\\Users\\Jack\\Documents`` → ``C--Users-Jack-Documents``."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def find_latest_transcript(cwd: Optional[str] = None,
                           projects_dir: Optional[Path] = None) -> Optional[Path]:
    """The most-recently-modified transcript. Prefers the folder matching ``cwd``
    (the session you're most likely chatting in); otherwise the newest across all
    projects. Returns ``None`` if there are none."""
    base = Path(projects_dir) if projects_dir is not None else default_projects_dir()
    if not base.exists():
        return None
    candidates: List[Path] = []
    if cwd:
        sub = base / slug_for_path(cwd)
        if sub.exists():
            candidates = list(sub.glob("*.jsonl"))
    if not candidates:
        candidates = list(base.glob("*/*.jsonl"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def read_user_turns(path: Path, since_line: int = 0) -> Tuple[List[str], int]:
    """Return ``(new_user_turns, total_line_count)`` for ``path``, reading only
    lines at or after ``since_line``. The returned line count is the caller's
    next ``since_line`` — so a follow-up scan sees only what's new.

    Robust by design: unreadable files yield ``([], since_line)`` and malformed
    JSON lines are skipped, never raised — a scan must never crash a session."""
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return [], since_line
    turns: List[str] = []
    for raw in lines[max(0, since_line):]:
        raw = raw.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if rec.get("type") != "user" or rec.get("isMeta"):
            continue
        msg = rec.get("message")
        if not isinstance(msg, dict) or msg.get("role") != "user":
            continue
        content = msg.get("content")
        if isinstance(content, str) and content.strip():
            turns.append(content.strip())
    return turns, len(lines)
