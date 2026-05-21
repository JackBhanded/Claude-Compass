"""Tests for questions.py — the inquisitive companion (bank + anti-nag cap)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from claude_compass.questions import DEFAULT_QUESTIONS, QuestionBank
from claude_compass.store import FACET_CATEGORIES, Store

_CATEGORY_KEYS = {k for k, _ in FACET_CATEGORIES}


def make(tmp_path):
    s = Store(home=tmp_path / "cc")
    s.init()
    return s, QuestionBank(s)


def test_bank_is_large_and_unique():
    ids = [q.id for q in DEFAULT_QUESTIONS]
    assert len(ids) >= 100              # deeply-researched bank, not a stub
    assert len(ids) == len(set(ids))    # no duplicate ids
    assert all(q.category and q.label and q.text for q in DEFAULT_QUESTIONS)


def test_every_question_category_is_known():
    # so every answer renders under a real heading (not silently bucketed "other")
    for q in DEFAULT_QUESTIONS:
        assert q.category in _CATEGORY_KEYS, f"{q.id} -> unknown category {q.category}"


def test_has_guardrail_questions():
    # the guardrail-setting questions are the safety meat of the bank
    guardrails = [q for q in DEFAULT_QUESTIONS if q.guardrail]
    assert len(guardrails) >= 15


def test_every_category_has_questions():
    used = {q.category for q in DEFAULT_QUESTIONS}
    for key, _ in FACET_CATEGORIES:
        if key == "other":
            continue
        assert key in used, f"category {key} has no questions"


# -- clickable options + number resolution -------------------------------- #

def test_most_questions_have_options():
    with_opts = [q for q in DEFAULT_QUESTIONS if q.options]
    assert len(with_opts) >= 100   # nearly every question offers quick picks


def test_resolve_single_number(tmp_path):
    s, qb = make(tmp_path)
    # comm_tone: ["Warm and friendly", "Balanced", "Terse and to-the-point"]
    assert qb.resolve_answer("comm_tone", "3") == "Terse and to-the-point"


def test_resolve_multi_numbers(tmp_path):
    s, qb = make(tmp_path)
    out = qb.resolve_answer("exp_langs", "1,3")   # exp_langs is multi
    assert len(out.split(",")) == 2


def test_resolve_freetext_passthrough(tmp_path):
    s, qb = make(tmp_path)
    assert qb.resolve_answer("comm_tone", "in my own words") == "in my own words"


def test_resolve_then_answer_records_option(tmp_path):
    s, qb = make(tmp_path)
    final = qb.resolve_answer("comm_tone", "1")
    f = qb.answer("comm_tone", final)
    assert f.text == "Tone: Warm and friendly"


def test_resolve_out_of_range_falls_back_to_text(tmp_path):
    s, qb = make(tmp_path)
    # 99 isn't a valid option index -> treat as free text
    assert qb.resolve_answer("comm_tone", "99") == "99"


# -- quickstart (fill recommended defaults) ------------------------------- #

def test_quickstart_fills_meaningful_defaults(tmp_path):
    s, qb = make(tmp_path)
    n = qb.quickstart()
    assert n == qb.recommended_count() and n >= 80
    facets = s.load()
    # all live + tagged as defaults
    assert all(f.approved for f in facets)
    assert all(f.source == "default" for f in facets)
    # the recommended best-first answer landed
    assert any(f.text == "Tone: Warm and friendly" for f in facets)
    # placeholders ("Nothing specific", "None", "(type...)") were skipped
    assert not any("Nothing specific" in f.text for f in facets)
    assert not any("(type" in f.text for f in facets)


def test_quickstart_is_idempotent(tmp_path):
    s, qb = make(tmp_path)
    first = qb.quickstart()
    assert first > 0
    assert qb.quickstart() == 0   # everything already answered


def test_quickstart_skips_already_answered(tmp_path):
    s, qb = make(tmp_path)
    qb.answer("comm_tone", "my own tone")   # I answered this one myself
    qb.quickstart()
    tones = [f.text for f in s.load() if f.text.startswith("Tone:")]
    # quickstart didn't overwrite my own answer with the default
    assert "Tone: my own tone" in tones
    assert "Tone: Warm and friendly" not in tones


def test_next_question_then_answer_advances(tmp_path):
    s, qb = make(tmp_path)
    first = qb.next_question()
    assert first is not None
    qb.answer(first.id, "terse and to-the-point")
    second = qb.next_question()
    assert second is not None and second.id != first.id


def test_answer_creates_approved_you_facet(tmp_path):
    s, qb = make(tmp_path)
    q = next(x for x in DEFAULT_QUESTIONS if x.id == "fb_bluntness")
    facet = qb.answer(q.id, "just say it straight")
    assert facet is not None
    assert facet.source == "you" and facet.approved is True
    assert facet.category == "feedback"
    # the label prefixes the answer so the profile reads naturally
    assert "Bluntness: just say it straight" in [f.text for f in s.load()]
    # and it renders into the injected profile (it's approved)
    assert "just say it straight" in s.render_profile()


def test_empty_answer_ignored(tmp_path):
    s, qb = make(tmp_path)
    q = qb.next_question()
    assert qb.answer(q.id, "   ") is None
    assert s.load() == []


def test_skip_removes_from_rotation(tmp_path):
    s, qb = make(tmp_path)
    q = qb.next_question()
    qb.skip(q.id)
    assert qb.next_question().id != q.id
    qb.reset_skips()
    assert qb.next_question().id == q.id  # back in order


def test_remaining_shrinks(tmp_path):
    s, qb = make(tmp_path)
    total = len(qb.remaining())
    qb.answer(qb.next_question().id, "an answer")
    assert len(qb.remaining()) == total - 1


# -- the anti-nag frequency cap ------------------------------------------- #

def test_due_true_when_never_asked(tmp_path):
    s, qb = make(tmp_path)
    assert qb.due() is True


def test_due_false_right_after_asking(tmp_path):
    s, qb = make(tmp_path)
    qb.mark_asked()
    assert qb.due(min_interval_hours=48) is False


def test_due_true_after_interval(tmp_path):
    s, qb = make(tmp_path)
    qb.mark_asked()
    # Backdate last_asked beyond the interval.
    st = json.loads(s.questions_path.read_text(encoding="utf-8"))
    st["last_asked"] = (datetime.now(timezone.utc) - timedelta(hours=72)).isoformat(timespec="seconds")
    s.questions_path.write_text(json.dumps(st), encoding="utf-8")
    assert qb.due(min_interval_hours=48) is True


def test_due_false_when_nothing_left(tmp_path):
    s, qb = make(tmp_path)
    for q in list(qb.remaining()):
        qb.skip(q.id)
    assert qb.remaining() == []
    assert qb.due() is False  # never nag when there's nothing to ask
