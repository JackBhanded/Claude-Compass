# DECLINATION.md — Compass's self-correcting engine

> *Declination* (navigation): the drift between magnetic north and true north
> that **changes over time and must be corrected**. A compass that never corrects
> for declination slowly lies to you. This document specifies how Compass keeps
> the profile pointing at *true* north — your real, current working style — by
> watching how you actually behave and recalibrating itself.

**Status:** design **v2** — approved shape, not yet built.
**Builds on:** the v0.2 "learn-from-history" roadmap item, evolved from *learn
once* into *stay calibrated*.

> **What changed in v2.** v1 stored a continuous "confidence" score per facet and
> mutated it with log-odds math. We scrapped it. A mutated score can't explain
> itself, conflates *staleness* with *contradiction*, and drifts — all fatal for a
> trust-centric tool. v2 makes each facet's state an **evidence ledger** and turns
> every decision into a deterministic **query** over it. See §3.

---

## 1. The problem

Today every facet is locked at 100% confidence forever. That causes the two
failure modes Jack flagged from day one:

- **Ossification** — a preference you've outgrown keeps being injected, and a
  fresh Claude obediently obeys a ghost.
- **Bloat** — low-signal facts accumulate and drown the high-signal ones.

A self-correcting Compass detects when your *behavior* contradicts a *stored
belief*, then resolves the conflict — silently for cosmetic prefs, by asking for
anything that touches trust or identity.

**Two distinct axes, deliberately kept separate (the v2 insight):**

- **Staleness** — *"has anyone exercised this lately?"* A question of **time**.
  Resolved by a gentle "still true?" re-confirm. Being stale is **not** being
  wrong.
- **Contradiction** — *"is your behavior fighting this?"* A question of
  **evidence**. Resolved by an `auto` flip or a `suggest` proposal you approve.

v1's single score smushed these together, which manufactured a re-confirm-fatigue
bug (facets rotting toward uncertainty even when nothing contradicted them). v2
never conflates them.

## 2. Design decisions (locked)

| Decision | Choice | Rationale |
|---|---|---|
| Facet state | **Evidence ledger**, not a stored score | Auditable, deterministic, can't drift; *is* the dashboard's "why did this change?" receipt. |
| Detector | **Hybrid** — local heuristics gate, your own Claude adjudicates | Most turns contradict nothing; heuristics avoid paying for "no change." Claude only runs on flagged candidates. |
| Flip threshold | **≥3 consistent observations across ≥2 sessions, dominant alternative** | Snappy enough to adapt, strict enough to resist single-session over-fit. |
| Per-facet **mode** | **Every facet is `auto` / `suggest` / `fixed` — you set the mix** | `auto` = silent low-stakes tuning; `suggest` = learns but you approve before it changes; `fixed` = you own the switch, engine never touches it. Risky/unknown facets **floor at `suggest`** (never `auto`). |
| Trigger | **Own lightweight hook**, gated at ~12 min elapsed AND ≥6 new turns | Fires during active chat without secretly depending on live-mode being on (see §8). |
| Worker | **Detached** — the hook never blocks a prompt | A prompt must never wait on an LLM scan. |

## 3. Mental model — the evidence ledger

Each facet owns a small, **bounded** append-only ledger of *observations*. There
is **no stored confidence number.** Every policy decision is a pure query over
the ledger, recomputed on demand.

An observation:

```json
{ "ts": "2026-05-22T14:30:00Z", "session": "abc123",
  "signal": "CONTRADICT", "strength": "strong",
  "suggests": "as long as it needs", "source": "claude|heuristic|behavior" }
```

- `signal` ∈ `SUPPORT | CONTRADICT | SUGGEST_ALT`.
- `strength` ∈ `weak | strong` — set by the adjudicator, so a query can weight a
  firm "stop that" above an offhand one. (We store strength as data, not as a
  pre-collapsed scalar.)
- `suggests` — the alternative value, when the signal points at one.
- The ledger keeps the **last `N=10` observations per facet** (`TUNABLE`); older
  ones fold into a small rolling tally so history isn't lost, just compacted.

### 3.1 Decisions are queries, not stored state

```
            ┌──────────────────── facet ledger ────────────────────┐
            │  obs · obs · obs · obs · obs  (newest → oldest)       │
            └───────────────────────────────────────────────────────┘
                                   │
        ┌──────────────┬───────────┼───────────┬──────────────┐
        ▼              ▼           ▼            ▼              ▼
   should flip?   should ask?  is it stale?  contested?   display
                                                          confidence
```

