# Changelog

All notable changes to Claude Compass are documented here.
This project follows [Semantic Versioning](https://semver.org/).

## [0.2.0] — 2026-05-25

A brand-new look, in-page answering, groundwork for a self-correcting Compass, and
a startup convenience. Nothing your Claude sessions read changes from the learning
work — the new learning is strictly read-only evidence-gathering you can inspect.

### Changed
- **A gorgeous new look (elevated Claude-brew + dark mode).** The dashboard is now
  frosted glassmorphism over a soft drifting aurora, with gradient accents, a
  count-up stat row, a calibration progress bar, a sleek dark mode (remembered
  across reloads), and a strong type hierarchy. The double-click app window is
  restyled to match — stat row, progress bar, a bold accent question card, soft
  card shadows, mode pills, and the same light/dark toggle.

### Added
- **Answer right in the dashboard — no command.** `compass dashboard` now starts a
  tiny local helper, so you can pick a suggested answer or type your own straight
  in the page; it saves and re-syncs every Claude surface instantly. The app window
  answers inline too. (`compass dashboard --static` keeps the old write-a-file
  behaviour.)
- **Declination, Phase 1 (opt-in, read-only).** Compass can now learn from your
  own local Claude history without changing anything yet. A heuristic detector
  scans the *new* user turns in a transcript, maps telling phrases (e.g. "just the
  code", "drop the emoji", repeated "no/stop") to the matching facet, and records
  them as **evidence** in a per-facet ledger. Run it with `compass scan`
  (`--dry-run` shows what it would record without writing). Each facet has a
  **mode** — `auto` / `suggest` / `fixed` — and `fixed` facets are never touched.
  This is the safe first slice of the "stay calibrated over time" design in
  `DECLINATION.md`; the actual self-correction (flips and proposals) lands in a
  later phase.
- **Run at startup.** A "Run at startup" toggle in the tray menu pins Compass to
  your per-user Windows startup (no admin needed), so it keeps your sessions
  attuned from the moment you log in. Greyed out when running from source.

### Notes
- Privacy: the scan reads your local transcripts on your machine; the heuristic
  stage sends nothing anywhere. (Future phases that ask your own Claude to
  adjudicate stay within the same trust boundary as using Claude Code at all, are
  opt-in, and respect the `pause` kill-switch.)

[0.2.0]: https://github.com/JackBhanded/claude-compass/compare/v0.1.0...v0.2.0

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
- **Live mode** (`compass live on`) — an optional Claude Code UserPromptSubmit
  hook that re-injects your profile before *every* message, so edits take effect
  on your very next prompt, not only in new sessions.
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
