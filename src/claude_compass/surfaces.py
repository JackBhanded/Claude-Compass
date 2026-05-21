"""surfaces.py — find the Claude memory file(s) to sync the profile into.

Same elegant target as Lifejacket: the user-level ``~/.claude/CLAUDE.md`` is read
by **both** Claude Code and Cowork, so syncing that one file makes every surface
profile-aware. Pure path logic, fully testable with an injected home dir.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

__all__ = [
    "Surface",
    "claude_code_home",
    "discover_surfaces",
    "load_extra_surfaces",
]


@dataclass
class Surface:
    key: str
    label: str
    path: Path
    kind: str
    exists: bool

    @property
    def parent_exists(self) -> bool:
        return self.path.parent.exists()


def claude_code_home() -> Path:
    """The Claude Code config dir. Honours ``CLAUDE_CONFIG_DIR``; else ``~/.claude``."""
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".claude"


def discover_surfaces(
    claude_home: Optional[Path] = None,
    extra_paths: Optional[List[Path]] = None,
) -> List[Surface]:
    ch = Path(claude_home) if claude_home is not None else claude_code_home()
    surfaces: List[Surface] = []

    cc_file = ch / "CLAUDE.md"
    if ch.exists() or cc_file.exists():
        surfaces.append(Surface(
            key="claude-code:user",
            label="Claude Code + Cowork (user memory ~/.claude/CLAUDE.md)",
            path=cc_file,
            kind="claude-code",
            exists=cc_file.exists(),
        ))

    seen = {s.path.resolve() for s in surfaces if s.path.exists()}
    for raw in (extra_paths or []):
        p = Path(raw).expanduser()
        rp = p.resolve()
        if rp in seen:
            continue
        seen.add(rp)
        surfaces.append(Surface(
            key=f"manual:{p.name}:{abs(hash(str(rp))) % 100000}",
            label=f"Manual ({p})",
            path=p,
            kind="manual",
            exists=p.exists(),
        ))
    return surfaces


def load_extra_surfaces(store_home: Path) -> List[Path]:
    """Opt-in extra surface paths from ``<store>/surfaces.json``. Never crashes."""
    cfg = Path(store_home) / "surfaces.json"
    if not cfg.exists():
        return []
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    paths = data.get("paths", []) if isinstance(data, dict) else []
    out: List[Path] = []
    for entry in paths:
        if isinstance(entry, str) and entry.strip():
            out.append(Path(entry).expanduser())
    return out
