# Changelog

All notable changes to Claude Compass are documented here.
This project follows [Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-05-21

First public release. Keep every Claude session attuned to how you like to work.

### Added
- **Profile store + safe sync** — a curated set of working-style "facets"
  rendered to a tiny profile and spliced into `~/.claude/CLAUDE.md` (read by both
  Claude Code and Cowork) under a self-managed `COMPASS` block. Built on the same
  audited safe-write engine as Claude Lifejacket (atomic writes, backup +
  rollback, marker-bounded edits, hand-edit detection). Coexists with a Lifejacket
  block in the same file without collision.
- **Inquisitive companion** — a deeply-researched bank of ~125 calibration
  questions (grounded in Anthropic's steering docs + working-style psychology),
  each with best-first **clickable answer options** (single- or multi-select,
  plus type-your-own). ~25 are guardrail-setters whose answers become hard rules
  ("always confirm before deleting", "never commit secrets"). `compass ask` /
  `answer` (by number or words) turns replies into profile notes; frequency-capped
  so it never nags.
- **`quickstart`** — fills the recommended (best-first) answer for every question
  with a meaningful default, for a strong baseline in one click; tagged
  `(default)` so you can tweak any, and skips the open/placeholder ones.
- **Trust & control** — an approval gate (inferred notes never reach a session
  until you approve them), `compass pause`/`resume` as a real kill-switch
  (removes the block from your memory on the spot), and `compass forget` that
  re-syncs so deletes are gone everywhere (no ghost memories).
- **CLI** — `init / ask / answer / show / forget / approve / sync / pause /
  resume / status / log / dashboard / install-hook / uninstall-hook / doctor`.
- **SessionStart hook** — refreshes your profile and (gently, at most once every
  couple of days) surfaces one calibration question.
- **HTML dashboard** — light "Claude brew" status page with a **light/dark
  toggle**, a hero stat row + calibration progress bar, your profile by category
  (with sources + pending tags), surface status, activity, and the verbatim
  injected text. A read-only snapshot.
- **Double-click app** — the interactive surface: answer questions via clickable
  pills, **edit** / **approve** / **forget** any note, **pause/resume**, sync, and
  open the dashboard — and it lives in your **system tray** (minimize-to-tray;
  right-click for Sync / Pause / Dashboard / Quit; `compass tray` runs it quietly).
- **Edit** — `compass edit <n> "..."` (and the app's Edit button) fix a note in
  place; editing endorses it (becomes yours, approved) and re-syncs everywhere.
- **120+ tests** covering the engine, store, sync, control layer, questions,
  hook, CLI, dashboard, and app logic.

## [Unreleased] — ideas for v0.2

- **Call-your-own-Claude engine** (privacy-first, opt-in) powering:
  - **Learn-from-history** — draft profile notes from your local Claude transcripts.
  - **AI-generated adaptive questions** — infinite, personalized follow-ups based
    on what you've already told Compass and where the profile has gaps (so it's
    no longer limited to the built-in bank).
- **Go back / re-answer** in the question flow (`compass back` / a Back button)
  — step back to redo a just-answered question, not only edit it after the fact.
- Starter **presets** (one-click tuned profiles, e.g. "Senior / terse / autonomous").
- Stale-note re-confirmation.

[0.1.0]: https://github.com/JackBhanded/claude-compass/releases/tag/v0.1.0
