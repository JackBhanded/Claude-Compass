"""questions.py — Compass's inquisitive companion.

A small curated bank of calibration questions. Compass surfaces one now and then
to deepen your profile over time. The prior-art research was emphatic about not
nagging, so:

  * questions are surfaced at most once per ``min_interval`` (default ~2 days),
  * one at a time,
  * always skippable,
  * and an answer becomes a normal *you*-sourced facet (auto-approved, since you
    said it yourself).

State (which questions are answered/skipped + when we last asked) lives in
``~/.claude-compass/questions.json``; the questions themselves are defined here
in code so the bank can grow between versions without migrating user data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from .safewrite import write_text_atomic
from .store import Store

__all__ = ["Question", "QuestionBank", "DEFAULT_QUESTIONS"]


@dataclass
class Question:
    id: str
    category: str   # maps to a profile facet category
    label: str      # short label that prefixes the recorded facet
    text: str       # the prompt shown to the user


# The bank. `label` prefixes the answer when it becomes a facet, so the profile
# reads naturally (e.g. "Tone: terse and to-the-point").
DEFAULT_QUESTIONS: List[Question] = [
    Question("comm_tone", "communication", "Tone",
             "How do you like Claude to talk to you — warm and chatty, or terse and to-the-point?"),
    Question("comm_length", "communication", "Answer length",
             "Do you prefer short answers you can scan, or thorough explanations?"),
    Question("comm_name", "communication", "Address",
             "What should Claude call you, and any vibe you like (buddy, formal, playful)?"),
    Question("comm_emoji", "communication", "Emoji",
             "Emojis in responses — love them, fine in moderation, or never?"),
    Question("fb_bluntness", "feedback", "Bluntness",
             "When something's wrong with your idea or code, how direct should Claude be?"),
    Question("fb_praise", "feedback", "Praise",
             "Do you want encouragement along the way, or just the facts?"),
    Question("fb_pushback", "feedback", "Pushback",
             "Should Claude challenge your decisions when it disagrees, or defer to you?"),
    Question("exp_level", "expertise", "Experience",
             "How would you describe your overall experience level as a developer?"),
    Question("exp_langs", "expertise", "Strong areas",
             "Which languages or areas are you most comfortable in?"),
    Question("exp_weak", "expertise", "Newer areas",
             "Anything you're newer to, where you'd like a little extra hand-holding?"),
    Question("exp_goals", "expertise", "Goals",
             "Anything you're trying to get better at, that Claude could gently support?"),
    Question("wf_style", "workflow", "Working style",
             "How do you like to work — plan it all up front, or build-then-refine?"),
    Question("wf_plan", "workflow", "Plans vs action",
             "Starting a task, do you want a plan to approve first, or should Claude just go?"),
    Question("wf_autonomy", "workflow", "Autonomy",
             "How much should Claude do on its own vs check in with you often?"),
    Question("wf_testing", "workflow", "Testing",
             "How much do you care about tests / verification on a typical task?"),
    Question("fmt_lists", "formatting", "Lists vs prose",
             "Prefer answers as bullet lists, or flowing prose?"),
    Question("fmt_code", "formatting", "Code comments",
             "Heavily-commented code, or clean code that speaks for itself?"),
    Question("fmt_files", "formatting", "Files vs chat",
             "For longer outputs, do you like files you can open, or everything in chat?"),
    Question("dom_domain", "domains", "Domain",
             "What kind of work or projects do you mostly use Claude for?"),
    Question("dom_tools", "domains", "Tools",
             "Which tools, editors, or stack do you use day to day?"),
    Question("dom_os", "domains", "Platform",
             "What OS / environment do you mostly work in?"),
    Question("peeve_avoid", "peeves", "Avoid",
             "Anything that really annoys you in how AI assistants respond?"),
    Question("peeve_overdo", "peeves", "Over-doing",
             "Anything Claude tends to over-do that you'd like dialled down?"),
    Question("other_misc", "other", "Anything else",
             "Anything else about how you like to work that would help Claude help you?"),
]

_BY_ID = {q.id: q for q in DEFAULT_QUESTIONS}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class QuestionBank:
    """Stateful view over the question bank for one store."""

    def __init__(self, store: Store):
        self.store = store

    # -- state -------------------------------------------------------------- #
    def _load(self) -> dict:
        p = self.store.questions_path
        if not p.exists():
            return {"answered": [], "skipped": [], "last_asked": None, "asked_count": 0}
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"answered": [], "skipped": [], "last_asked": None, "asked_count": 0}
        data.setdefault("answered", [])
        data.setdefault("skipped", [])
        data.setdefault("last_asked", None)
        data.setdefault("asked_count", 0)
        return data

    def _save(self, state: dict) -> None:
        write_text_atomic(self.store.questions_path,
                          json.dumps(state, indent=2, ensure_ascii=False) + "\n",
                          backup=self.store.questions_path.exists())

    # -- queries ------------------------------------------------------------ #
    def all_questions(self) -> List[Question]:
        return list(DEFAULT_QUESTIONS)

    def remaining(self) -> List[Question]:
        st = self._load()
        done = set(st["answered"]) | set(st["skipped"])
        return [q for q in DEFAULT_QUESTIONS if q.id not in done]

    def next_question(self) -> Optional[Question]:
        rem = self.remaining()
        return rem[0] if rem else None

    def answered_count(self) -> int:
        return len(self._load()["answered"])

    def due(self, min_interval_hours: float = 48.0) -> bool:
        """Is it polite to surface a question now? True only if there's an
        unanswered question AND we haven't asked within ``min_interval_hours``.
        This is the anti-nag guard the hook uses."""
        if not self.remaining():
            return False
        st = self._load()
        last = st.get("last_asked")
        if not last:
            return True
        try:
            elapsed = (_now() - datetime.fromisoformat(last)).total_seconds() / 3600.0
        except (ValueError, TypeError):
            return True
        return elapsed >= min_interval_hours

    # -- actions ------------------------------------------------------------ #
    def mark_asked(self) -> None:
        st = self._load()
        st["last_asked"] = _now().isoformat(timespec="seconds")
        st["asked_count"] = int(st.get("asked_count", 0)) + 1
        self._save(st)

    def answer(self, question_id: str, text: str):
        """Record an answer: add it as a *you*-sourced (approved) facet and mark
        the question answered. Returns the new Facet, or None if the answer was
        empty / the id unknown."""
        q = _BY_ID.get(question_id)
        if not q:
            return None
        text = (text or "").strip()
        if not text:
            return None
        facet = self.store.add_facet(q.category, f"{q.label}: {text}", source="you")
        st = self._load()
        if question_id not in st["answered"]:
            st["answered"].append(question_id)
        if question_id in st["skipped"]:
            st["skipped"].remove(question_id)
        self._save(st)
        self.store.log_event(f"answered '{question_id}' -> {q.category} facet")
        return facet

    def skip(self, question_id: str) -> bool:
        if question_id not in _BY_ID:
            return False
        st = self._load()
        if question_id not in st["skipped"] and question_id not in st["answered"]:
            st["skipped"].append(question_id)
            self._save(st)
        return True

    def reset_skips(self) -> None:
        """Let previously-skipped questions come back around."""
        st = self._load()
        st["skipped"] = []
        self._save(st)
