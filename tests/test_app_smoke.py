"""Smoke tests for app.py — run WITHOUT a display or PySide6 installed.

Qt imports live inside main(), so importing the module is always safe; the real
app behaviour is covered by test_appmodel.py.
"""

from __future__ import annotations

from claude_compass.app import _missing_pyside_message, main


def test_main_callable():
    assert callable(main)


def test_missing_pyside_message_helpful():
    msg = _missing_pyside_message()
    assert "PySide6" in msg and "dashboard" in msg


def test_module_imports_without_qt():
    import claude_compass.app as app
    assert hasattr(app, "main")
