# CLAUDE.md — Claude Compass

Context for any Claude (or human) picking up this repo. Keep it current.

## What this is

A Python tool that keeps every Claude session attuned to *how the user likes to
work*. You keep a small curated profile of working-style "facets"; Compass renders
it and safely splices it into `~/.claude/CLAUDE.md` — read by **both** Claude Code
and Cowork — inside a self-managed `COMPASS` block. Sibling of Claude Lifejacket
(which syncs *projects*); Compass syncs *the person*. Sync-IN only for v0.1.

## Architecture (`src/claude_compass/`)

- `safewrite.py` — **vendored** from Lifejacket (stdlib-only), re-keyed to the
  `COMPASS` marker prefix. The only code that edits the user's files; seven
  safety guarantees (atomic write, backup+verify+rollback, marker-bounded edits,
  hash idempotency + hand-edit detection, EOL preservation, symlink resolve,
  never auto-resolve conflicts). Coexists with a Lifejacket block in one file
  because the prefixes differ.
- `store.py` — the profile: `~/.claude-compass/` (`profile.json` facets,
  generated `profile.md`, `questions.json`, `manifest.json`, `state.json`,
  `backups/`, `activity.log`). A facet has a `source` (you/history) and an
  `approved` flag — **only approved facets render/inject** (the trust gate).
- `surfaces.py` / `sync.py` — find `~/.claude/CLAUDE.md` and inject the profile.
  When **paused** (`state.json`), sync REMOVES the block instead (kill-switch).
- `questions.py` — the inquisitive companion: a curated bank + answered/skipped
  state + an anti-nag `due()` frequency cap.
- `cli.py` / `__main__.py` — `init/ask/answer/show/forget/approve/sync/pause/
  resume/status/log/dashboard/install-hook/uninstall-hook/doctor/hook`.
- `hookconfig.py` — SessionStart hook (same never-corrupt settings.json care).
- `dashboard.py` — light-Claude HTML status page (verbatim profile, pending,
  surfaces, activity).
- `appmodel.py` (Qt-free, tested) + `app.py` (PySide6 window).

## Trust & control (the core design)

Compass stores *claims about the person* and will infer some, so control is
paramount: (1) inferred facets start **pending** and never inject until approved;
(2) `pause` removes the block from memory immediately; (3) `forget` re-syncs so
deletes are gone everywhere (no ghost memories). These mirror the prior-art
lessons (ChatGPT memory complaints, progressive-profiling research).

## Testing

`pip install -e ".[dev]" && pytest` (or double-click `run-tests.bat`). 120+ tests,
incl. the engine, the approval gate, the pause kill-switch, the anti-nag cap, and
a test that a COMPASS block coexists with a LIFEJACKET block untouched.

## Build & ship

`build-exe.ps1` (PyInstaller + PySide6) → `dist/Claude Compass.exe`. GitHub
Actions builds + attaches the .exe on a `v*` tag.

## Roadmap

v0.2: **learn-from-history** (read local Claude transcripts, summarize via the
user's own Claude, draft facets for review — opt-in, privacy-first); system tray;
stale-note re-confirmation.

## Part of the fleet

- [Claude Meter](https://github.com/JackBhanded/claude-meter) — live usage on your taskbar.
- [Claude Lifeboat](https://github.com/JackBhanded/claude-lifeboat) — backup & restore for Claude data.
- [Claude Lifejacket](https://github.com/JackBhanded/claude-lifejacket) — keep every session aware of your projects.
- **Claude Compass** — you are here. (Lifejacket syncs your projects; Compass syncs you. Independent, but best together.)

_Maintainer's working-style/personal context is kept in private notes, not in this public file._
