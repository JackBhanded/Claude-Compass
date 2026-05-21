"""questions.py — Compass's inquisitive companion.

A curated bank (~100) of calibration questions, each with **best-first suggested
answers** (researched against Anthropic's steering docs + working-style
psychology) the user can pick with a click — single- or multi-select — always
with the option to type their own.

  * Ask about OBSERVABLE PREFERENCES, never self-typing — sliders, not boxes.
  * `options` are ordered best/safest-first (the recommended default leads).
  * `guardrail=True` answers become imperative rules Claude follows reliably.
  * Custom free-text is ALWAYS allowed (the pills are shortcuts, not a cage).

State (answered/skipped + when we last asked) lives in
``~/.claude-compass/questions.json``; the bank lives here in code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from .safewrite import write_text_atomic
from .store import Store

__all__ = ["Question", "QuestionBank", "DEFAULT_QUESTIONS"]


@dataclass
class Question:
    id: str
    category: str            # maps to a profile facet category
    label: str               # short label that prefixes the recorded facet
    text: str                # the prompt shown to the user
    options: List[str] = field(default_factory=list)  # best-first suggested answers
    multi: bool = False      # may pick more than one
    guardrail: bool = False  # answer becomes a hard rule Claude should follow


def _q(id, category, label, text, options=None, multi=False, guardrail=False):
    return Question(id, category, label, text, options or [], multi, guardrail)


DEFAULT_QUESTIONS: List[Question] = [
    # -- Communication style --------------------------------------------- #
    _q("comm_tone", "communication", "Tone",
       "How do you like Claude to talk to you?",
       ["Warm and friendly", "Balanced", "Terse and to-the-point"]),
    _q("comm_length", "communication", "Answer length",
       "How long should answers usually be?",
       ["Short and scannable", "As long as it needs", "Thorough and detailed"]),
    _q("comm_order", "communication", "Order",
       "How should answers be structured?",
       ["Bottom-line first", "Reasoning, then the conclusion"]),
    _q("comm_warmth", "communication", "Warmth",
       "Overall register?",
       ["Warm and personable", "Neutral", "Dry and businesslike"]),
    _q("comm_name", "communication", "Address",
       "What should Claude call you?",
       ["Use my first name", "Casual (hey / friend)", "Keep it formal"]),
    _q("comm_emoji", "communication", "Emoji",
       "Emojis in responses?",
       ["Never", "Sparingly", "Love them"], guardrail=True),
    _q("comm_humor", "communication", "Humor",
       "A little humor?",
       ["A bit of humor is welcome", "Keep it professional"]),
    _q("comm_jargon", "communication", "Jargon",
       "Language level?",
       ["Use domain jargon freely", "Keep it plain"]),
    _q("comm_locale", "communication", "Language/locale",
       "Spelling / language preference?",
       ["US English", "UK English"]),
    _q("comm_summaries", "communication", "Summaries",
       "After a long task, want a summary of what changed?",
       ["Skip it (I'll read the diff)", "Brief summary", "Detailed summary"]),
    _q("comm_followups", "communication", "Next-step ideas",
       "End with suggestions?",
       ["Suggest next steps", "Just answer what I asked"]),
    _q("comm_proactive", "communication", "Proactivity",
       "Point out things you notice?",
       ["Proactively flag things", "Stick to what's asked"]),

    # -- Feedback & honesty ---------------------------------------------- #
    _q("fb_bluntness", "feedback", "Bluntness",
       "When something's wrong with your work, how direct?",
       ["Just say it straight", "Honest but tactful", "Soften it a bit"]),
    _q("fb_praise", "feedback", "Praise",
       "Encouragement, or just the facts?",
       ["Just the facts", "A little encouragement is nice"]),
    _q("fb_pushback", "feedback", "Pushback",
       "Disagreements?",
       ["Challenge me when you disagree", "Mostly defer to me"]),
    _q("fb_sycophancy", "feedback", "Honesty over agreement",
       "Honest pushback even when unwelcome?",
       ["Always be honest with me", "Lean supportive"], guardrail=True),
    _q("fb_idk", "feedback", "Saying 'I don't know'",
       "Better to admit uncertainty than guess?",
       ["Yes — say 'I'm not sure'", "Give your best guess, flagged"], guardrail=True),
    _q("fb_confidence", "feedback", "Confidence flags",
       "Flag low-confidence answers?",
       ["Flag when unsure", "Just answer"]),
    _q("fb_cite", "feedback", "Citations",
       "Sources for factual claims?",
       ["Cite sources", "Move fast, I'll verify"]),
    _q("fb_challenge", "feedback", "Challenge the premise",
       "If a request seems off?",
       ["Question the premise", "Just do what's asked"]),
    _q("fb_devil", "feedback", "Devil's advocate",
       "Want a devil's-advocate take on big calls?",
       ["Yes, on big decisions", "No, keep it simple"]),

    # -- Autonomy & guardrails ------------------------------------------- #
    _q("auto_askact", "autonomy", "Ask vs act",
       "Default working mode?",
       ["Ask before acting", "Act, then report back"], guardrail=True),
    _q("auto_destructive", "autonomy", "Destructive actions",
       "Before delete / overwrite / force-push?",
       ["Always confirm first", "Go ahead if you're confident"], guardrail=True),
    _q("auto_scope", "autonomy", "Scope of changes",
       "How wide can changes go?",
       ["Stay tightly scoped", "Refactor broadly when it helps"], guardrail=True),
    _q("auto_neverlist", "autonomy", "Never without asking",
       "Anything Claude should NEVER do without explicit say-so?",
       ["Nothing specific"], guardrail=True),
    _q("auto_commit", "autonomy", "Git",
       "Version control on its own?",
       ["Don't commit — leave it to me", "OK to commit", "OK to commit and push"], guardrail=True),
    _q("auto_outside", "autonomy", "Stay in lane",
       "Edit files beyond the one you named?",
       ["Stay in the named files", "OK to touch closely-related files"], guardrail=True),
    _q("auto_install", "autonomy", "Installs & long jobs",
       "Install packages / start long jobs without asking?",
       ["Ask first", "Go ahead"], guardrail=True),
    _q("auto_clarify", "autonomy", "Ambiguity",
       "When your request is ambiguous?",
       ["Ask a clarifying question first", "Assume and state it"], guardrail=True),
    _q("auto_bigchange", "autonomy", "Big/risky changes",
       "For a big or risky change?",
       ["Plan for me to approve first", "Just proceed"], guardrail=True),
    _q("auto_uncertain", "autonomy", "When unsure",
       "Unsure how you'd want it done?",
       ["Ask me", "Pick a sensible default and note it"]),

    # -- How they like to work ------------------------------------------- #
    _q("wf_style", "workflow", "Working style",
       "How do you like to work?",
       ["Build, then refine", "Plan it all up front", "A bit of both"]),
    _q("wf_plan", "workflow", "Plans vs action",
       "Starting a task?",
       ["Plan to approve first", "Just go"]),
    _q("wf_options", "workflow", "Options vs decide",
       "Several good approaches?",
       ["Show me the options", "Pick the best and proceed"]),
    _q("wf_checkpoints", "workflow", "Check-ins",
       "Cadence?",
       ["Check in along the way", "One finished deliverable"]),
    _q("wf_rhythm", "workflow", "Rhythm",
       "Your working rhythm?",
       ["Quick iterative chunks", "Long deep-focus stretches"]),
    _q("wf_thoroughness", "workflow", "Thorough vs fast",
       "Default trade-off?",
       ["Thorough and complete", "Good enough, fast"]),
    _q("wf_stress", "workflow", "Under pressure",
       "When you're time-pressured?",
       ["Switch to 'just fix it' mode", "Always explain"]),
    _q("wf_done", "workflow", "Definition of done",
       "What's 'done'?",
       ["Polished and complete", "Minimal working version"]),
    _q("wf_testing", "workflow", "Testing",
       "How much do tests matter?",
       ["A lot — test everything", "For important code", "Rarely"]),
    _q("wf_research", "workflow", "Explore first",
       "Before coding?",
       ["Explore the codebase first", "Dive straight in"]),

    # -- Format & output ------------------------------------------------- #
    _q("fmt_lists", "formatting", "Lists vs prose",
       "Default format?",
       ["Bullet lists", "Flowing prose", "Mix as needed"]),
    _q("fmt_structure", "formatting", "Structure",
       "Headers and sections?",
       ["Headers and sections", "Plain continuous text"]),
    _q("fmt_tables", "formatting", "Tables",
       "Comparisons?",
       ["Use tables", "Keep it in sentences"]),
    _q("fmt_tldr", "formatting", "TL;DR",
       "A one-line TL;DR atop long answers?",
       ["Yes please", "No need"]),
    _q("fmt_length", "formatting", "Length cap",
       "Default length?",
       ["Keep it short", "Length as needed"]),
    _q("fmt_files", "formatting", "Files vs chat",
       "Longer outputs?",
       ["Files I can open", "Everything in chat"]),
    _q("fmt_codeblocks", "formatting", "Code delivery",
       "How to deliver code changes?",
       ["Diffs", "Full files", "Just the snippet"]),

    # -- Background & expertise ------------------------------------------ #
    _q("exp_level", "expertise", "Experience",
       "Your overall level?",
       ["Senior / expert", "Mid-level", "Junior / learning", "Not a developer"]),
    _q("exp_years", "expertise", "Years",
       "How long doing this kind of work?",
       ["10+ years", "5-10 years", "2-5 years", "Under 2 years"]),
    _q("exp_langs", "expertise", "Strong areas",
       "Languages/areas you're most comfortable in?",
       ["Python", "JavaScript / TypeScript", "Go", "Rust", "Java", "C#",
        "PowerShell", "SQL"], multi=True),
    _q("exp_weak", "expertise", "Newer areas",
       "Anything you're newer to (extra hand-holding)?",
       ["Nothing in particular"]),
    _q("exp_explain", "expertise", "Teach vs do",
       "While working?",
       ["Explain as you go", "Assume I know, just do it"]),
    _q("exp_role", "expertise", "Default role",
       "Default role for Claude?",
       ["Pair programmer", "Code reviewer", "Tutor", "Rubber duck"]),
    _q("exp_goals", "expertise", "Goals",
       "Anything you're trying to get better at?",
       ["Nothing specific"]),
    _q("exp_terms", "expertise", "Domain terms",
       "Acronyms / terms specific to your work?",
       ["None"]),

    # -- How they learn best --------------------------------------------- #
    _q("learn_examples", "learning", "Examples vs theory",
       "You learn best from?",
       ["Worked examples", "The underlying principle first"]),
    _q("learn_bigpicture", "learning", "Big-picture vs detail",
       "Order of explanation?",
       ["Big-picture first", "Build up from specifics"]),
    _q("learn_depth", "learning", "The 'why'",
       "How much depth?",
       ["I enjoy the 'why'", "Mostly the 'what to do'"]),
    _q("learn_ambiguity", "learning", "Definite vs 'it depends'",
       "When there's no single right answer?",
       ["Give me a definite recommendation", "I'm fine with 'it depends'"]),
    _q("learn_visual", "learning", "Diagrams & analogies",
       "What helps you grasp things?",
       ["Diagrams & analogies", "Precise plain text"]),
    _q("learn_steps", "learning", "Step-by-step",
       "Instructions as?",
       ["Numbered step-by-step", "A narrative"]),
    _q("learn_pace", "learning", "Pace",
       "How much at once?",
       ["One thing at a time", "A lot at once is fine"]),
    _q("learn_recap", "learning", "Recap",
       "A short recap at the end of a session?",
       ["Yes, recap it", "No need"]),

    # -- Code & conventions ---------------------------------------------- #
    _q("code_langs", "codestyle", "Languages/versions",
       "Languages & framework versions to target?",
       ["Python", "TypeScript", "Go", "Rust", "Java", "C#"], multi=True, guardrail=True),
    _q("code_formatter", "codestyle", "Formatter/linter",
       "Defer to your formatter/linter?",
       ["Yes — defer to it (Prettier/Black/ESLint)", "No formatter"]),
    _q("code_naming", "codestyle", "Conventions",
       "Naming / file-org conventions?",
       ["Follow the existing code"]),
    _q("code_comments", "codestyle", "Comment density",
       "How commented should code be?",
       ["Light — clean code", "Moderate", "Heavily commented"]),
    _q("code_arch", "codestyle", "Architecture",
       "Architectural leaning?",
       ["Match the codebase", "Functional", "Object-oriented"]),
    _q("code_deps", "codestyle", "Dependencies",
       "New dependencies?",
       ["Avoid / justify them", "Add freely"], guardrail=True),
    _q("code_banned", "codestyle", "Banned",
       "Libraries / patterns Claude should never use?",
       ["Nothing"], guardrail=True),
    _q("code_errors", "codestyle", "Errors & logging",
       "Error-handling / logging conventions?",
       ["Follow the codebase"]),
    _q("code_tests", "codestyle", "Tests required",
       "Tests for new code?",
       ["Required", "For important code", "Not required"], guardrail=True),
    _q("code_runcmds", "codestyle", "Build/test/run",
       "Your build / test / run commands?",
       ["(type them below)"]),
    _q("code_commit", "codestyle", "Commit style",
       "Commit-message style?",
       ["Conventional Commits", "Short imperative", "No preference"]),
    _q("code_styleguide", "codestyle", "Style reference",
       "A style guide / file to mirror?",
       ["Match existing code"]),
    _q("code_perf", "codestyle", "Readability vs performance",
       "When they conflict?",
       ["Readability", "Performance", "Depends"]),

    # -- Safety & boundaries --------------------------------------------- #
    _q("safe_secrets", "safety", "Secrets",
       "Rule for secrets / keys?",
       ["Never hardcode, commit, or echo them", "I'll handle secrets myself"], guardrail=True),
    _q("safe_pii", "safety", "Private data",
       "Data Claude must never log / repeat / store?",
       ["None"], guardrail=True),
    _q("safe_prod", "safety", "Production",
       "Do you work against production?",
       ["Yes — be extra careful with prod", "I don't touch prod"], guardrail=True),
    _q("safe_topics", "safety", "Off-limits",
       "Topics or kinds of help that are off-limits?",
       ["None"], guardrail=True),
    _q("safe_review", "safety", "Double-check",
       "Anything to always double-check before finishing?",
       ["Nothing specific"]),
    _q("safe_compliance", "safety", "Compliance",
       "Compliance-sensitive domain?",
       ["No", "Health", "Finance", "Legal", "Other"], multi=True, guardrail=True),
    _q("safe_external", "safety", "External actions",
       "Network / external-service actions?",
       ["Confirm those first", "No need"], guardrail=True),

    # -- Domains & tools ------------------------------------------------- #
    _q("dom_domain", "domains", "Domain",
       "What do you mostly use Claude for?",
       ["Web dev", "Data / ML", "DevOps / infra", "Scripting / automation",
        "Mobile", "Writing / docs"], multi=True),
    _q("dom_tools", "domains", "Tools",
       "Tools / editors you use day to day?",
       ["VS Code", "Claude Code", "Cursor", "JetBrains", "Vim / Neovim",
        "Terminal"], multi=True),
    _q("dom_stack", "domains", "Stack",
       "Typical stack / services Claude should assume?",
       ["(type it below)"]),
    _q("dom_os", "domains", "Platform",
       "What environment do you work in?",
       ["Windows", "macOS", "Linux", "WSL"], multi=True),
    _q("dom_team", "domains", "Solo vs team",
       "Solo or team?",
       ["Solo", "Small team", "Large team / org"]),

    # -- Accessibility & wellbeing --------------------------------------- #
    _q("acc_brevity", "accessibility", "Scannability",
       "Do dense walls of text lose you?",
       ["Yes — short chunks, key points bolded", "Dense is fine"], guardrail=True),
    _q("acc_dyslexia", "accessibility", "Readability",
       "Formatting that helps you read?",
       ["Lists over prose, plain words", "No special needs"], guardrail=True),
    _q("acc_predictable", "accessibility", "Predictable structure",
       "A consistent response structure?",
       ["Yes, keep it predictable", "No preference"]),
    _q("acc_tone", "accessibility", "Condescension",
       "Anything in AI tone that grates on you?",
       ["Nothing comes to mind"], guardrail=True),
    _q("acc_language", "accessibility", "Plain phrasing",
       "Would clear, simple phrasing help?",
       ["Yes, keep it simple", "Full complexity is fine"]),

    # -- Pet peeves ------------------------------------------------------ #
    _q("peeve_avoid", "peeves", "Avoid",
       "Anything that annoys you in AI responses?",
       ["Nothing specific"], guardrail=True),
    _q("peeve_overdo", "peeves", "Over-doing",
       "Anything Claude over-does that you'd dial down?",
       ["Nothing specific"], guardrail=True),
    _q("peeve_filler", "peeves", "Filler phrases",
       "Filler phrases you're tired of?",
       ["None"], guardrail=True),
    _q("peeve_apology", "peeves", "Over-apologizing",
       "Claude over-apologizing / hedging?",
       ["Skip the over-apologizing", "It's fine"]),
    _q("peeve_format", "peeves", "Format peeves",
       "Formatting that bugs you?",
       ["Too many bullets", "Too many headers", "Walls of bold", "Emojis"],
       multi=True, guardrail=True),

    # -- Other ----------------------------------------------------------- #
    _q("other_proud", "other", "Respect",
       "Anything about how you work you're proud of and want respected?",
       ["Nothing specific"]),
    _q("other_pronouns", "other", "Address & respect",
       "Pronouns, or how you'd like to be addressed?",
       ["he/him", "she/her", "they/them"]),
    _q("other_context", "other", "Anything else",
       "Anything else Claude should know to help you better?",
       ["Nothing else"]),

    # -- Deeper cuts (all from the research, all worth asking) ----------- #
    _q("comm_ack", "communication", "When I'm stuck",
       "When you're frustrated or stuck?",
       ["Just solve it", "Acknowledge it briefly, then solve"]),
    _q("comm_brainstorm", "communication", "Brainstorming",
       "Exploring ideas?",
       ["Brainstorm broadly first", "Converge on one fast"]),
    _q("fb_review_order", "feedback", "Review order",
       "In a review, lead with?",
       ["The problems", "What's good first"]),
    _q("fb_own_mistakes", "feedback", "When Claude errs",
       "When Claude gets something wrong?",
       ["Own it briefly and fix it", "Explain what went wrong"]),
    _q("auto_assumptions", "autonomy", "State assumptions",
       "Should Claude state its assumptions as it goes?",
       ["Yes, state them", "Only when they matter"], guardrail=True),
    _q("auto_cost", "autonomy", "Cost/time",
       "Before expensive or slow operations?",
       ["Check in on cost/time first", "Just proceed"], guardrail=True),
    _q("auto_interrupt", "autonomy", "Interruptions",
       "Mid-task questions?",
       ["Batch them for the end", "Ask as they come up"]),
    _q("wf_agenda", "workflow", "Session agenda",
       "A quick plan/agenda at the start of a work session?",
       ["Yes, a quick agenda", "No, just dive in"]),
    _q("wf_verify", "workflow", "Self-verify",
       "After finishing, verify the result before handing back?",
       ["Always verify first", "Trust and hand back"], guardrail=True),
    _q("fmt_math", "formatting", "Math",
       "Calculations / math?",
       ["Show the steps", "Just the result"]),
    _q("fmt_code_first", "formatting", "Code or words first",
       "In answers with code?",
       ["Code first", "Explanation first"]),
    _q("exp_mentor", "expertise", "Teach me things",
       "Occasionally teach you something new in your domain?",
       ["Yes, teach me", "Only when I ask"]),
    _q("learn_analogy_domain", "learning", "Analogy source",
       "A field you know well that Claude can draw analogies from?",
       ["No preference"]),
    _q("learn_antipatterns", "learning", "Pitfalls",
       "Useful to see common mistakes / anti-patterns?",
       ["Yes, show the pitfalls", "Just the right way"]),
    _q("code_typing", "codestyle", "Typing",
       "Type hints / strict typing?",
       ["Prefer strict typing", "Loose is fine"]),
    _q("code_funcsize", "codestyle", "Function size",
       "Function size?",
       ["Small, focused functions", "Fewer larger ones", "No preference"]),
    _q("code_review_focus", "codestyle", "Review focus",
       "When reviewing code, focus on?",
       ["Correctness", "Security", "Performance", "Readability"], multi=True),
    _q("code_docs", "codestyle", "Docs",
       "Docstrings / API docs for new code?",
       ["Document it", "Public APIs only", "Skip unless asked"]),
    _q("safe_money", "safety", "Money",
       "Anything touching money / payments / billing?",
       ["Extra confirmation", "Normal caution"], guardrail=True),
    _q("safe_backup", "safety", "Backups",
       "Remind you to back up before risky operations?",
       ["Yes, remind me", "No need"]),
    _q("acc_focus", "accessibility", "Focus",
       "Keep responses focused and on-task?",
       ["Yes, stay focused", "Tangents welcome"]),
    _q("well_breaks", "accessibility", "Rest",
       "On long pushes, nudge you to rest, or power through?",
       ["A gentle nudge is nice", "Power through"]),
    _q("well_celebrate", "accessibility", "Wins",
       "Celebrate wins with you?",
       ["Yes, a little celebration", "Stay neutral"]),
    _q("other_motivation", "other", "What energizes you",
       "What gets you energized?",
       ["Shipping", "Learning", "Polishing the craft", "Hard problems"], multi=True),
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

    def get(self, question_id: str) -> Optional[Question]:
        return _BY_ID.get(question_id)

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
        """Polite to surface a question now? True only if one is left AND we
        haven't asked within ``min_interval_hours`` — the anti-nag guard."""
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
        the question answered. ``text`` may be a single choice, a joined set of
        choices, or the user's own words. Returns the Facet, or None if empty."""
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

    def resolve_answer(self, question_id: str, raw: str) -> Optional[str]:
        """Turn a CLI answer arg into final text. Numbers (e.g. '1' or '1,3')
        select option(s) best-first; anything else is taken as free text."""
        q = _BY_ID.get(question_id)
        if not q:
            return None
        raw = (raw or "").strip()
        if not raw:
            return None
        tokens = [t.strip() for t in raw.split(",")]
        if q.options and all(t.isdigit() for t in tokens if t):
            picks = []
            for t in tokens:
                if not t:
                    continue
                i = int(t)
                if 1 <= i <= len(q.options):
                    picks.append(q.options[i - 1])
            if picks:
                return ", ".join(picks)
        return raw

    def skip(self, question_id: str) -> bool:
        if question_id not in _BY_ID:
            return False
        st = self._load()
        if question_id not in st["skipped"] and question_id not in st["answered"]:
            st["skipped"].append(question_id)
            self._save(st)
        return True

    def reset_skips(self) -> None:
        st = self._load()
        st["skipped"] = []
        self._save(st)
