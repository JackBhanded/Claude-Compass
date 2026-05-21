"""Exhaustive tests for the vendored safe-write engine (COMPASS markers).

Mirrors Lifejacket's suite — if these pass, Compass can trust a tool that edits
the user's memory. Includes a test that a COMPASS block and a (foreign)
LIFEJACKET block coexist untouched, since they share one CLAUDE.md.

Run from the project root:  pytest -q   (or double-click run-tests.bat)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from claude_compass.safewrite import (
    MarkerError,
    SyncStatus,
    make_markers,
    read_managed_block,
    remove_managed_block,
    sync_managed_block,
    write_text_atomic,
)

BID = "profile"
V = 1


def _begin(bid=BID, v=V):
    return f"<!-- COMPASS:BEGIN id={bid} v={v} -->"


def write_raw(path: Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8"))


# -- markers -------------------------------------------------------------- #

def test_make_markers_basic():
    begin, end_head = make_markers("profile", 1)
    assert begin == "<!-- COMPASS:BEGIN id=profile v=1 -->"
    assert end_head == "<!-- COMPASS:END id=profile v=1"


@pytest.mark.parametrize("bad", ["", "has space", "semi;colon", "star*", "a/b", "(grp)"])
def test_bad_block_id_raises(bad):
    with pytest.raises(MarkerError):
        make_markers(bad, 1)


# -- create / append ------------------------------------------------------ #

def test_create_new_file(tmp_path):
    f = tmp_path / "CLAUDE.md"
    r = sync_managed_block(f, BID, V, "i like terse, blunt feedback")
    assert r.status == SyncStatus.CREATED and r.changed
    text = f.read_text(encoding="utf-8")
    assert _begin() in text and "blunt feedback" in text and "sha256=" in text
    assert not f.read_bytes().startswith(b"\xef\xbb\xbf")


def test_append_preserves_user_content(tmp_path):
    f = tmp_path / "CLAUDE.md"
    write_raw(f, "# My notes\n\nSacred.\n")
    sync_managed_block(f, BID, V, "profile bits")
    out = f.read_text(encoding="utf-8")
    assert out.startswith("# My notes") and "Sacred." in out and "profile bits" in out


# -- idempotency / update / tamper ---------------------------------------- #

def test_unchanged_is_idempotent(tmp_path):
    f = tmp_path / "CLAUDE.md"
    sync_managed_block(f, BID, V, "stable")
    m1 = f.stat().st_mtime_ns
    r = sync_managed_block(f, BID, V, "stable")
    assert r.status == SyncStatus.UNCHANGED and f.stat().st_mtime_ns == m1


def test_update_rewrites_and_backs_up(tmp_path):
    f = tmp_path / "CLAUDE.md"
    sync_managed_block(f, BID, V, "v one")
    r = sync_managed_block(f, BID, V, "v two")
    assert r.status == SyncStatus.UPDATED and r.changed
    assert r.backup_path and r.backup_path.exists()
    assert "v two" in f.read_text(encoding="utf-8")
    assert "v one" in r.backup_path.read_text(encoding="utf-8")


def test_handedit_detected_and_refused(tmp_path):
    f = tmp_path / "CLAUDE.md"
    sync_managed_block(f, BID, V, "original")
    write_raw(f, f.read_text(encoding="utf-8").replace("original", "my own words"))
    r = sync_managed_block(f, BID, V, "compass wants this")
    assert r.status == SyncStatus.TAMPERED and not r.changed
    assert "my own words" in f.read_text(encoding="utf-8")


def test_force_overrides_tamper(tmp_path):
    f = tmp_path / "CLAUDE.md"
    sync_managed_block(f, BID, V, "original")
    write_raw(f, f.read_text(encoding="utf-8").replace("original", "hand edit"))
    r = sync_managed_block(f, BID, V, "forced", force=True)
    assert r.status == SyncStatus.UPDATED and "forced" in f.read_text(encoding="utf-8")


def test_duplicate_blocks_refused(tmp_path):
    f = tmp_path / "CLAUDE.md"
    sync_managed_block(f, BID, V, "first")
    text = f.read_text(encoding="utf-8")
    write_raw(f, text + "\n\n" + _begin() + "\nsecond\n<!-- COMPASS:END id=profile v=1 -->\n")
    before = f.read_text(encoding="utf-8")
    r = sync_managed_block(f, BID, V, "third")
    assert r.status == SyncStatus.CONFLICT and f.read_text(encoding="utf-8") == before


# -- line endings / unicode / dry-run ------------------------------------- #

def test_crlf_preserved(tmp_path):
    f = tmp_path / "CLAUDE.md"
    sync_managed_block(f, BID, V, "one")
    write_raw(f, f.read_text(encoding="utf-8").replace("\n", "\r\n"))
    r = sync_managed_block(f, BID, V, "two", force=True)
    assert r.status in (SyncStatus.UPDATED, SyncStatus.UNCHANGED)
    raw = f.read_bytes()
    assert raw.count(b"\r\n") > 0 and raw.count(b"\n") == raw.count(b"\r\n")


def test_unicode(tmp_path):
    f = tmp_path / "CLAUDE.md"
    inner = "prefers: café, naïve, 日本語, 🧭 calm tone"
    sync_managed_block(f, BID, V, inner)
    assert read_managed_block(f, BID) == inner


def test_dry_run_writes_nothing(tmp_path):
    f = tmp_path / "CLAUDE.md"
    r = sync_managed_block(f, BID, V, "preview", dry_run=True)
    assert r.status == SyncStatus.CREATED and not r.changed and not f.exists()


# -- read / remove -------------------------------------------------------- #

def test_read_after_create(tmp_path):
    f = tmp_path / "CLAUDE.md"
    sync_managed_block(f, BID, V, "the inner stuff")
    assert read_managed_block(f, BID) == "the inner stuff"


def test_remove_keeps_user_content(tmp_path):
    f = tmp_path / "CLAUDE.md"
    write_raw(f, "# Mine\n\nkeep me\n")
    sync_managed_block(f, BID, V, "managed")
    r = remove_managed_block(f, BID)
    assert r.status == SyncStatus.UPDATED
    out = f.read_text(encoding="utf-8")
    assert "keep me" in out and "COMPASS" not in out


# -- coexistence with a Lifejacket block (the key cross-tool guarantee) --- #

def test_coexists_with_lifejacket_block(tmp_path):
    f = tmp_path / "CLAUDE.md"
    # A pre-existing Lifejacket projects block (foreign prefix) + user content.
    lj = ("<!-- LIFEJACKET:BEGIN id=projects v=1 -->\n"
          "- **Claude Meter** - shipped\n"
          "<!-- LIFEJACKET:END id=projects v=1 sha256=" + ("0" * 64) + " -->\n")
    write_raw(f, "# Top\n\n" + lj + "\nbottom\n")
    # Compass adds its own block...
    sync_managed_block(f, BID, V, "wants blunt, terse answers")
    out = f.read_text(encoding="utf-8")
    assert "LIFEJACKET:BEGIN" in out          # the foreign block survives
    assert "Claude Meter" in out
    assert "COMPASS:BEGIN" in out             # ours added
    # ...and updating ours never touches theirs.
    sync_managed_block(f, BID, V, "wants warm but concise answers")
    out2 = f.read_text(encoding="utf-8")
    assert "Claude Meter" in out2
    assert read_managed_block(f, BID) == "wants warm but concise answers"
    # Compass must not even see the Lifejacket block as its own.
    assert read_managed_block(f, "projects") is None


# -- write_text_atomic ---------------------------------------------------- #

def test_write_text_atomic(tmp_path):
    f = tmp_path / "nested" / "profile.json"
    bak = write_text_atomic(f, '{"ok": true}')
    assert f.exists() and bak is None
    assert f.read_text(encoding="utf-8") == '{"ok": true}'
    bak2 = write_text_atomic(f, "changed", backup=True)
    assert bak2 and bak2.exists() and bak2.read_text(encoding="utf-8") == '{"ok": true}'
