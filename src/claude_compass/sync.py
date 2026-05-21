"""sync.py — push the curated profile into every Claude memory surface, safely.

The conductor. It asks the :mod:`store` for the rendered profile, asks
:mod:`surfaces` where to put it, and hands the actual edit to the audited
managed-block engine. The profile goes inline into a ``COMPASS:BEGIN id=profile``
block — which sits happily beside a Lifejacket projects block in the same file,
since the two tools key on different marker prefixes.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .safewrite import (
    SyncResult,
    SyncStatus,
    remove_managed_block,
    sync_managed_block,
)
from .store import PROFILE_BLOCK_ID, PROFILE_VERSION, Store
from .surfaces import Surface, discover_surfaces, load_extra_surfaces

__all__ = ["SurfaceReport", "sync_all", "preview_all", "profile_fingerprint"]


@dataclass
class SurfaceReport:
    surface: Surface
    result: SyncResult

    @property
    def changed(self) -> bool:
        return self.result.changed

    @property
    def headline(self) -> str:
        icons = {
            SyncStatus.CREATED: "+", SyncStatus.UPDATED: "~",
            SyncStatus.UNCHANGED: "=", SyncStatus.SKIPPED: ".",
            SyncStatus.TAMPERED: "!", SyncStatus.CONFLICT: "!",
        }
        icon = icons.get(self.result.status, "?")
        return f"[{icon}] {self.surface.label}: {self.result.message.strip()}"


def profile_fingerprint(profile: str) -> str:
    norm = profile.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def sync_all(
    store: Store,
    *,
    claude_home: Optional[Path] = None,
    extra_paths: Optional[List[Path]] = None,
    force: bool = False,
    create_if_missing: bool = True,
    dry_run: bool = False,
) -> List[SurfaceReport]:
    """Sync the rendered profile into every discovered surface.

    If Compass is **paused**, this REMOVES the profile block from every surface
    instead of writing it — the kill switch — so Compass immediately stops
    influencing your sessions, while your profile data stays safe in the store.
    """
    paused = store.is_paused()
    profile = store.render_profile()
    fp = profile_fingerprint(profile)

    extras = list(load_extra_surfaces(store.home))
    if extra_paths:
        extras.extend(Path(p) for p in extra_paths)

    surfaces = discover_surfaces(claude_home=claude_home, extra_paths=extras)

    reports: List[SurfaceReport] = []
    for surface in surfaces:
        if paused:
            result = remove_managed_block(
                surface.path, PROFILE_BLOCK_ID,
                backup_dir=store.backups_dir, dry_run=dry_run,
            )
        else:
            result = sync_managed_block(
                surface.path,
                PROFILE_BLOCK_ID,
                PROFILE_VERSION,
                profile,
                create_if_missing=create_if_missing,
                force=force,
                backup_dir=store.backups_dir,
                dry_run=dry_run,
            )
        if not dry_run:
            store.record_sync(
                surface.key, path=str(surface.path),
                status=str(result.status),
                profile_hash=("(paused)" if paused else fp),
            )
            verb = "paused (profile removed)" if paused else "sync"
            store.log_event(f"{verb} - {surface.label}: {result.status}")
        reports.append(SurfaceReport(surface=surface, result=result))

    if not dry_run and not surfaces:
        store.log_event("sync - no Claude memory surfaces found")
    if not dry_run and not paused:
        store.write_profile_md(profile)

    return reports


def preview_all(
    store: Store,
    *,
    claude_home: Optional[Path] = None,
    extra_paths: Optional[List[Path]] = None,
) -> List[SurfaceReport]:
    return sync_all(store, claude_home=claude_home, extra_paths=extra_paths, dry_run=True)
