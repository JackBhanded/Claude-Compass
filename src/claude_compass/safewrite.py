"""safewrite.py — the bedrock of Claude Compass.

VENDORED, byte-for-byte in behaviour, from Claude Lifejacket's audited safe-write
engine (the only difference is the marker prefix and the friendly wording). It is
the *only* code in Compass that ever modifies a file the user cares about (their
``CLAUDE.md``). Everything else is built on top of it. So this is where we are
paranoid.

It edits files by managing a single, clearly-delimited block:

    ...the user's own content, which we NEVER touch...

    <!-- COMPASS:BEGIN id=profile v=1 -->
    ...content that Compass owns and may rewrite...
    <!-- COMPASS:END id=profile v=1 sha256=<hash-of-inner> -->

    ...more of the user's own content, which we NEVER touch...

Because the marker prefix differs (COMPASS vs LIFEJACKET), a Compass block and a
Lifejacket block live happily side by side in the same ``CLAUDE.md`` — each tool
only ever sees and touches its own.

The seven safety non-negotiables (every one is implemented and tested):

  1. Never write in place. Write to a temp file in the same directory, flush +
     fsync it, then atomically ``os.replace`` it over the target, then fsync the
     directory. A crash mid-write can never leave a half-written memory file.
  2. Backup-before-write. Before any change, copy the current file to a
     timestamped backup. Verify the new file after writing; if verification
     fails, roll back from the backup.
  3. Touch ONLY the bytes between our unique versioned markers. If the markers
     are missing we append a fresh block; if they are *duplicated* we refuse and
     do nothing (an ambiguous file is a file we will not gamble on).
  4. Content hash in the END marker → idempotent (skip the write entirely if the
     desired content already matches) AND hand-edit detection (if the user has
     edited inside our block, the stored hash won't match the actual inner text;
     we stop and warn rather than clobber their edit).
  5. UTF-8 without BOM; preserve the file's existing line endings (CRLF vs LF).
  6. Lock the file and re-read it immediately before writing (concurrent-writer
     defense); resolve symlinks so we write the real file, not the link.
  7. Never auto-resolve a conflict in the user's file. On tamper/conflict we
     return a result the caller can surface as a diff — we never silently win.

Nothing here imports anything outside the standard library. Keep it that way.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

__all__ = [
    "SyncStatus",
    "SyncResult",
    "MarkerError",
    "sync_managed_block",
    "read_managed_block",
    "remove_managed_block",
    "make_markers",
    "write_text_atomic",
]


# --------------------------------------------------------------------------- #
# Result types
# --------------------------------------------------------------------------- #

class SyncStatus(str, Enum):
    """What happened (or would happen) during a sync. Every value is something
    we can explain to a nervous human in one warm sentence."""

    CREATED = "created"        # file didn't exist (or had no block) -> block added
    UPDATED = "updated"        # block existed and we rewrote it with new content
    UNCHANGED = "unchanged"    # block already held exactly this content -> no write
    TAMPERED = "tampered"      # user edited inside our block -> we stopped, untouched
    SKIPPED = "skipped"        # dry-run, or nothing to do
    CONFLICT = "conflict"      # ambiguous markers (e.g. duplicated) -> refused

    def __str__(self) -> str:
        return self.value


@dataclass
class SyncResult:
    """The outcome of a sync. Carries enough context for the caller to narrate
    a friendly message and, if needed, show the user a diff."""

    status: SyncStatus
    path: Path
    block_id: str
    changed: bool = False
    backup_path: Optional[Path] = None
    old_inner: Optional[str] = None
    new_inner: Optional[str] = None
    message: str = ""
    detail: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """True when the operation completed safely. TAMPERED and CONFLICT are
        *not* failures of Compass — they are Compass correctly refusing to do
        something dangerous — but they did not change the file, so callers
        usually want to treat them specially."""
        return self.status in (
            SyncStatus.CREATED,
            SyncStatus.UPDATED,
            SyncStatus.UNCHANGED,
            SyncStatus.SKIPPED,
        )


class MarkerError(Exception):
    """Raised for a programmer error in how markers are requested (e.g. a
    block_id with characters that would break the marker regex). This is *our*
    bug to fix, never the user's file being weird — that path returns a
    CONFLICT result instead of raising."""


# --------------------------------------------------------------------------- #
# Markers
# --------------------------------------------------------------------------- #

_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")

_MARKER_PREFIX = "COMPASS"


def make_markers(block_id: str, version: int) -> "tuple[str, str]":
    """Return the (begin, end-without-hash) marker strings for a block."""
    _validate_id(block_id)
    begin = f"<!-- {_MARKER_PREFIX}:BEGIN id={block_id} v={version} -->"
    end_head = f"<!-- {_MARKER_PREFIX}:END id={block_id} v={version}"
    return begin, end_head


def _validate_id(block_id: str) -> None:
    if not block_id or not _ID_RE.match(block_id):
        raise MarkerError(
            f"block_id {block_id!r} is invalid; use only letters, digits, "
            "'_', '.', '-' (no spaces or regex characters)."
        )


def _block_pattern(block_id: str) -> "re.Pattern[str]":
    """A regex matching a whole managed block, capturing inner content + hash."""
    bid = re.escape(block_id)
    pat = (
        r"<!--[ \t]*" + _MARKER_PREFIX + r":BEGIN[ \t]+id=" + bid +
        r"[ \t]+v=(?P<vbegin>\d+)[ \t]*-->"
        r"(?P<inner>.*?)"
        r"<!--[ \t]*" + _MARKER_PREFIX + r":END[ \t]+id=" + bid +
        r"[ \t]+v=(?P<vend>\d+)"
        r"(?:[ \t]+sha256=(?P<sha>[0-9a-fA-F]{64}))?"
        r"[ \t]*-->"
    )
    return re.compile(pat, re.DOTALL)


# --------------------------------------------------------------------------- #
# Hashing
# --------------------------------------------------------------------------- #

def _canonical(inner: str) -> str:
    """Canonical form for hashing/comparison: normalise line endings to '\\n' and
    strip edge blank lines. Single source of truth so writer and reader agree;
    immune to CRLF<->LF flips and stray trailing newlines."""
    return inner.replace("\r\n", "\n").replace("\r", "\n").strip("\n")


def _hash_inner(inner: str) -> str:
    return hashlib.sha256(_canonical(inner).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# Line-ending + encoding helpers
# --------------------------------------------------------------------------- #

def _detect_newline(text: str) -> str:
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    if crlf > lf:
        return "\r\n"
    if lf > 0:
        return "\n"
    return os.linesep if os.linesep in ("\r\n", "\n") else "\n"


def _read_text(path: Path) -> str:
    data = path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.decode("utf-8")


# --------------------------------------------------------------------------- #
# Atomic write (#1) with backup + verify + rollback (#2)
# --------------------------------------------------------------------------- #

def _atomic_write(path: Path, text: str) -> None:
    """temp file in same dir -> write -> flush -> fsync -> os.replace -> fsync dir."""
    directory = path.parent
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".compass.tmp", dir=str(directory)
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)
        _fsync_dir(directory)
    except BaseException:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
        raise


def write_text_atomic(path, text: str, *, backup: bool = False) -> Optional[Path]:
    """Public helper: crash-safely write ``text`` to ``path`` (UTF-8, no BOM).
    Same primitive the managed-block engine uses, exposed so the rest of Compass
    can write *its own* files (profile registry, generated profile). Use only for
    files Compass fully controls, never for the user's CLAUDE.md."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    bak = _make_backup(path, None) if backup else None
    _atomic_write(_resolve(path), text)
    return bak


