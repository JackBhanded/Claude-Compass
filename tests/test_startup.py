"""Tests for startup.py — the Run-at-startup registry helper.

Side-effect-free: registry-touching calls run only on non-Windows (no-ops),
so running the suite never edits a real machine's Run key.
"""
from __future__ import annotations

import os

import pytest

from claude_compass import startup


def test_value_name_and_key():
    assert startup.VALUE_NAME == "ClaudeCompass"
    assert startup.RUN_KEY.endswith(r"CurrentVersion\Run")


def test_unfrozen_in_dev():
    assert startup.is_frozen() is False
    assert startup.executable_path() is None


@pytest.mark.skipif(os.name == "nt", reason="off-Windows the calls must be no-ops")
def test_noops_off_windows():
    assert startup.is_enabled() is False
    assert startup.enable() is False
    assert startup.disable() is False
