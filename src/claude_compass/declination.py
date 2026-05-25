"""declination.py — Compass's self-correcting engine (Phase 0: classification).

*Declination* (navigation) is the drift between magnetic north and true north
that changes over time and must be corrected. This module is where Compass keeps
the profile pointing at *true* north as the user's working style shifts.

Phase 0 ships only the **pure classification logic** the v1→v2 migration needs:
how to map an existing free-text facet back to the calibration question it came
from, and what *mode* a facet should default to. Later phases add the detector,
the evidence-ledger queries, and the auto/suggest/fixed actions.

A facet's **mode** decides what declination may do to it:

* ``auto``    — learn and change it silently (low mirror-risk dials),
* ``suggest`` — learn, but the user approves before anything changes,
* ``fixed``   — never touched; the user owns the switch.

Import direction matters: this module imports the question bank, which imports
``store``. ``store`` therefore imports *this* module **lazily** (inside the
functions that need it) to avoid an import cycle — do not hoist that to a
module-level import.
"""

from __future__ import annotations

from typing import Optional

from .questions import _BY_ID

__all__ = [
    "MODES",
    "CONTEXT_DEPENDENT",
    "MIRROR_PRONE",
    "IDENTITY",
    "RISKY_CATEGORIES",
    "match_question_id",
    "is_risky",
    "default_mode_for",
]

MODES = ("auto", "suggest", "fixed")

# Dials where no single value is even correct (context-dependent) — the engine
# must not infer these; the user sets them directly. Default mode: ``fixed``.
CONTEXT_DEPENDENT = frozenset({"comm_length", "fmt_length", "wf_thoroughness"})

# Format/verbosity dials where how you *type* ≠ how you want to *read* (the
# "mirror fallacy"). Learnable, but never silently — default mode: ``suggest``.
MIRROR_PRONE = frozenset({"fmt_lists", "fmt_tldr", "fmt_structure", "comm_emoji"})

# Who-you-are facets. Never silently rewritten — default mode: ``suggest``.
IDENTITY = frozenset({"comm_name", "other_pronouns"})

# Categories where a wrong silent change could actually hurt.
RISKY_CATEGORIES = frozenset({"safety", "autonomy"})


def match_question_id(category: str, text: str) -> Optional[str]:
    """Best-effort map a stored facet back to its calibration question.

    Facets recorded from a question read ``"<Label>: <value>"`` (see
    ``QuestionBank.answer``), so we match the label before the first colon
    against the question bank, scoped to the facet's category (labels are not
    globally unique). Returns ``None`` for free-text/manual notes — which the
    caller treats as risky (fail-closed)."""
    if ":" not in text:
        return None
    label = text.split(":", 1)[0].strip().lower()
    if not label:
        return None
    for q in _BY_ID.values():
        if q.category == category and q.label.lower() == label:
            return q.id
    return None


def is_risky(question_id: Optional[str]) -> bool:
    """True if a facet must never be silently auto-tuned. **Fails closed**: an
    unknown or unmappable facet is treated as risky."""
    if question_id is None:
        return True
    q = _BY_ID.get(question_id)
    if q is None:
        return True
    return q.guardrail or q.category in RISKY_CATEGORIES or question_id in IDENTITY


def default_mode_for(question_id: Optional[str]) -> str:
    """The mode a facet should start in, derived from its character (§4 of
    DECLINATION.md). Precedence: context-dependent → ``fixed``; risky or
    mirror-prone → ``suggest``; everything else → ``auto``."""
    if question_id in CONTEXT_DEPENDENT:
        return "fixed"
    if is_risky(question_id) or question_id in MIRROR_PRONE:
        return "suggest"
    return "auto"
