"""detector.py — Stage 1 of declination's hybrid detector (heuristics).

Cheap, local, and tuned for **recall**: scan the user's typed turns for phrases
that bear on a known calibration question, and emit candidate *hits*. A hit
names the **question** it bears on (not a specific facet) plus the signal —
``SUPPORT`` / ``CONTRADICT`` / ``SUGGEST_ALT`` — and, when one is implied, the
alternative value. The caller resolves a hit to the actual facet(s) in the
profile and decides what (if anything) to do with it.

Phase 1 keeps the net deliberately **narrow and high-precision**: a handful of
unambiguous phrases. Stage 2 (the user's own Claude adjudicating) and a broader
net come later. These rules are heuristics, so they're tuned to over- rather
than under-flag, but kept small so false alarms stay rare while we watch it
learn.

These weights/phrases are TUNABLE — expect to calibrate them against real usage.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

__all__ = ["Hit", "RULES", "scan_turns"]


@dataclass
class Hit:
    question_id: str          # the calibration question this bears on
    signal: str               # SUPPORT | CONTRADICT | SUGGEST_ALT
    strength: str = "weak"    # weak | strong
    suggests: Optional[str] = None   # the alternative value, when implied
    matched: str = ""         # the phrase that fired (for dry-run transparency)


# (compiled pattern, question_id, signal, strength, suggested-value)
# Patterns are matched case-insensitively against each user turn.
_RAW_RULES = [
    # Bluntness / feedback (auto-mode facet — silently learnable later)
    (r"\b(be blunt|stop sugar\s*coating|too soft|don'?t sugar\s*coat)\b",
     "fb_bluntness", "SUGGEST_ALT", "strong", "Just say it straight"),
    # Emoji (suggest-mode — proposes, never silent)
    (r"\b(love the emoji|more emoji|emojis? are great)\b",
     "comm_emoji", "SUGGEST_ALT", "weak", "Love them"),
    (r"\b(drop the emoji|no emoji|stop the emoji|fewer emoji|lose the emoji)\b",
     "comm_emoji", "SUGGEST_ALT", "strong", "Never"),
    # Lists vs prose (suggest-mode, mirror-prone)
    (r"\b(too many bullets|stop the bullets|write it (out|in prose)|in prose)\b",
     "fmt_lists", "SUGGEST_ALT", "weak", "Flowing prose"),
    # Proactivity / ask-vs-act (suggest-mode, autonomy)
    (r"\b(just fix it|just do it|stop asking|don'?t ask)\b",
     "auto_askact", "CONTRADICT", "weak", None),
    # Bottom-line-first (auto-mode)
    (r"\b(get to the point|bottom line first|too much preamble)\b",
     "comm_order", "SUGGEST_ALT", "weak", "Bottom-line first"),
]

RULES = [(re.compile(pat, re.IGNORECASE), qid, sig, strg, sug)
         for (pat, qid, sig, strg, sug) in _RAW_RULES]


def scan_turns(turns: List[str]) -> List[Hit]:
    """Run the heuristic rules over a batch of user turns, newest interest last.
    Returns one :class:`Hit` per (turn, rule) match — duplicates across turns are
    intentional, since repetition is exactly the signal the ledger queries count."""
    hits: List[Hit] = []
    for turn in turns:
        for pattern, qid, signal, strength, suggests in RULES:
            m = pattern.search(turn)
            if m:
                hits.append(Hit(question_id=qid, signal=signal, strength=strength,
                                suggests=suggests, matched=m.group(0)))
    return hits
