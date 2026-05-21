"""store.py — Claude Compass's profile store.

The single source of truth for *who the user is, to Claude*. Lives entirely in
Compass's own home (``~/.claude-compass/`` by default) and, like Lifejacket's
store, owns its files outright but still writes them atomically.

Layout::

    ~/.claude-compass/
        profile.json      # structured facets (the editable truth)
        profile.md        # generated: the curated text we inject into CLAUDE.md
        questions.json    # the inquisitive-question bank + which are answered
        manifest.json     # per-surface sync bookkeeping
        backups/          # timestamped backups of anything we change
        activity.log      # what Compass has been doing

A *facet* is one small, reviewable fact about how the user likes to work — e.g.
``communication: "wants warm but concise answers"``. The profile is deliberately
small and human-readable: it goes into every Claude session, and the user can
see and edit every word.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .safewrite import write_text_atomic

__all__ = [
    "Facet",
    "Store",
    "StoreError",
    "default_home",
    "PROFILE_BLOCK_ID",
    "PROFILE_VERSION",
    "FACET_CATEGORIES",
]

PROFILE_BLOCK_ID = "profile"
PROFILE_VERSION = 1

# The facets we organise a profile around. Order here = order in the rendered
# profile, so it reads naturally and the hash stays stable.
FACET_CATEGORIES = [
    ("communication", "Communication style"),
    ("feedback", "Feedback & honesty"),
    ("autonomy", "Autonomy & guardrails"),
    ("workflow", "How they like to work"),
    ("formatting", "Format & output"),
    ("expertise", "Background & expertise"),
    ("learning", "How they learn best"),
    ("codestyle", "Code & conventions"),
    ("safety", "Safety & boundaries"),
    ("domains", "Domains & tools"),
    ("accessibility", "Accessibility & wellbeing"),
    ("peeves", "Pet peeves / things to avoid"),
    ("other", "Other"),
]
_CATEGORY_KEYS = {k for k, _ in FACET_CATEGORIES}


class StoreError(Exception):
    """Something went wrong reading/writing the store. Messages are human-facing."""


def default_home() -> Path:
    """Where the profile store lives. Override with ``COMPASS_HOME``."""
    import os
    override = os.environ.get("COMPASS_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".claude-compass"


def _now_date() -> str:
    return datetime.now(timezone.utc).date().isoformat()


@dataclass
class Facet:
    """One reviewable fact about the user's working style.

    ``approved`` is the trust gate: only approved facets are ever rendered into
    the profile that gets injected. Things the user states themselves (``source
    == "you"``) are approved on the spot; things Compass *infers* (``source ==
    "history"``) start unapproved (pending) and never reach a Claude session
    until the user reviews and approves them."""

    category: str          # one of FACET_CATEGORIES keys
    text: str              # the human-readable statement
    source: str = "you"    # "you" (asked/manual) | "history" (inferred) | "import"
    approved: bool = True   # only approved facets are injected
    updated: str = field(default_factory=_now_date)

    def normalised_category(self) -> str:
        return self.category if self.category in _CATEGORY_KEYS else "other"


class Store:
    """Read/write access to the profile, the question bank, and bookkeeping."""

    def __init__(self, home: Optional[Path] = None):
        self.home = Path(home) if home is not None else default_home()

    # -- paths -------------------------------------------------------------- #
    @property
    def profile_path(self) -> Path:
        return self.home / "profile.json"

    @property
    def profile_md_path(self) -> Path:
        return self.home / "profile.md"

    @property
    def questions_path(self) -> Path:
        return self.home / "questions.json"

    @property
    def manifest_path(self) -> Path:
        return self.home / "manifest.json"

    @property
    def backups_dir(self) -> Path:
        return self.home / "backups"

    @property
    def activity_log_path(self) -> Path:
        return self.home / "activity.log"

    # -- lifecycle ---------------------------------------------------------- #
    def init(self) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        if not self.profile_path.exists():
            self._save_profile({"version": PROFILE_VERSION, "facets": []})

    def exists(self) -> bool:
        return self.profile_path.exists()

    # -- profile read/write ------------------------------------------------- #
    def load(self) -> List[Facet]:
        """Load all facets. [] if uninitialised."""
        if not self.profile_path.exists():
            return []
        try:
            raw = json.loads(self.profile_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise StoreError(
                f"I couldn't read your profile at {self.profile_path}. It may "
                f"have been edited into invalid JSON ({exc}). I left it alone "
                "rather than guess."
            ) from exc
        items = raw.get("facets", []) if isinstance(raw, dict) else []
        facets: List[Facet] = []
        for item in items:
            if not isinstance(item, dict) or not item.get("text"):
                continue
            facets.append(Facet(
                category=item.get("category", "other"),
                text=item["text"].strip(),
                source=item.get("source", "you"),
                # Missing 'approved' defaults to True so older manual profiles
                # keep working; inferred facets are always written with it.
                approved=bool(item.get("approved", True)),
                updated=item.get("updated", _now_date()),
            ))
        return facets

    def _save_profile(self, payload: dict) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        write_text_atomic(self.profile_path, text, backup=self.profile_path.exists())

    def save_facets(self, facets: List[Facet]) -> None:
        payload = {
            "version": PROFILE_VERSION,
            "facets": [
                {"category": f.normalised_category(), "text": f.text,
                 "source": f.source, "approved": bool(f.approved),
                 "updated": f.updated}
                for f in facets if f.text.strip()
            ],
        }
        self._save_profile(payload)

    # -- mutations ---------------------------------------------------------- #
    def add_facet(self, category: str, text: str, source: str = "you",
                  approved: Optional[bool] = None) -> Facet:
        """Add a facet. De-dupes on identical (category, text).

        ``approved`` defaults by source: things you state ("you") are approved
        immediately; anything inferred ("history") starts pending until you
        review it, so it never reaches a Claude session unapproved."""
        text = (text or "").strip()
        if not text:
            raise StoreError("A profile note can't be empty.")
        if approved is None:
            approved = (source == "you")
        facets = self.load()
        for f in facets:
            if f.category == category and f.text.lower() == text.lower():
                return f  # already present
        facet = Facet(category=category, text=text, source=source, approved=approved)
        facets.append(facet)
        self.save_facets(facets)
        return facet

    def remove_facet(self, index: int) -> bool:
        """Remove a facet by its 1-based index in render order."""
        ordered = self.ordered_facets()
        if not (1 <= index <= len(ordered)):
            return False
        target = ordered[index - 1]
        facets = self.load()
        kept = [f for f in facets if not (
            f.category == target.category and f.text == target.text)]
        if len(kept) == len(facets):
            return False
        self.save_facets(kept)
        return True

    def clear(self) -> None:
        self.save_facets([])

    def edit_facet(self, index: int, new_text: str) -> Optional[Facet]:
        """Edit a note's text by its 1-based index in :meth:`ordered_facets`.
        Editing is endorsing — the note becomes yours (source='you') and approved,
        so a fixed-up inferred note goes live. Returns the updated Facet or None."""
        new_text = (new_text or "").strip()
        if not new_text:
            return None
        ordered = self.ordered_facets()
        if not (1 <= index <= len(ordered)):
            return None
        target = ordered[index - 1]
        facets = self.load()
        for f in facets:
            if f.category == target.category and f.text == target.text:
                f.text = new_text
                f.source = "you"
                f.approved = True
                f.updated = _now_date()
                self.save_facets(facets)
                return f
        return None

    def approve_facet(self, index: int) -> bool:
        """Approve a pending facet by its 1-based index in :meth:`ordered_facets`
        (the same numbering shown in `show`/`review`)."""
        ordered = self.ordered_facets()
        if not (1 <= index <= len(ordered)):
            return False
        target = ordered[index - 1]
        facets = self.load()
        changed = False
        for f in facets:
            if f.category == target.category and f.text == target.text and not f.approved:
                f.approved = True
                changed = True
        if changed:
            self.save_facets(facets)
        return changed

    def approve_all(self) -> int:
        facets = self.load()
        n = 0
        for f in facets:
            if not f.approved:
                f.approved = True
                n += 1
        if n:
            self.save_facets(facets)
        return n

    # -- ordering / rendering ----------------------------------------------- #
    def _order(self):
        return {k: i for i, (k, _) in enumerate(FACET_CATEGORIES)}

    def ordered_facets(self) -> List[Facet]:
        """ALL facets (approved + pending) in category order — for display +
        indexing (so `show`, `review`, `forget`, `approve` share one numbering)."""
        order = self._order()
        return sorted(
            self.load(),
            key=lambda f: (order.get(f.normalised_category(), len(order)),
                           f.text.lower()),
        )

    def approved_facets(self) -> List[Facet]:
        return [f for f in self.ordered_facets() if f.approved]

    def pending_facets(self) -> List[Facet]:
        return [f for f in self.ordered_facets() if not f.approved]

    def render_profile(self, facets: Optional[List[Facet]] = None) -> str:
        """Render the curated profile text Compass injects. ONLY approved facets
        are included. Deterministic, so the safe-write hash is stable (re-syncing
        unchanged content writes nothing)."""
        if facets is None:
            facets = self.approved_facets()
        else:
            order = self._order()
            facets = sorted([f for f in facets if f.approved],
                            key=lambda f: (order.get(f.normalised_category(), len(order)),
                                           f.text.lower()))
            return self._render_lines(facets)
        return self._render_lines(facets)

    def _render_lines(self, facets: List[Facet]) -> str:
        lines = [
            "About the person you're working with (kept current by Claude "
            "Compass, so every session can adapt to how they like to work):",
            "",
        ]
        if not facets:
            lines.append("- _(no profile yet — run `compass ask` or `compass "
                         "learn` to begin)_")
            return "\n".join(lines)

        labels = dict(FACET_CATEGORIES)
        by_cat: Dict[str, List[Facet]] = {}
        for f in facets:
            by_cat.setdefault(f.normalised_category(), []).append(f)
        for key, label in FACET_CATEGORIES:
            if key in by_cat:
                lines.append(f"**{label}:**")
                for f in by_cat[key]:
                    lines.append(f"- {f.text}")
                lines.append("")
        return "\n".join(lines).rstrip()

    def write_profile_md(self, text: Optional[str] = None) -> Path:
        if text is None:
            text = self.render_profile()
        write_text_atomic(self.profile_md_path, text + "\n",
                          backup=self.profile_md_path.exists())
        return self.profile_md_path

    # -- manifest ----------------------------------------------------------- #
    def load_manifest(self) -> dict:
        if not self.manifest_path.exists():
            return {"version": 1, "surfaces": {}}
        try:
            return json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"version": 1, "surfaces": {}}

    def save_manifest(self, manifest: dict) -> None:
        text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
        write_text_atomic(self.manifest_path, text,
                          backup=self.manifest_path.exists())

    def record_sync(self, surface_key: str, *, path: str, status: str,
                    profile_hash: str) -> None:
        manifest = self.load_manifest()
        manifest.setdefault("surfaces", {})[surface_key] = {
            "path": path,
            "status": status,
            "profile_hash": profile_hash,
            "last_sync": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        self.save_manifest(manifest)

    # -- activity log ------------------------------------------------------- #
    def log_event(self, message: str) -> None:
        try:
            self.home.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with self.activity_log_path.open("a", encoding="utf-8") as fh:
                fh.write(f"{ts}  {message}\n")
        except OSError:
            pass

    def read_recent_events(self, limit: int = 20) -> List[str]:
        p = self.activity_log_path
        if not p.exists():
            return []
        try:
            lines = [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
        except OSError:
            return []
        return lines[-limit:]

    # -- state (the pause kill-switch) -------------------------------------- #
    @property
    def state_path(self) -> Path:
        return self.home / "state.json"

    def _load_state(self) -> dict:
        if not self.state_path.exists():
            return {}
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def is_paused(self) -> bool:
        """When paused, sync REMOVES the profile block from every surface — so
        Compass stops influencing your sessions immediately — while keeping your
        profile data so you can fix it and resume."""
        return bool(self._load_state().get("paused", False))

    def set_paused(self, paused: bool) -> None:
        st = self._load_state()
        st["paused"] = bool(paused)
        write_text_atomic(self.state_path, json.dumps(st, indent=2) + "\n",
                          backup=self.state_path.exists())
