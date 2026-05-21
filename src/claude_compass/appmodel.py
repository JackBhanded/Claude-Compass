"""appmodel.py — the brains behind the double-click app, with NO GUI imports.

The PySide6 window in ``app.py`` asks this module for a :class:`Snapshot` to
draw and calls these functions on button clicks. Keeping the logic here (Qt-free)
means the whole app behaviour is unit-tested without a display.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .hookconfig import HOOK_TAG, settings_path
from .questions import QuestionBank
from .store import FACET_CATEGORIES, Store
from .surfaces import claude_code_home, discover_surfaces, load_extra_surfaces
from .sync import profile_fingerprint, sync_all

__all__ = [
    "FacetView", "SurfaceView", "Snapshot", "build_snapshot",
    "hook_is_on", "answer_question", "approve", "approve_all",
    "forget", "edit", "quickstart", "set_paused", "do_sync",
]

_LABELS = dict(FACET_CATEGORIES)


@dataclass
class FacetView:
    index: int
    category_label: str
    text: str
    source: str
    approved: bool


@dataclass
class SurfaceView:
    label: str
    state: str   # in_sync | out_of_date | never | attention | paused
    detail: str


@dataclass
class Snapshot:
    facets: List[FacetView]
    surfaces: List[SurfaceView]
    hook_on: bool
    paused: bool
    next_question_text: Optional[str]
    next_question_id: Optional[str]
    next_question_options: List[str]
    next_question_multi: bool
    recent: List[str]


def hook_is_on(claude_home=None) -> bool:
    sp = settings_path(claude_home or claude_code_home())
    if not sp.exists():
        return False
    try:
        return HOOK_TAG in sp.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False


def build_snapshot(store: Store, *, claude_home=None) -> Snapshot:
    ordered = store.ordered_facets()
    facets = [
        FacetView(
            index=i,
            category_label=_LABELS.get(f.normalised_category(), f.category),
            text=f.text, source=f.source, approved=f.approved,
        )
        for i, f in enumerate(ordered, 1)
    ]

    profile_text = store.render_profile()
    fp = profile_fingerprint(profile_text)
    manifest = store.load_manifest().get("surfaces", {})
    surfs = discover_surfaces(claude_home=claude_home,
                              extra_paths=load_extra_surfaces(store.home))
    paused = store.is_paused()
    views: List[SurfaceView] = []
    for s in surfs:
        entry = manifest.get(s.key)
        if not entry:
            state, detail = "never", "Never synced"
        elif entry.get("status") in ("tampered", "conflict"):
            state, detail = "attention", "Needs your eyes"
        elif entry.get("profile_hash") == "(paused)":
            state, detail = "paused", "Paused (removed)"
        elif entry.get("profile_hash") == fp:
            state, detail = "in_sync", "In sync"
        else:
            state, detail = "out_of_date", "Out of date"
        views.append(SurfaceView(label=s.label, state=state, detail=detail))

    q = QuestionBank(store).next_question()
    return Snapshot(
        facets=facets, surfaces=views, hook_on=hook_is_on(claude_home),
        paused=paused,
        next_question_text=q.text if q else None,
        next_question_id=q.id if q else None,
        next_question_options=list(q.options) if q else [],
        next_question_multi=bool(q.multi) if q else False,
        recent=store.read_recent_events(8),
    )


def answer_question(store: Store, qid: str, text: str):
    return QuestionBank(store).answer(qid, text)


def quickstart(store: Store, *, claude_home=None) -> int:
    """Fill recommended defaults for a strong baseline, then sync."""
    n = QuestionBank(store).quickstart()
    sync_all(store, claude_home=claude_home)
    return n


def approve(store: Store, index: int) -> bool:
    return store.approve_facet(index)


def approve_all(store: Store) -> int:
    return store.approve_all()


def forget(store: Store, index: int, *, claude_home=None) -> bool:
    """Remove a facet AND re-sync, so it's gone everywhere (no ghost memories)."""
    if not store.remove_facet(index):
        return False
    sync_all(store, claude_home=claude_home)
    return True


def edit(store: Store, index: int, new_text: str, *, claude_home=None) -> bool:
    """Edit a facet's text AND re-sync, so the change reaches every session."""
    if store.edit_facet(index, new_text) is None:
        return False
    sync_all(store, claude_home=claude_home)
    return True


def set_paused(store: Store, paused: bool, *, claude_home=None):
    """Flip the kill-switch and immediately apply it (pause removes the block,
    resume restores it)."""
    store.set_paused(paused)
    store.log_event("paused by user" if paused else "resumed by user")
    return sync_all(store, claude_home=claude_home)


def do_sync(store: Store, *, claude_home=None, force: bool = False):
    return sync_all(store, claude_home=claude_home, force=force)