| Question | Query | Drives |
|---|---|---|
| **Should it flip?** | ≥3 CONTRADICT/SUGGEST_ALT across ≥2 sessions, one alt holds ≥60% of alt-votes — **and** facet is in `auto` mode | silent auto-tune |
| **Should we propose?** | same evidence, but facet is in `suggest` mode | pending recalibration → you approve |
| **Is it stale?** | newest *active* observation older than `14 days` (`TUNABLE`) | gentle "still true?" re-confirm |
| **Is it contested?** | a flip followed by CONTRADICT-back within `7 days` (`TUNABLE`) | freeze auto-tune, escalate |
| **Display confidence** | recent SUPPORT − CONTRADICT, weighted by strength | dashboard sparkline — **derived, never stored** |

**`fixed`-mode facets short-circuit all of the above** (§4): the detector skips
them entirely — no observations recorded, no queries run. They change only when
*you* set them.

### 3.2 The flip (`auto` mode)

When the *should-flip* query is true: rewrite the facet text to the dominant
alternative, append a `FLIP` marker to the ledger (so the change is itself
audited), log it, refresh the dashboard "recent recalibrations" panel, and
re-sync. Fully reversible via `compass edit` / `forget`.

### 3.3 The proposal (`suggest` mode)

Same evidence, **no silent change.** Enqueue a *pending recalibration* and surface
it through `questions.py`, which already knows the option-space and whether the
facet is a `guardrail`. Your answer resolves it the normal, audited way.

### 3.4 Staleness ≠ doubt

A facet nobody has exercised in `14 days` is **stale**, not **distrusted**. Stale
facets keep injecting unchanged (stale beats empty — your v0.1 principle) and just
earn a low-priority "still true?" the next time a question is `due()`. Confirming
it stamps a fresh SUPPORT observation. This is why removing the score *fixes*
re-confirm fatigue instead of patching it: time and evidence never collide.

## 4. Modes & defaults

Every facet has a **mode** — the operative control over what declination may do to
it. Mode is **user-settable** (§9); each facet just starts in a sensible *default*
mode derived from its character.

| Mode | What declination does | Reversible? |
|---|---|---|
| `auto` 🟢 | Learns and changes it **silently** (logged, revertable) | yes — `compass log` + `edit`/`forget` |
| `suggest` 🟡 | Learns and **proposes**; nothing changes until *you* approve | n/a — never changes unprompted |
| `fixed` 🔴 | **Never touches it** — no observations, no queries; you own the switch | n/a — only you change it |

### 4.1 Default mode (derived, precedence order)

```
fixed    if  facet is context-dependent — no single value is even correct
             (comm_length, fmt_length, wf_thoroughness)
suggest  elif facet is risky/unknown — guardrail, safety, autonomy, identity,
             or unclassifiable (no matched question_id)          ← the safety floor
         or   facet is mirror-prone format
             (fmt_lists, fmt_tldr, fmt_structure, comm_emoji)
auto     else  low mirror-risk, learns well from feedback
             (comm_tone, comm_warmth, comm_order, learning-style, …)
```

### 4.2 The safety floor (fail-closed)

You can move any facet between modes — **except** you can never set a
guardrail / safety / autonomy / identity / unclassifiable facet to `auto`. Those
floor at `suggest`: you may *lock* them harder (`fixed`) but never let Compass
change them silently. So nothing risky — and nothing Compass can't confidently map
— is ever rewritten without your say-so. `compass mode … auto` simply refuses on
those.

### 4.3 Why three, not two

`auto` keeps the engine earning its keep on safe dials. `fixed` hands you the
switch on dials where inference is wrong by construction (length, thoroughness).
`suggest` is the middle that makes **mirror-prone-but-learnable** dials safe — it
learns the pattern but routes the *decision* to you, honouring Compass's founding
rule: *nothing inferred goes live until you approve it.*

## 5. The hybrid detector

### Stage 1 — heuristics (cheap, local, free) — tuned for **recall**
Scan only the *new* user turns since the last offset for active-signal patterns
mapped to facet categories. Examples:

| Signal in your message | Flags facet | As |
|---|---|---|
| "more detail / longer / explain more / go deeper" | `comm_length=short` | CONTRADICT |
| "just the code / skip the explanation / tl;dr / too long" | verbose length | CONTRADICT |
| repeated "no / stop / I said / don't" on the same theme | matching facet | CONTRADICT |
| "love the emoji / drop the emoji" | `comm_emoji` | SUGGEST_ALT |
| consistently picking fast over thorough | `wf_thoroughness` | SUGGEST_ALT |

Flag liberally — a false alarm is cheap, a miss is not. **If nothing is flagged,
Stage 2 does not run and zero tokens are spent.**

