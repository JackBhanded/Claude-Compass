"""cli.py — the friendly ``compass`` command line.

    compass init                 set up your local profile store
    compass ask                  show the next calibration question
    compass answer <id> "..."    answer it (becomes a profile note)
    compass show                 your full profile + where each bit came from
    compass list                 same, compact
    compass forget <n>           remove a note (and re-sync so it's gone everywhere)
    compass approve <n> | --all  approve an inferred note so it goes live
    compass sync [--dry-run]     push your profile into Claude's memory
    compass pause | resume       kill-switch: pull / restore Compass's influence
    compass status               where things stand
    compass log                  recent activity
    compass install-hook         make it automatic (SessionStart)
    compass uninstall-hook       remove the automatic hook
    compass hook                 (internal) run by Claude Code at session start
    compass doctor               quick health check

Every message aims to bring a small smile — even the unhappy ones.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

from . import __version__
from .hookconfig import (
    hook_command,
    install_live_hook,
    install_session_start_hook,
    settings_path,
    uninstall_live_hook,
    uninstall_session_start_hook,
)
from .questions import QuestionBank
from .store import FACET_CATEGORIES, Obs, Store, StoreError, default_home
from .surfaces import claude_code_home, discover_surfaces, load_extra_surfaces
from .sync import preview_all, sync_all

COMPASS = "[*]"   # ASCII-safe little marker for headers


def _out(msg: str = "") -> None:
    print(msg)


def _store() -> Store:
    return Store(default_home())


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #

def cmd_init(args) -> int:
    s = _store()
    s.init()
    _out(f"{COMPASS} Your profile store is ready at {s.home}")
    _out("    Get started with:  python -m claude_compass ask")
    return 0


def cmd_ask(args) -> int:
    s = _store()
    s.init()
    qb = QuestionBank(s)
    q = qb.next_question()
    if not q:
        _out(f"{COMPASS} No more questions for now — your profile's looking great. ")
        _out("    (Re-open old ones anytime with: python -m claude_compass ask --reset)")
        return 0
    if getattr(args, "reset", False):
        qb.reset_skips()
        q = qb.next_question()
    qb.mark_asked()
    _out(f"{COMPASS} A quick one to help Claude work the way you like:")
    _out("")
    _out(f"    {q.text}")
    if q.options:
        _out("")
        for i, opt in enumerate(q.options, 1):
            _out(f"      {i}) {opt}")
        how = "numbers, e.g. 1,3" if q.multi else "a number"
        _out("")
        _out(f"    Answer:  python -m claude_compass answer {q.id} <{how} — or type your own>")
    else:
        _out("")
        _out(f"    Answer:  python -m claude_compass answer {q.id} \"your answer\"")
    _out(f"    Skip:    python -m claude_compass skip {q.id}")
    return 0


def cmd_quickstart(args) -> int:
    s = _store()
    s.init()
    qb = QuestionBank(s)
    n = qb.quickstart()
    if n == 0:
        _out(f"{COMPASS} Nothing to fill — you've already answered the questions "
             "that have recommended defaults. ")
        return 0
    _out(f"{COMPASS} Filled {n} recommended defaults — a strong baseline in one go.")
    _out("    They're marked '(default)'; tweak any with show / edit / forget, or "
         "keep answering questions to make them yours.")
    sync_all(s)
    _out("    Synced into your Claude sessions.")
    return 0


def cmd_answer(args) -> int:
    s = _store()
    s.init()
    qb = QuestionBank(s)
    final = qb.resolve_answer(args.id, args.text)   # turns a number into the option text
    facet = qb.answer(args.id, final) if final else None
    if not facet:
        _out(f"{COMPASS} Hmm, I couldn't record that — check the question id "
             "(see: python -m claude_compass ask) and that your answer isn't empty.")
        return 1
    _out(f"{COMPASS} Got it — added to your profile: \"{facet.text}\"")
    _out("    Run  python -m claude_compass sync  to share it with your sessions.")
    return 0


def cmd_skip(args) -> int:
    s = _store()
    s.init()
    if QuestionBank(s).skip(args.id):
        _out(f"{COMPASS} Skipped — I won't ask that one again (until you reset).")
        return 0
    _out(f"{COMPASS} I don't recognise that question id.")
    return 1


def _print_facets(s: Store) -> None:
    ordered = s.ordered_facets()
    if not ordered:
        _out("    Your profile is empty. Try:  python -m claude_compass ask")
        return
    labels = dict(FACET_CATEGORIES)
    last_cat = None
    for i, f in enumerate(ordered, 1):
        cat = f.normalised_category()
        if cat != last_cat:
            _out("")
            _out(f"  {labels.get(cat, cat)}")
            last_cat = cat
        tag = "" if f.approved else "  [pending review]"
        src = "" if f.source == "you" else f"  ({f.source})"
        _out(f"    [{i}] {f.text}{src}{tag}")


def cmd_show(args) -> int:
    s = _store()
    _out(f"{COMPASS} Your Compass profile (what every session can see about how "
         "you work):")
    _print_facets(s)
    pending = s.pending_facets()
    if pending:
        _out("")
        _out(f"    {len(pending)} note(s) are pending your review (inferred, not "
             "yet shared). Approve with: python -m claude_compass approve <n>")
    return 0


def cmd_forget(args) -> int:
    s = _store()
    if not s.remove_facet(args.index):
        _out(f"{COMPASS} No note at [{args.index}] — see: python -m claude_compass show")
        return 1
    _out(f"{COMPASS} Removed note [{args.index}].")
    # delete == gone everywhere: re-sync immediately so it leaves your CLAUDE.md too.
    reports = sync_all(s)
    if reports:
        _out("    Re-synced — it's gone from your Claude memory too, not just here.")
    return 0


def cmd_edit(args) -> int:
    s = _store()
    f = s.edit_facet(args.index, args.text)
    if not f:
        _out(f"{COMPASS} No note at [{args.index}] (see: python -m claude_compass "
             "show), or the new text was empty.")
        return 1
    _out(f"{COMPASS} Updated note [{args.index}]: \"{f.text}\"")
    sync_all(s)
    _out("    Re-synced — your sessions now see the edit.")
    return 0


def cmd_approve(args) -> int:
    s = _store()
    if args.all:
        n = s.approve_all()
        _out(f"{COMPASS} Approved {n} note(s). Run  python -m claude_compass sync  "
             "to share them.")
        return 0
    if args.index is None:
        _out(f"{COMPASS} Give a number (see: python -m claude_compass show) or --all.")
        return 1
    if s.approve_facet(args.index):
        _out(f"{COMPASS} Approved note [{args.index}] — it'll go live on the next sync.")
        return 0
    _out(f"{COMPASS} Nothing pending at [{args.index}].")
    return 1


def cmd_sync(args) -> int:
    s = _store()
    s.init()
    reports = preview_all(s) if args.dry_run else sync_all(s, force=args.force)
    if s.is_paused():
        _out(f"{COMPASS} Compass is PAUSED — sync removes your profile from "
             "Claude's memory. Run  python -m claude_compass resume  to turn it "
             "back on.")
    elif args.dry_run:
        _out(f"{COMPASS} Dry run — here's what I *would* do (nothing written):")
    else:
        _out(f"{COMPASS} Synced your profile into every Claude memory surface:")
    if not reports:
        _out("    (No Claude memory surfaces found. Is Claude Code installed? "
             "Looked in: " + str(claude_code_home()) + ")")
        return 0
    _out("")
    blocked = False
    for r in reports:
        _out("    " + r.headline)
        if r.result.status.value in ("tampered", "conflict"):
            blocked = True
    if blocked:
        _out("")
        _out("    A surface needs your eyes (a block was hand-edited or is "
             "ambiguous). Re-run with --force once you're happy. I changed "
             "nothing there.")
        return 2
    return 0


def cmd_pause(args) -> int:
    s = _store()
    s.init()
    s.set_paused(True)
    s.log_event("paused by user")
    _out(f"{COMPASS} Paused. Pulling your profile out of Claude's memory now...")
    sync_all(s)   # removes the block from every surface
    _out("    Done — Compass is no longer influencing your sessions. Your profile "
         "is safe here. Resume anytime: python -m claude_compass resume")
    return 0


def cmd_resume(args) -> int:
    s = _store()
    s.init()
    s.set_paused(False)
    s.log_event("resumed by user")
    _out(f"{COMPASS} Welcome back — restoring your profile to Claude's memory...")
    sync_all(s)
    _out("    Done. Compass is steering again. ")
    return 0


def cmd_status(args) -> int:
    s = _store()
    qb = QuestionBank(s)
    _out(f"{COMPASS} Claude Compass status")
    _out("")
    facets = s.load()
    approved = len(s.approved_facets())
    pending = len(s.pending_facets())
    _out(f"  Profile:   {approved} live note(s)"
         + (f", {pending} pending review" if pending else "")
         + f"   ({s.home})")
    _out(f"  Paused:    {'YES - not influencing sessions' if s.is_paused() else 'no'}")
    surfaces = discover_surfaces(extra_paths=load_extra_surfaces(s.home))
    manifest = s.load_manifest().get("surfaces", {})
    _out(f"  Surfaces:  {len(surfaces)} found")
    for surf in surfaces:
        entry = manifest.get(surf.key)
        when = entry.get("last_sync", "never") if entry else "never synced yet"
        _out(f"    - {surf.label}  ({when})")
    sp = settings_path(claude_code_home())
    hooked = sp.exists() and "claude_compass" in sp.read_text(encoding="utf-8", errors="ignore")
    _out(f"  Auto-sync: {'ON' if hooked else 'off'}"
         + ("" if hooked else "  (turn on: python -m claude_compass install-hook)"))
    nxt = qb.next_question()
    if nxt:
        _out(f"  Next Q:    \"{nxt.text}\"")
    return 0


def cmd_log(args) -> int:
    s = _store()
    events = s.read_recent_events(args.lines)
    if not events:
        _out(f"{COMPASS} No activity yet — run a sync and it'll show up here.")
        return 0
    _out(f"{COMPASS} Recent activity:")
    _out("")
    for line in events:
        _out("  " + line)
    _out("")
    _out(f"    Full log: {s.activity_log_path}")
    return 0


def cmd_install_hook(args) -> int:
    res = install_session_start_hook(claude_code_home())
    _out(f"{COMPASS} {res.message}")
    if res.backup_path:
        _out(f"    (backup: {res.backup_path})")
    return 0 if res.ok else 1


def cmd_uninstall_hook(args) -> int:
    res = uninstall_session_start_hook(claude_code_home())
    _out(f"{COMPASS} {res.message}")
    return 0 if res.ok else 1


def cmd_hook(args) -> int:
    """Run by Claude Code on SessionStart. Prints ONLY the hook JSON on stdout:
    the profile as additionalContext, plus — gently, at most once per interval —
    one calibration question for the session to (optionally) ask."""
    s = _store()
    try:
        s.init()
        sync_all(s)  # refresh the file; ignore per-surface detail
        context = ""
        if not s.is_paused():
            context = s.render_profile()
            qb = QuestionBank(s)
            if qb.due():
                q = qb.next_question()
                if q:
                    qb.mark_asked()
                    context += (
                        "\n\n[Compass] If it fits naturally, you might ask the "
                        f"user (once): \"{q.text}\" — if they answer, remind them "
                        f"they can save it with: compass answer {q.id} \"...\"")
    except Exception:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "SessionStart", "additionalContext": ""}}))
        return 0
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SessionStart", "additionalContext": context}}))
    return 0


def cmd_dashboard(args) -> int:
    from .dashboard import write_dashboard
    s = _store()
    s.init()
    out = write_dashboard(s)

    # --static (or a fallback if the server can't bind): just the HTML file.
    if getattr(args, "static", False):
        _out(f"{COMPASS} Your dashboard is ready: {out}")
        if not args.no_open:
            try:
                import webbrowser
                webbrowser.open(out.as_uri())
                _out("    Opening it in your browser now. ")
            except Exception:
                _out("    Open that file in any browser to see it.")
        return 0

    # Live mode: a tiny local server so you can answer right in the page and it
    # saves + re-syncs with no command typed. Falls back to the static file if it
    # can't start (e.g. no free port).
    try:
        return _serve_dashboard(s, open_browser=not args.no_open)
    except Exception:
        _out(f"{COMPASS} Your dashboard is ready: {out}")
        _out("    (Couldn't start the live-answer server — opening the file instead.)")
        if not args.no_open:
            try:
                import webbrowser
                webbrowser.open(out.as_uri())
            except Exception:
                pass
        return 0


def _serve_dashboard(store, open_browser: bool = True) -> int:
    """Serve the dashboard on 127.0.0.1 so answers save straight from the page."""
    import json as _json
    import threading
    import webbrowser
    from http.server import BaseHTTPRequestHandler, HTTPServer

    from .appmodel import do_sync
    from .dashboard import render_dashboard_html

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # keep the terminal quiet
            return

        def _send(self, code, body, ctype="text/html; charset=utf-8"):
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(data)
            except Exception:
                pass

        def do_GET(self):
            if self.path in ("/", "/index.html", "/dashboard.html"):
                self._send(200, render_dashboard_html(store))
            else:
                self._send(404, "not found", "text/plain; charset=utf-8")

        def _read_json(self):
            try:
                n = int(self.headers.get("Content-Length", 0))
                return _json.loads(self.rfile.read(n) or b"{}")
            except Exception:
                return {}

        def do_POST(self):
            payload = self._read_json()
            qb = QuestionBank(store)
            try:
                if self.path == "/answer":
                    qid = str(payload.get("id", "")).strip()
                    text = str(payload.get("text", "")).strip()
                    final = qb.resolve_answer(qid, text) if qid else None
                    facet = qb.answer(qid, final) if final else None
                    if not facet:
                        return self._send(400, '{"ok":false}', "application/json")
                    try:
                        do_sync(store)   # share it with every session, no command
                    except Exception:
                        pass
                    return self._send(200, '{"ok":true}', "application/json")
                if self.path == "/skip":
                    qb.skip(str(payload.get("id", "")).strip())
                    return self._send(200, '{"ok":true}', "application/json")
            except Exception:
                return self._send(400, '{"ok":false}', "application/json")
            self._send(404, '{"ok":false}', "application/json")

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    port = httpd.server_address[1]
    url = f"http://127.0.0.1:{port}/"
    _out(f"{COMPASS} Compass dashboard is live at {url}")
    _out("    Answer questions right in the page — it saves and re-syncs instantly.")
    _out("    Press Ctrl+C here when you're done.")
    if open_browser:
        threading.Timer(0.4, lambda: _safe_open(webbrowser, url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        _out(f"\n{COMPASS} Dashboard closed. Your profile is saved. ")
    finally:
        httpd.server_close()
    return 0


def _safe_open(webbrowser, url):
    try:
        webbrowser.open(url)
    except Exception:
        pass


def cmd_tray(args) -> int:
    try:
        from .app import main as app_main
    except Exception:
        _out(f"{COMPASS} The tray needs the desktop app. Install PySide6: "
             "pip install --user PySide6")
        return 1
    return app_main(start_in_tray=True)


def cmd_hook_prompt(args) -> int:
    """Run by Claude Code on UserPromptSubmit (live mode). Prints ONLY the hook
    JSON: the current profile as additionalContext, so edits land on the very
    next message. Fast — no sync; empty when paused."""
    s = _store()
    try:
        s.init()
        context = "" if s.is_paused() else s.render_profile()
    except Exception:
        context = ""
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit", "additionalContext": context}}))
    return 0


def cmd_live(args) -> int:
    ch = claude_code_home()
    if args.state == "off":
        res = uninstall_live_hook(ch)
        _out(f"{COMPASS} {res.message}")
        return 0 if res.ok else 1
    res = install_live_hook(ch)
    _out(f"{COMPASS} {res.message}")
    if res.ok:
        _out("    Live mode is ON — in new Claude Code sessions your profile "
             "refreshes before every message, so edits take effect on your next "
             "prompt (not just new sessions). Turn off with: compass live off")
    return 0 if res.ok else 1


def cmd_doctor(args) -> int:
    s = _store()
    _out(f"{COMPASS} Compass check-up")
    _out("")
    _out(f"  Python:      {sys.version.split()[0]}")
    _out(f"  Store:       {'ok' if s.exists() else 'not initialised (run init)'} ({s.home})")
    ch = claude_code_home()
    _out(f"  Claude home: {'found' if ch.exists() else 'not found'}  ({ch})")
    _out(f"  Paused:      {'yes' if s.is_paused() else 'no'}")
    _out(f"  Hook cmd:    {hook_command()}")
    _out("")
    _out("  If all of the above looks right, you're pointed true. ")
    return 0


def cmd_scan(args) -> int:
    """Declination Phase 1: read your latest transcript, map telling phrases to
    the facets they bear on, and record them as evidence. Read-only on what your
    sessions see — it never flips a facet or changes your CLAUDE.md (that's a
    later phase). ``--dry-run`` shows the findings without recording anything."""
    from datetime import datetime, timezone
    from pathlib import Path
    from .detector import scan_turns
    from .transcripts import find_latest_transcript, read_user_turns

    s = _store()
    s.init()
    path = Path(args.file) if args.file else find_latest_transcript(cwd=os.getcwd())
    if not path or not path.exists():
        _out(f"{COMPASS} No transcript found to scan. Point me at one with: "
             "python -m claude_compass scan --file <path-to.jsonl>")
        return 1

    since = 0 if args.all else s.get_scan_offset(str(path))
    turns, new_offset = read_user_turns(path, since)
    hits = scan_turns(turns)

    by_qid: dict = {}
    for f in s.load():
        by_qid.setdefault(f.question_id, []).append(f)

    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    session = path.stem
    pairs, matched, skipped_fixed = [], [], 0
    for h in hits:
        targets = by_qid.get(h.question_id, [])  # Phase 1 never invents a facet
        for f in targets:
            if f.mode == "fixed":
                skipped_fixed += 1   # a switch you own — declination keeps hands off
                continue
            pairs.append((f.id, Obs(ts=ts, session=session, signal=h.signal,
                                    strength=h.strength, suggests=h.suggests,
                                    source="heuristic")))
            matched.append((f, h))

    _out(f"{COMPASS} Scanned {len(turns)} new user turn(s) in {path.name}")
    if not matched and not skipped_fixed:
        _out("    Nothing stood out - no observations to record.")
    for f, h in matched:
        arrow = f" -> {h.suggests}" if h.suggests else ""
        _out(f"    {h.signal:<11} \"{f.text}\"  (matched: \"{h.matched}\"{arrow})  [{f.mode}]")
    if skipped_fixed:
        _out(f"    ({skipped_fixed} hit(s) ignored — they target fixed switches you own.)")

    if args.dry_run:
        _out("")
        _out("    Dry run - nothing recorded, scan position unchanged.")
        return 0

    n = s.record_observations(pairs)
    s.set_scan_offset(str(path), new_offset)
    s.log_event(f"scan: recorded {n} observation(s) from {path.name}")
    _out("")
    _out(f"    Recorded {n} observation(s) to the evidence ledger. "
         "(Nothing your sessions read changed - flips arrive in Phase 2.)")
    return 0


# --------------------------------------------------------------------------- #
# parser
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="compass",
        description="Keep every Claude session attuned to how you like to work.",
    )
    p.add_argument("--version", action="version",
                   version=f"claude-compass {__version__}")
    sub = p.add_subparsers(dest="command")

    sub.add_parser("init", help="set up the local profile store").set_defaults(func=cmd_init)

    sub.add_parser("quickstart",
                   help="fill recommended defaults for a strong baseline in one go"
                   ).set_defaults(func=cmd_quickstart)

    a = sub.add_parser("ask", help="show the next calibration question")
    a.add_argument("--reset", action="store_true", help="bring skipped questions back")
    a.set_defaults(func=cmd_ask)

    an = sub.add_parser("answer", help="answer a question")
    an.add_argument("id")
    an.add_argument("text")
    an.set_defaults(func=cmd_answer)

    sk = sub.add_parser("skip", help="skip a question")
    sk.add_argument("id")
    sk.set_defaults(func=cmd_skip)

    sub.add_parser("show", help="your full profile + sources").set_defaults(func=cmd_show)
    sub.add_parser("list", help="your profile (compact)").set_defaults(func=cmd_show)

    fg = sub.add_parser("forget", help="remove a note (re-syncs so it's gone everywhere)")
    fg.add_argument("index", type=int)
    fg.set_defaults(func=cmd_forget)

    ed = sub.add_parser("edit", help="edit a note's text (re-syncs)")
    ed.add_argument("index", type=int)
    ed.add_argument("text")
    ed.set_defaults(func=cmd_edit)

    ap = sub.add_parser("approve", help="approve an inferred (pending) note")
    ap.add_argument("index", type=int, nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.set_defaults(func=cmd_approve)

    sy = sub.add_parser("sync", help="push your profile into Claude's memory")
    sy.add_argument("--dry-run", action="store_true")
    sy.add_argument("--force", action="store_true")
    sy.set_defaults(func=cmd_sync)

    sub.add_parser("pause", help="kill-switch: pull Compass out of your sessions").set_defaults(func=cmd_pause)
    sub.add_parser("resume", help="restore Compass to your sessions").set_defaults(func=cmd_resume)
    sub.add_parser("status", help="where things stand").set_defaults(func=cmd_status)

    lg = sub.add_parser("log", help="recent activity")
    lg.add_argument("--lines", type=int, default=20)
    lg.set_defaults(func=cmd_log)

    d = sub.add_parser("dashboard", help="open the visual status dashboard")
    d.add_argument("--no-open", action="store_true",
                   help="write the HTML file but don't open a browser")
    d.add_argument("--static", action="store_true",
                   help="just write the HTML file (don't start the live-answer server)")
    d.set_defaults(func=cmd_dashboard)

    sub.add_parser("tray", help="run Compass quietly in your system tray").set_defaults(func=cmd_tray)
    sub.add_parser("install-hook", help="make sync automatic").set_defaults(func=cmd_install_hook)

    lv = sub.add_parser("live", help="turn live per-message profile updates on/off (Claude Code)")
    lv.add_argument("state", nargs="?", choices=["on", "off"], default="on")
    lv.set_defaults(func=cmd_live)
    sub.add_parser("hook-prompt", help=argparse.SUPPRESS).set_defaults(func=cmd_hook_prompt)
    sub.add_parser("uninstall-hook", help="remove the automatic hook").set_defaults(func=cmd_uninstall_hook)
    sub.add_parser("hook", help=argparse.SUPPRESS).set_defaults(func=cmd_hook)
    sub.add_parser("doctor", help="quick health check").set_defaults(func=cmd_doctor)

    sc = sub.add_parser("scan",
                        help="learn from your latest transcript (records evidence; "
                             "changes nothing your sessions see)")
    sc.add_argument("--dry-run", action="store_true",
                    help="show what would be recorded, write nothing")
    sc.add_argument("--file", help="scan a specific transcript .jsonl (default: your latest)")
    sc.add_argument("--all", action="store_true",
                    help="rescan from the start, ignoring the saved position")
    sc.set_defaults(func=cmd_scan)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
