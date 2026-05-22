<div align="center">

<img src="assets/claude-logo.svg" width="64" alt="Claude" />

# Claude Compass

**Keep every Claude session attuned to *how you like to work*.**

You've explained your style to Claude a hundred times — "be blunt," "skip the
preamble," "I'm new to this part," "just show me the code." Compass remembers it
*for* you: a small, curated profile of your working style that it safely splices
into the memory every Claude session reads, so each one adapts to you from the
first message.

[![License: MIT](https://img.shields.io/badge/License-MIT-D97757.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-D97757.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-140%2B%20passing-3F8F77.svg)](#trust--control)

</div>

---

## What's inside

- **~125 calibration questions**, researched against Anthropic's steering docs +
  working-style psychology — each with **best-first, click-to-pick answers**.
- **~25 automatic guardrails** — your answer becomes a rule Claude follows
  ("always confirm before deleting," "never commit secrets").
- **You're in control** — approve / edit / forget any note; a **pause kill-switch**
  that pulls Compass out of your sessions on the spot; nothing inferred goes live
  until you approve it.
- **A light/dark dashboard** showing the *verbatim* profile every session reads,
  a **double-click app**, and a **system-tray** companion.
- **SessionStart auto-sync**, built on the same audited safe-write engine as
  Lifejacket. 140+ tests.

---

## Why

Claude Code and Cowork start every session as a blank slate about *you*. Compass
fixes that. It keeps a profile of how you like to work and injects it into the
user-level `~/.claude/CLAUDE.md` — read by **both** Claude Code and Cowork —
inside a clearly-marked, self-managed block. So "warm but concise," "challenge my
decisions," "I work ship-then-refine" travel with you into every new session, no
re-explaining.

It learns who you are two gentle ways:

- **By asking.** Now and then (never more than once every couple of days), Compass
  poses one thoughtful calibration question. Your answer becomes a profile note.
- **From your history** *(v0.2, opt-in)* — it will read your *local* Claude
  transcripts and draft profile notes for you to review.

**The questions are researched, not guessed.** The ~125 calibration questions are
grounded in Anthropic's own prompt-engineering and steering guidance *and* in
validated working-style psychology (Big Five, communication styles, learning &
cognition, accessibility). Each offers best-first, click-to-pick answers, and ~25
set automatic **guardrails** — turning your answer into a hard rule Claude follows
("always confirm before deleting," "never commit secrets," "never use these
libraries"). Small, high-signal, and chosen because each one *measurably* changes
how Claude works for you.

## Better together with Claude Lifejacket

Compass has a sibling, **[Claude Lifejacket](https://github.com/JackBhanded/claude-lifejacket)**.
They're independent — each works perfectly on its own — but they're designed to
complement each other, and together they're the magic:

| | Lifejacket | Compass |
|---|---|---|
| Syncs… | your **projects** | **you** |
| So every session knows… | *what* you're working on | *how* you like to work |

Install both and a fresh Claude session opens already knowing **your projects
*and* your style** — context *and* personalization, from the very first message,
with zero re-explaining. They write to the same `CLAUDE.md` but live in separate,
non-colliding blocks, so they never step on each other (or on your own notes).

## Trust & control

Compass stores *claims about you* and will eventually *infer* some — so it's the
most transparent and controllable tool you'll install:

- **Nothing inferred reaches your sessions until you approve it.** Things you say
  yourself go live immediately; anything Compass infers sits **pending** and is
  never injected until you review and approve it.
- **See everything.** The dashboard shows your profile grouped by category, where
  each note came from (you vs inferred), the *verbatim* text every session reads,
  and a full activity log.
- **A real kill-switch.** `compass pause` doesn't just stop syncing — it *removes*
  your profile from `CLAUDE.md` on the spot, so Compass instantly stops
  influencing every session, while keeping your data so you can fix and `resume`.
- **No ghost memories.** `compass forget` removes a note **and re-syncs**, so it's
  gone from your sessions too — not just the store.

All built on the same audited safe-write engine as Lifejacket (atomic writes,
backup + rollback, marker-bounded edits, never clobbers your hand-edits). 120+
tests.

## Install

**Easiest — the app (Windows):** download **`Claude Compass.exe`** from the
[latest release](https://github.com/JackBhanded/claude-compass/releases/latest)
and double-click it. A little window opens with your profile, the next question,
and Approve / Forget / Pause / Sync buttons. No Python, no terminal.

**For the command line (any platform):** Python 3.9+
([get it here](https://www.python.org/downloads/) — on Windows tick "Add to PATH").

- Windows: right-click `install.ps1` → **Run with PowerShell**, or `pip install --user .`
- macOS/Linux: `pip install --user .`

After installing, `python -m claude_compass <command>` always works; from the
project folder you can also run `.\compass <command>` (Windows) / `./compass <command>`.

## Quickstart

```bash
compass init                 # set up your local profile
compass quickstart           # (optional) fill recommended defaults for a fast baseline
compass ask                  # answer a calibration question or two
compass answer comm_tone "warm but concise"
compass sync                 # share your profile with every Claude session
compass install-hook         # make it automatic, forever
compass dashboard            # see everything it knows, in your browser
```

## Commands

| Command | What it does |
|---|---|
| `compass init` | Create the local profile store (`~/.claude-compass/`) |
| `compass quickstart` | Fill the recommended answers for a strong baseline in one go |
| `compass ask` | Show the next calibration question |
| `compass answer <id> "..."` | Answer it (becomes a profile note) |
| `compass show` | Your full profile + where each note came from |
| `compass forget <n>` | Remove a note (and re-sync so it's gone everywhere) |
| `compass edit <n> "..."` | Edit a note in place (re-syncs) |
| `compass approve <n>` / `--all` | Approve an inferred (pending) note |
| `compass tray` | Run quietly in your system tray |
| `compass sync [--dry-run]` | Push your profile into Claude's memory |
| `compass pause` / `resume` | Kill-switch: pull / restore Compass's influence |
| `compass dashboard` | Open the visual status page |
| `compass status` / `log` | Where things stand / recent activity |
| `compass install-hook` / `uninstall-hook` | Turn automatic syncing on/off |
| `compass live on` / `off` | Live mode: re-inject your profile before every message (Claude Code), so edits land on your next prompt |
| `compass doctor` | Quick health check |

## Roadmap

- **v0.2** — **learn-from-history**: read your *local* Claude transcripts and draft
  profile notes (opt-in, you review before anything syncs); a system-tray
  companion; richer re-confirmation of stale notes.

## Part of the fleet

- [Claude Meter](https://github.com/JackBhanded/claude-meter) — live usage on your taskbar.
- [Claude Lifeboat](https://github.com/JackBhanded/claude-lifeboat) — backup & restore for your Claude data.
- [Claude Lifejacket](https://github.com/JackBhanded/claude-lifejacket) — keep every session aware of your projects.
- **Claude Compass** — keep every session attuned to you. *(you are here)*

## About the author

<table>
<tr>
<td width="120" valign="top">
<img src="https://www.SawYouAtSinai.com/_layouts/images/team/jackbio.jpg" width="100" alt="Jack Bhanded">
</td>
<td valign="top">

Built by **[Jack Bhanded](https://www.sawyouatsinai.com/jewish-dating-team.aspx)**, Lead developer and architect at [SawYouAtSinai](https://www.sawyouatsinai.com). Devotee of innovative technologies and gadgets. Built this because he was tired of re-explaining how he likes to work to every fresh Claude session.

</td>
</tr>
</table>

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for the version-by-version list of changes.

## License

[MIT](LICENSE) © Jack Bhanded — do whatever you want, just keep the copyright notice.