### Stage 2 — your Claude (only on flagged candidates) — tuned for **precision**
One batched, structured call: pass the candidate facets + the relevant excerpts,
ask Claude to classify each as `SUPPORT | CONTRADICT | SUGGEST_ALT(value)` with a
`strength` and the target facet `id`. Returns strict JSON, which becomes ledger
observations. Shells out to the user's *own* local Claude.

### Two clean signal sources, one trap avoided
- **Reactions to Claude's output** are subject to the feedback-loop trap (§6.3),
  so only *active* reactions count, never passive non-complaint.
- **Your own intrinsic behavior** — how *you* write, what *you* pick when offered
  options — is **safe SUPPORT/SUGGEST_ALT**, because it isn't a reaction to what
  Compass injected. The detector tags observations with `source` so the ledger
  keeps the distinction.

### Closing the recall gap
Heuristics can miss subtle contradictions. Mitigation: **once per day**, run one
full Claude pass over the day's session regardless of heuristic flags. Cheap
daily, and it sweeps what the rules didn't catch.

## 6. Pitfalls & mitigations

1. **Single-session over-fit** — one "give me more detail" on a hairy topic ≠
   "stop being concise." → The flip query requires ≥3 observations across ≥2
   sessions; one ledger entry changes nothing.
2. **Context-dependent prefs** — "thorough normally, just-fix-it under pressure"
   looks like a contradiction but isn't. → A flip followed by a contradiction-back
   marks the facet **contested**: auto-tuning freezes and we escalate to a
   question.
3. **The feedback-loop trap** ⚠️ — Compass injects "short answers" → Claude is
   short → you don't complain → it looks endorsed. **Absence of complaint ≠
   endorsement.** → Passive non-complaint **never enters the ledger.** Only active
   reactions and your own intrinsic behavior are logged. The guard is a *filter on
   what gets recorded*, not a fragile weight.
4. **Silent ≠ invisible** — every flip writes a ledger marker + `activity.log`
   line, shows in a dashboard "recent recalibrations" panel, and is one command to
   revert. You should never wonder why a behavior changed.
5. **Privacy + cost** 💰🔒 — **same trust boundary as using Claude Code at all:
   nothing goes anywhere Claude isn't already going.** Stage 2 sends transcript
   excerpts to *your own* Claude (Anthropic), exactly as your normal sessions do —
   no third party, no new endpoint. Opt-in (`compass declination on`), respects the
   `pause` kill-switch, and a configurable **daily call budget** (`TUNABLE`,
   proposed 10) caps spend.

## 7. Data model changes (backward-compatible)

`Facet` gains optional fields, all defaulting to today's behavior. **No stored
confidence score** — that's the v2 correction.

| Field | Type | Default | Why |
|---|---|---|---|
| `id` | `str` (uuid4) | generated | Stable target for a correction across text edits |
| `question_id` | `str?` | best-effort match | Links facet → option-space + `guardrail` flag |
| `mode` | `str` (`auto` / `suggest` / `fixed`) | derived per §4; `fixed` for `comm_length` | What declination may do to this facet; user-overridable, with a `suggest` floor on risky facets |
| `ledger` | `list[Obs]` | `[]` | Bounded evidence log (last 10 + rolling tally); the single source of truth for every decision in §3 |

`Obs` = `{ts, session, signal, strength, suggests?, source}`. Display confidence
is computed from `ledger` on read; it is never persisted.

**Migration:** bump `PROFILE_VERSION 1 → 2`. On load, backfill `id` (uuid4),
empty `ledger`, best-effort `question_id` (match facet by its label prefix against
`Question.label`), and a default `mode` derived per §4 (`fixed` for `comm_length`
+ the context-dependent dials; `suggest` for mirror-prone + risky facets; `auto`
otherwise). Old profiles read unchanged; an un-matchable facet gets no
`question_id` and so defaults to `suggest`, **never `auto`** — migration can never
make an old note silently auto-tunable.

## 8. Trigger plumbing

v1 secretly piggybacked the live-mode hook — so with live mode off, declination
silently did nothing. v2 fixes that:

- `compass declination on` installs its **own** lightweight `UserPromptSubmit`
  hook (independent of `compass live on`), via the existing never-corrupt
  `hookconfig` machinery.
- The hook is a tiny, synchronous gate: read `last_scan_ts` + `turns_since_scan`
  from `state.json`; if `elapsed ≥ 12 min` **and** `turns ≥ 6` (`TUNABLE`), spawn
  `compass scan --detached` and reset the counters. Otherwise return instantly.
  **It never blocks the prompt.**
- The detached `scan` reads the transcript tail since the last byte offset, runs
  the hybrid detector, appends ledger observations, applies `auto`-mode flips,
  enqueues `suggest`-mode proposals, logs, and re-syncs.
