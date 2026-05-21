"""Tests for dashboard.py + the `dashboard` CLI command."""

from __future__ import annotations

import pytest

from claude_compass.cli import main
from claude_compass.dashboard import render_dashboard_html, write_dashboard
from claude_compass.store import Store
from claude_compass.sync import sync_all


@pytest.fixture
def env(tmp_path, monkeypatch):
    cc = tmp_path / "cc"
    ch = tmp_path / "dot-claude"
    ch.mkdir()
    monkeypatch.setenv("COMPASS_HOME", str(cc))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(ch))
    return {"cc": cc, "ch": ch}


def populated(tmp_path) -> Store:
    s = Store(home=tmp_path / "cc")
    s.init()
    s.add_facet("communication", "warm but concise", source="you")
    s.add_facet("expertise", "inferred: senior backend", source="history")
    return s


def test_render_has_logo_and_facets(tmp_path):
    s = populated(tmp_path)
    html = render_dashboard_html(s)
    assert "<!DOCTYPE html>" in html
    assert "M4.709 15.955" in html and "#D97757" in html  # real Claude logo
    assert "<title>Claude</title>" in html
    assert "warm but concise" in html


def test_render_marks_pending_and_hides_from_injected(tmp_path):
    s = populated(tmp_path)
    html = render_dashboard_html(s)
    # the inferred facet shows in the profile listing, tagged pending...
    assert "pending review" in html
    assert "inferred: senior backend" in html
    # ...but the "what every session is reading" box only has approved content.
    # (verify via the store render, which the box mirrors)
    assert "inferred: senior backend" not in s.render_profile()


def test_render_escapes_html(tmp_path):
    s = Store(home=tmp_path / "cc")
    s.init()
    s.add_facet("peeves", "<script>alert(1)</script>")
    html = render_dashboard_html(s)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_render_shows_paused_banner(tmp_path):
    s = populated(tmp_path)
    s.set_paused(True)
    html = render_dashboard_html(s)
    assert "PAUSED" in html


def test_write_dashboard_in_store(tmp_path):
    s = populated(tmp_path)
    out = write_dashboard(s)
    assert out.exists() and out.parent == s.home and out.name == "dashboard.html"


def test_cli_dashboard_no_open(env, capsys, monkeypatch):
    import webbrowser
    monkeypatch.setattr(webbrowser, "open", lambda *a, **k: pytest.fail("should not open"))
    main(["init"])
    main(["answer", "comm_tone", "warm"])
    capsys.readouterr()
    assert main(["dashboard", "--no-open"]) == 0
    assert (env["cc"] / "dashboard.html").exists()


def test_cli_dashboard_reflects_sync(env, capsys, monkeypatch):
    import webbrowser
    monkeypatch.setattr(webbrowser, "open", lambda *a, **k: None)
    main(["init"])
    main(["answer", "comm_tone", "warm but concise"])
    main(["sync"])
    capsys.readouterr()
    main(["dashboard", "--no-open"])
    html = (env["cc"] / "dashboard.html").read_text(encoding="utf-8")
    assert "In sync" in html
