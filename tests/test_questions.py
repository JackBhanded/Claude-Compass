"""Tests for questions.py — the inquisitive companion (bank + anti-nag cap)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from claude_compass.questions import DEFAULT_QUESTIONS, QuestionBank
from claude_compass.store import Store


def make(tmp_path):
    s = Store(home=tmp_path / "cc")
    s.init()
    return s, QuestionBank(s)


def test_bank_nonempty_and_unique_ids():
    ids = [q.id for q in DEFAULT_QUESTIONS]
    assert len(ids) >= 15
    assert len(ids) == len(set(ids))
    # every question maps to a real facet category-ish string (non-empty)
    assert all(q.category and q.label and q.text for q in DEFAULT_QUESTIONS)


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