- A future `compass tray` timer can also drive scans on a true wall clock — a
  nice enhancement, not required for v1.

## 9. New CLI surface

| Command | What it does |
|---|---|
| `compass declination on` / `off` | Opt-in master switch; installs/removes the scan hook |
| `compass scan [--detached] [--dry-run]` | Run a detection pass now (`--dry-run` shows what *would* change) |
| `compass drift` | Show each facet's ledger, derived confidence, stale/contested flags |
| `compass length <short\|balanced\|detailed\|adaptive>` | Set answer length directly — a `fixed` switch (`adaptive` = "you judge per task," the honest default for context-dependent length) |
| `compass mode <n> <auto\|suggest\|fixed>` | Set any facet's mode (§4). Refuses `auto` on a guardrail/safety/identity facet — the `suggest` floor |
| `compass log` | (existing) now also lists auto-recalibrations |
| `compass edit` / `forget` | (existing) revert an auto-tune you didn't like |

Mode is a per-facet dropdown in the dashboard, and `fixed` switches like answer
length get a one-click toggle — no terminal needed.

## 10. Testing plan (required — tests are non-negotiable here)

- **Ledger queries are pure** — flip/ask/stale/contested are deterministic
  functions of a ledger fixture; no hidden state.
- **Flip gate** — fires only at ≥3 obs across ≥2 sessions with a dominant alt;
  2 obs, or 3 in one session, or no dominant alt → no flip.
- **Stakes classification** — guardrail/identity/safety/autonomy/**unclassifiable**
  → HIGH; rest → LOW. (Explicit test that an un-`question_id`'d facet is HIGH.)
- **`fixed` is untouchable** — a `fixed` facet (and `comm_length` by default after
  migration) records **no** ledger observations, never flips, never proposes;
  `compass mode` / `compass length` is the only thing that changes it.
- **`suggest` never auto-applies** — a `suggest` facet that meets the flip query
  lands as a *pending* proposal, never a silent change.
- **Safety floor** — `compass mode <facet> auto` is refused for guardrail / safety
  / autonomy / identity / unclassifiable facets; they can only be `suggest` or `fixed`.
- **Default-mode derivation** — context-dependent → `fixed`; mirror-prone + risky
  → `suggest`; low-mirror → `auto`.
- **Risky facets never auto-flip** — a guardrail/safety facet under flip-pressure
  still lands as a pending proposal, never a silent change (trust gate holds).
- **Staleness ≠ doubt** — a facet with only old SUPPORT obs is *stale* (re-confirm
  due) but still injects unchanged and is never flipped.
- **Feedback-loop guard** — passive non-complaint produces **no** ledger entry.
- **Intrinsic-behavior support** — a `source="behavior"` SUPPORT obs is recorded
  and counts.
- **Contested freeze** — flip-then-contradict marks contested + stops auto-tuning.
- **Migration** — v1 profile backfills id/ledger/question_id without data loss;
  un-matchable facet becomes HIGH.
- **Hook gate** — does *not* spawn under the time/turn threshold; does when over;
  never blocks.
- **Heuristic mapping** — known phrases map to the right facet + signal.
- **Pause kill-switch** — disables scanning entirely.
- **Safe re-sync** — a flip re-syncs through the audited safe-write engine.
- **Ledger bound** — never exceeds N entries; overflow folds into the tally.

## 11. Phasing (each phase testable + shippable)

| Phase | Delivers | Behavior change |
|---|---|---|
| 0 | Data-model (id, question_id, ledger) + v1→v2 migration | None (invisible groundwork) |
| 1 | Heuristic detector + `compass scan --dry-run` + ledger writes | None visible (read-only findings) |
| 2 | Flip queries + `auto` flips + `suggest` proposals + `compass drift`/`mode` + dashboard panel | First real self-correction |
| 3 | Own scan hook + 12-min/6-turn gate + daily budget cap | Becomes automatic during chat |
| 4 | Stage-2 Claude adjudication + daily full pass | Precision + recall complete |
| 5 | Contested handling + staleness re-confirm wiring | Robustness hardening |

## 12. Open questions

- Default daily Claude-call budget? (proposed: **10**, `TUNABLE`)
- `compass drift` — CLI-only for v1, or also in the dashboard from the start?
- Tunables to calibrate against real usage once Phase 2 ships: ledger size `N=10`,
  stale window `14d`, contested window `7d`, flip count `3`, session span `2`,
  alt-dominance `60%`, scan gate `12 min / 6 turns`.
- Should intrinsic-behavior SUPPORT (`source="behavior"`) count toward the flip
  *threshold*, or only toward staleness refresh? (Leaning: staleness only — keep
  flips driven by explicit contradiction.)