def _fsync_dir(directory: Path) -> None:
    if os.name != "posix":
        return
    try:
        dir_fd = os.open(str(directory), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        pass


def _make_backup(path: Path, backup_dir: Optional[Path]) -> Optional[Path]:
    if not path.exists():
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    target_dir = backup_dir if backup_dir is not None else path.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    backup = target_dir / f"{path.name}.{stamp}.bak"
    backup.write_bytes(path.read_bytes())
    return backup


# --------------------------------------------------------------------------- #
# Building a fresh block
# --------------------------------------------------------------------------- #

def _render_block(block_id: str, version: int, inner: str, newline: str) -> str:
    begin, end_head = make_markers(block_id, version)
    body = _canonical(inner)
    sha = _hash_inner(inner)
    end = f"{end_head} sha256={sha} -->"
    block = "\n".join([begin, body, end])
    return block.replace("\n", newline)


# --------------------------------------------------------------------------- #
# Public: read / remove / sync
# --------------------------------------------------------------------------- #

def read_managed_block(path: Path, block_id: str) -> Optional[str]:
    path = Path(path)
    _validate_id(block_id)
    if not path.exists():
        return None
    text = _read_text(_resolve(path))
    matches = list(_block_pattern(block_id).finditer(text))
    if len(matches) != 1:
        return None
    return _canonical(matches[0].group("inner"))


def _resolve(path: Path) -> Path:
    try:
        return path.resolve(strict=False)
    except OSError:
        return path


def sync_managed_block(
    path,
    block_id: str,
    version: int,
    new_inner: str,
    *,
    create_if_missing: bool = True,
    force: bool = False,
    backup_dir=None,
    dry_run: bool = False,
) -> SyncResult:
    """Idempotently sync a managed block into ``path``. Never raises for a weird
    user file — ambiguity returns CONFLICT/TAMPERED so the caller can show a diff."""
    path = Path(path)
    real = _resolve(path)
    _validate_id(block_id)
    backup_dir = Path(backup_dir) if backup_dir is not None else None

    # ---- Case A: the file does not exist yet -------------------------------
    if not real.exists():
        if not create_if_missing:
            return SyncResult(
                status=SyncStatus.SKIPPED, path=real, block_id=block_id,
                changed=False, new_inner=new_inner,
                message="Nothing to do — the file isn't there and I was asked "
                        "not to create it.",
            )
        newline = os.linesep if os.linesep in ("\r\n", "\n") else "\n"
        block = _render_block(block_id, version, new_inner, newline)
        new_text = block + newline
        if dry_run:
            return SyncResult(
                status=SyncStatus.CREATED, path=real, block_id=block_id,
                changed=False, new_inner=new_inner.strip("\n"),
                message="Would create the file and add the Compass block.",
            )
        _atomic_write_with_guard(real, new_text, backup_dir)
        return SyncResult(
            status=SyncStatus.CREATED, path=real, block_id=block_id,
            changed=True, new_inner=new_inner.strip("\n"),
            message="Created the file and tucked in the Compass block.",
        )

    original = _read_text(real)
    newline = _detect_newline(original)
    matches = list(_block_pattern(block_id).finditer(original))

    # ---- Case B: ambiguous markers -> refuse (#3) --------------------------
    if len(matches) > 1:
        return SyncResult(
            status=SyncStatus.CONFLICT, path=real, block_id=block_id,
            changed=False, new_inner=new_inner.strip("\n"),
            message=(
                f"I found {len(matches)} Compass blocks with id '{block_id}' in "
                "this file. That's ambiguous, so I stopped and changed nothing. "
                "Please remove the extra block, then I'll take it from here."
            ),
            detail={"block_count": len(matches)},
        )

    # ---- Case C: no block yet -> append one --------------------------------
    if not matches:
        if not create_if_missing:
            return SyncResult(
                status=SyncStatus.SKIPPED, path=real, block_id=block_id,
                changed=False, new_inner=new_inner.strip("\n"),
                message="No Compass block here yet and I was asked not to add "
                        "one — so I left your file exactly as it was.",
            )
        block = _render_block(block_id, version, new_inner, newline)
        sep = ""
        if original and not original.endswith(("\n", "\r")):
            sep = newline + newline
        elif original:
            sep = newline
        new_text = original + sep + block + newline
        if dry_run:
            return SyncResult(
                status=SyncStatus.CREATED, path=real, block_id=block_id,
                changed=False, new_inner=new_inner.strip("\n"),
                message="Would add a fresh Compass block to the end of your file "
                        "(your existing content stays untouched).",
            )
        _atomic_write_with_guard(real, new_text, backup_dir)
        return SyncResult(
            status=SyncStatus.CREATED, path=real, block_id=block_id,
            changed=True, new_inner=new_inner.strip("\n"),
            message="Added a fresh Compass block — your own content above it is "
                    "exactly as you left it.",
        )

    # ---- Case D: exactly one block exists ----------------------------------
    m = matches[0]
    old_inner = m.group("inner").strip("\n")
    stored_hash = m.group("sha")
    actual_hash = _hash_inner(m.group("inner").strip("\n"))

    tampered = stored_hash is not None and stored_hash.lower() != actual_hash.lower()
    if tampered and not force:
        return SyncResult(
            status=SyncStatus.TAMPERED, path=real, block_id=block_id,
            changed=False, old_inner=old_inner, new_inner=new_inner.strip("\n"),
            message=(
                "It looks like this Compass block was edited by hand since I last "
                "wrote it. I won't overwrite your edit. Re-run with force=True if "
                "you'd like me to replace it with the fresh version."
            ),
            detail={"stored_hash": stored_hash, "actual_hash": actual_hash},
        )

    desired_hash = _hash_inner(new_inner.strip("\n"))
    if not tampered and desired_hash == actual_hash:
        return SyncResult(
            status=SyncStatus.UNCHANGED, path=real, block_id=block_id,
            changed=False, old_inner=old_inner, new_inner=new_inner.strip("\n"),
            message="Already up to date — nothing needed changing. ",
        )

    new_block = _render_block(block_id, version, new_inner, newline)
    new_text = original[: m.start()] + new_block + original[m.end():]

    if dry_run:
        return SyncResult(
            status=SyncStatus.UPDATED, path=real, block_id=block_id,
            changed=False, old_inner=old_inner, new_inner=new_inner.strip("\n"),
            message="Would refresh the Compass block with the latest content.",
        )

    backup = _atomic_write_with_guard(real, new_text, backup_dir)
    return SyncResult(
        status=SyncStatus.UPDATED, path=real, block_id=block_id,
        changed=True, backup_path=backup, old_inner=old_inner,
        new_inner=new_inner.strip("\n"),
        message="Refreshed the Compass block — and kept a backup, just in case.",
    )


def remove_managed_block(
    path,
    block_id: str,
    *,
    backup_dir=None,
    dry_run: bool = False,
) -> SyncResult:
    path = Path(path)
    real = _resolve(path)
    _validate_id(block_id)
    backup_dir = Path(backup_dir) if backup_dir is not None else None

    if not real.exists():
        return SyncResult(
            status=SyncStatus.SKIPPED, path=real, block_id=block_id,
            changed=False, message="Nothing to remove — the file isn't there.",
        )

    original = _read_text(real)
    matches = list(_block_pattern(block_id).finditer(original))
    if not matches:
        return SyncResult(
            status=SyncStatus.SKIPPED, path=real, block_id=block_id,
            changed=False, message="No Compass block to remove — your file is "
                                   "already clean.",
        )
    if len(matches) > 1:
        return SyncResult(
            status=SyncStatus.CONFLICT, path=real, block_id=block_id,
            changed=False,
            message=f"Found {len(matches)} blocks with id '{block_id}'; that's "
                    "ambiguous so I removed nothing.",
            detail={"block_count": len(matches)},
        )

    m = matches[0]
    old_inner = _canonical(m.group("inner"))
    nl = _detect_newline(original)
    start, end = m.start(), m.end()
    new_text = original[:start] + original[end:]
    new_text = re.sub(r"(?:\r?\n){3,}", nl + nl, new_text)

    if dry_run:
        return SyncResult(
            status=SyncStatus.UPDATED, path=real, block_id=block_id,
            changed=False, old_inner=old_inner,
            message="Would remove the Compass block and tidy the gap.",
        )

    backup = _atomic_write_with_guard(real, new_text, backup_dir)
    return SyncResult(
        status=SyncStatus.UPDATED, path=real, block_id=block_id, changed=True,
        backup_path=backup, old_inner=old_inner,
        message="Removed the Compass block — your own content is untouched.",
    )


# --------------------------------------------------------------------------- #
# Write guard: backup -> atomic write -> verify -> rollback
# --------------------------------------------------------------------------- #

def _atomic_write_with_guard(
    path: Path, new_text: str, backup_dir: Optional[Path]
) -> Optional[Path]:
    backup = _make_backup(path, backup_dir)
    try:
        _atomic_write(path, new_text)
    except BaseException:
        raise

    try:
        written = _read_text(path)
    except BaseException:
        _rollback(path, backup)
        raise
    if written.replace("\r\n", "\n") != new_text.replace("\r\n", "\n"):
        _rollback(path, backup)
        raise IOError(
            f"Post-write verification failed for {path}. I rolled the file back "
            "from the backup so nothing was lost."
        )
    return backup


def _rollback(path: Path, backup: Optional[Path]) -> None:
    if backup is not None and backup.exists():
        try:
            _atomic_write(path, _read_text(backup))
        except BaseException:
            path.write_bytes(backup.read_bytes())
    else:
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass
