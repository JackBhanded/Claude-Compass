"""dashboard.py — a calm, light-Claude status page for Compass.

`compass dashboard` renders a single self-contained HTML file (no external
assets) into the store directory and opens it. It's the *window* into everything
Compass knows and is doing — the heart of the see-it / control-it promise:

  * a clear PAUSED banner when the kill-switch is on,
  * your profile notes grouped by category, each tagged with where it came from
    (you vs inferred) and whether it's live or pending your review,
  * which Claude surfaces it's synced to, and when,
  * the next calibration question,
  * a recent-activity log,
  * and — most importantly — the EXACT profile text every Claude session reads,
    shown verbatim.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from .hookconfig import HOOK_TAG, settings_path
from .questions import DEFAULT_QUESTIONS, QuestionBank
from .store import FACET_CATEGORIES, Store
from .surfaces import claude_code_home, discover_surfaces, load_extra_surfaces
from .sync import profile_fingerprint

__all__ = ["render_dashboard_html", "write_dashboard"]

_CREAM = "#F4EEE4"
_CARD = "#FBF8F2"
_INK = "#2B2722"
_MUTED = "#8A8178"
_ORANGE = "#D97757"
_LINE = "#E7DFD2"
_OK = "#3F8F77"
_WARN = "#D9A757"
_ERR = "#C0563F"
_IDLE = "#B8AFA3"

_CLAUDE_LOGO_PATH = "M4.709 15.955l4.72-2.647.08-.23-.08-.128H9.2l-.79-.048-2.698-.073-2.339-.097-2.266-.122-.571-.121L0 11.784l.055-.352.48-.321.686.06 1.52.103 2.278.158 1.652.097 2.449.255h.389l.055-.157-.134-.098-.103-.097-2.358-1.596-2.552-1.688-1.336-.972-.724-.491-.364-.462-.158-1.008.656-.722.881.06.225.061.893.686 1.908 1.476 2.491 1.833.365.304.145-.103.019-.073-.164-.274-1.355-2.446-1.446-2.49-.644-1.032-.17-.619a2.97 2.97 0 01-.104-.729L6.283.134 6.696 0l.996.134.42.364.62 1.414 1.002 2.229 1.555 3.03.456.898.243.832.091.255h.158V9.01l.128-1.706.237-2.095.23-2.695.08-.76.376-.91.747-.492.584.28.48.685-.067.444-.286 1.851-.559 2.903-.364 1.942h.212l.243-.242.985-1.306 1.652-2.064.73-.82.85-.904.547-.431h1.033l.76 1.129-.34 1.166-1.064 1.347-.881 1.142-1.264 1.7-.79 1.36.073.11.188-.02 2.856-.606 1.543-.28 1.841-.315.833.388.091.395-.328.807-1.969.486-2.309.462-3.439.813-.042.03.049.061 1.549.146.662.036h1.622l3.02.225.79.522.474.638-.079.485-1.215.62-1.64-.389-3.829-.91-1.312-.329h-.182v.11l1.093 1.068 2.006 1.81 2.509 2.33.127.578-.322.455-.34-.049-2.205-1.657-.851-.747-1.926-1.62h-.128v.17l.444.649 2.345 3.521.122 1.08-.17.353-.608.213-.668-.122-1.374-1.925-1.415-2.167-1.143-1.943-.14.08-.674 7.254-.316.37-.729.28-.607-.461-.322-.747.322-1.476.389-1.924.315-1.53.286-1.9.17-.632-.012-.042-.14.018-1.434 1.967-2.18 2.945-1.726 1.845-.414.164-.717-.37.067-.662.401-.589 2.388-3.036 1.44-1.882.93-1.086-.006-.158h-.055L4.132 18.56l-1.13.146-.487-.456.061-.746.231-.243 1.908-1.312-.006.006z"  # noqa: E501

_STATE_COLOUR = {"in_sync": _OK, "out_of_date": _WARN, "never": _IDLE, "attention": _ERR}


def _claude_logo_svg(size: int = 30) -> str:
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><title>Claude</title>'
        f'<path d="{_CLAUDE_LOGO_PATH}" fill="{_ORANGE}" fill-rule="nonzero"></path></svg>'
    )


def _dot(colour: str) -> str:
    live = " live" if colour == _OK else ""
    return f'<span class="dot{live}" style="background:{colour}"></span>'


def _surface_state(current_fp: str, entry) -> "tuple[str, str]":
    if not entry:
        return _IDLE, "Never synced"
    status = entry.get("status", "")
    if status in ("tampered", "conflict"):
        return _ERR, "Needs your eyes"
    if entry.get("profile_hash") == "(paused)":
        return _IDLE, "Paused (removed)"
    if entry.get("profile_hash") == current_fp:
        return _OK, "In sync"
    return _WARN, "Out of date"


def _fmt_time(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%a %d %b, %I:%M %p").lstrip("0")
    except (ValueError, TypeError):
        return iso or "—"


def render_dashboard_html(store: Store) -> str:
    esc = html.escape
    facets = store.ordered_facets()
    approved = [f for f in facets if f.approved]
    pending = [f for f in facets if not f.approved]
    profile_text = store.render_profile()
    current_fp = profile_fingerprint(profile_text)
    manifest = store.load_manifest().get("surfaces", {})
    surfaces = discover_surfaces(extra_paths=load_extra_surfaces(store.home))
    events = store.read_recent_events(12)
    paused = store.is_paused()
    qb = QuestionBank(store)
    next_q = qb.next_question()

    # Hero stats
    n_total_q = len(DEFAULT_QUESTIONS)
    n_answered = min(qb.answered_count(), n_total_q)
    calib_pct = round(n_answered / n_total_q * 100) if n_total_q else 0
    n_surf = len(surfaces)
    n_insync = sum(1 for s in surfaces
                   if _surface_state(current_fp, manifest.get(s.key))[1] == "In sync")

    sp = settings_path(claude_code_home())
    hook_on = sp.exists() and HOOK_TAG in sp.read_text(encoding="utf-8", errors="ignore")
    now = datetime.now(timezone.utc).astimezone().strftime(
        "%a %d %b %Y, %I:%M %p").lstrip("0")

    labels = dict(FACET_CATEGORIES)

    # ---- profile facets, grouped ----
    if facets:
        by_cat: Dict[str, List] = {}
        for f in facets:
            by_cat.setdefault(f.normalised_category(), []).append(f)
        groups = []
        for key, label in FACET_CATEGORIES:
            if key not in by_cat:
                continue
            rows = []
            for f in by_cat[key]:
                tag = ""
                if not f.approved:
                    tag = '<span class="pill pend">pending review</span>'
                elif f.source != "you":
                    tag = f'<span class="pill src">{esc(f.source)}</span>'
                rows.append(f'<div class="facet">{esc(f.text)} {tag}</div>')
            groups.append(f'<div class="catgroup"><div class="catname">{esc(label)}'
                          f'</div>{"".join(rows)}</div>')
        facets_html = "".join(groups)
    else:
        facets_html = ('<div class="card empty"><p>Your profile is empty.</p>'
                       '<code>compass ask</code></div>')

    # ---- surfaces ----
    if surfaces:
        rows = []
        for surf in surfaces:
            colour, label = _surface_state(current_fp, manifest.get(surf.key))
            last = _fmt_time(manifest.get(surf.key, {}).get("last_sync", ""))
            rows.append(f"""
      <div class="card surface">
        {_dot(colour)}
        <div class="surface-body">
          <div class="surface-label">{esc(surf.label)}</div>
          <div class="surface-path">{esc(str(surf.path))}</div>
        </div>
        <div class="surface-state">
          <div class="state-label" style="color:{colour}">{esc(label)}</div>
          <div class="state-time">{esc(last)}</div>
        </div>
      </div>""")
        surfaces_html = "".join(rows)
    else:
        surfaces_html = ('<div class="card empty"><p>No Claude memory surfaces '
                         f'found.</p><div class="surface-path">Looked in: '
                         f'{esc(str(claude_code_home()))}</div></div>')

    paused_banner = ""
    if paused:
        paused_banner = ('<div class="paused">PAUSED — Compass is not influencing '
                         'your sessions. Run <code>compass resume</code> to turn '
                         'it back on.</div>')

    pending_banner = ""
    if pending and not paused:
        pending_banner = (f'<div class="pending-banner">{len(pending)} note(s) '
                          'inferred from your history are waiting for your review '
                          '— they are NOT shared with any session until you '
                          'approve them (<code>compass approve --all</code>).</div>')

    hook_colour = _OK if hook_on else _IDLE
    hook_text = ("On — every session refreshes automatically"
                 if hook_on else "Off — turn on with: compass install-hook")
    nextq_html = (f'<div class="card"><b>Next question:</b> {esc(next_q.text)}'
                  f'<div class="hint">Answer with: compass answer {esc(next_q.id)} '
                  '"..."</div></div>') if next_q else ""

    activity = "\n".join(reversed(events)) if events else \
        "No activity yet — run a sync and it'll appear here."

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Claude Compass</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; padding: 0 0 56px; background: {_CREAM}; color: {_INK};
    font: 15px/1.5 -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
  .wrap {{ max-width: 860px; margin: 0 auto; padding: 0 24px; }}
  header {{ display: flex; align-items: center; gap: 12px; padding: 34px 0 6px; }}
  header .logo {{ display: inline-flex; }}
  header h1 {{ font-size: 24px; margin: 0; font-weight: 650; letter-spacing: -0.2px; }}
  header .sub {{ color: {_MUTED}; font-size: 13px; margin-top: 2px; }}
  .stats {{ display: flex; gap: 10px; margin: 18px 0 10px; flex-wrap: wrap; }}
  .stat {{ flex: 1; min-width: 92px; background: {_CARD}; border: 1px solid {_LINE};
    border-radius: 12px; padding: 12px 14px; text-align: center; }}
  .stat .num {{ font-size: 22px; font-weight: 650; color: {_ORANGE}; line-height: 1.1; }}
  .stat .lbl {{ font-size: 11px; color: {_MUTED}; margin-top: 4px;
    text-transform: uppercase; letter-spacing: 0.4px; }}
  .progress {{ height: 6px; background: {_LINE}; border-radius: 999px; overflow: hidden;
    margin: 0 0 6px; }}
  .progress .bar {{ height: 100%; background: {_ORANGE}; border-radius: 999px;
    transition: width .4s ease; }}
  h2 {{ font-size: 13px; text-transform: uppercase; letter-spacing: 0.8px;
    color: {_MUTED}; margin: 30px 0 12px; font-weight: 600; }}
  .card {{ background: {_CARD}; border: 1px solid {_LINE}; border-radius: 14px;
    padding: 16px 18px; margin-bottom: 12px; }}
  .catgroup {{ background: {_CARD}; border: 1px solid {_LINE}; border-radius: 14px;
    padding: 12px 18px; margin-bottom: 10px; }}
  .catname {{ color: {_ORANGE}; font-size: 12px; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }}
  .facet {{ padding: 4px 0; font-size: 14.5px; }}
  .pill {{ font-size: 11px; font-weight: 600; padding: 1px 8px; border-radius: 999px;
    margin-left: 6px; vertical-align: middle; }}
  .pill.pend {{ color: #854F0B; background: rgba(217,167,87,0.22); }}
  .pill.src {{ color: {_MUTED}; background: rgba(138,129,120,0.15); }}
  .paused {{ background: rgba(217,167,87,0.18); border: 1px solid {_WARN};
    color: #6b4e12; border-radius: 12px; padding: 12px 16px; margin: 14px 0;
    font-weight: 600; }}
  .pending-banner {{ background: rgba(63,143,119,0.10); border: 1px solid {_OK};
    color: #245c4a; border-radius: 12px; padding: 12px 16px; margin: 14px 0;
    font-size: 14px; }}
  .surface {{ display: flex; align-items: center; gap: 14px; }}
  .surface-body {{ flex: 1; min-width: 0; }}
  .surface-label {{ font-weight: 600; }}
  .surface-path {{ color: {_MUTED}; font-size: 11.5px; margin-top: 3px;
    font-family: ui-monospace, "Cascadia Code", Consolas, monospace;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .surface-state {{ text-align: right; white-space: nowrap; }}
  .state-label {{ font-weight: 600; font-size: 13.5px; }}
  .state-time {{ color: {_MUTED}; font-size: 11.5px; margin-top: 2px; }}
  .dot {{ width: 12px; height: 12px; border-radius: 50%; flex: none;
    box-shadow: 0 0 0 4px rgba(0,0,0,0.03); }}
  @keyframes lj-pulse {{ 0%,100%{{transform:scale(1);opacity:1}} 50%{{transform:scale(0.68);opacity:0.5}} }}
  .dot.live {{ animation: lj-pulse 1.9s ease-in-out infinite; }}
  @media (prefers-reduced-motion: reduce) {{ .dot.live {{ animation: none; }} }}
  .hookbar {{ display: flex; align-items: center; gap: 12px; }}
  .hint {{ color: {_MUTED}; font-size: 12px; margin-top: 6px;
    font-family: ui-monospace, Consolas, monospace; }}
  .digest {{ background: #fff; border: 1px dashed {_LINE}; border-radius: 12px;
    padding: 16px 18px; white-space: pre-wrap; font-size: 13.5px;
    font-family: ui-monospace, "Cascadia Code", Consolas, monospace;
    color: #4a443c; overflow-x: auto; }}
  .empty {{ text-align: center; color: {_MUTED}; }}
  .empty code {{ display: inline-block; margin-top: 8px; background: {_CREAM};
    padding: 6px 12px; border-radius: 8px; color: {_INK}; }}
  footer {{ color: {_MUTED}; font-size: 12px; text-align: center; margin-top: 34px; }}
  .tbtn {{ background: {_CARD}; border: 1px solid {_LINE}; color: {_MUTED};
    border-radius: 999px; padding: 6px 14px; font-size: 12px; cursor: pointer;
    flex: none; }}
  .tbtn:hover {{ color: {_INK}; }}
  .card, .catgroup, .stat {{ transition: transform .15s ease, background .2s ease,
    border-color .2s ease, color .2s ease; }}
  .card:hover, .catgroup:hover, .stat:hover {{ transform: translateY(-1px); }}
  body, .sub, h2, .digest, footer {{ transition: background .25s ease, color .25s ease; }}
  body.dark {{ background: #221d19; color: #ece6dc; }}
  body.dark .sub, body.dark h2, body.dark .stat .lbl, body.dark .surface-path,
  body.dark .state-time, body.dark .hint, body.dark footer {{ color: #a89f95; }}
  body.dark .card, body.dark .catgroup, body.dark .stat,
  body.dark .hookbar {{ background: #2c2620; border-color: #3a332c; }}
  body.dark .progress {{ background: #3a332c; }}
  body.dark .digest {{ background: #1d1814; border-color: #3a332c; color: #cfc7bb; }}
  body.dark .tbtn {{ background: #2c2620; border-color: #3a332c; color: #a89f95; }}
  body.dark .tbtn:hover {{ color: #ece6dc; }}
  body.dark .pill.src {{ background: rgba(255,255,255,0.08); color: #cfc7bb; }}
</style></head>
<body><div class="wrap">
  <header>
    <span class="logo">{_claude_logo_svg(32)}</span>
    <div style="flex:1"><h1>Claude Compass</h1>
      <div class="sub">Every Claude session, attuned to how you like to work.</div></div>
    <button class="tbtn" id="themeToggle" onclick="toggleTheme()" aria-label="Toggle light/dark theme">Dark</button>
  </header>

  <div class="stats">
    <div class="stat"><div class="num">{len(approved)}</div><div class="lbl">live notes</div></div>
    <div class="stat"><div class="num">{len(pending)}</div><div class="lbl">pending</div></div>
    <div class="stat"><div class="num">{n_answered}/{n_total_q}</div><div class="lbl">calibrated</div></div>
    <div class="stat"><div class="num">{n_insync}/{n_surf}</div><div class="lbl">in sync</div></div>
    <div class="stat"><div class="num">{'On' if hook_on else 'Off'}</div><div class="lbl">auto-sync</div></div>
  </div>
  <div class="progress" title="Calibration: {n_answered} of {n_total_q} answered"><div class="bar" style="width:{calib_pct}%"></div></div>

  {paused_banner}
  {pending_banner}

  <h2>Your profile &middot; {len(approved)} live{(", " + str(len(pending)) + " pending") if pending else ""}</h2>
  {facets_html}

  <h2>Claude memory surfaces</h2>
  {surfaces_html}

  <h2>Auto-sync</h2>
  <div class="card hookbar">{_dot(hook_colour)}<div>{esc(hook_text)}</div></div>

  {nextq_html}

  <h2>What every session is reading</h2>
  <div class="digest">{esc(profile_text)}</div>

  <h2>Recent activity</h2>
  <div class="digest">{esc(activity)}</div>

  <footer>Snapshot taken {esc(now)} &middot; re-run <code>compass dashboard</code> to refresh</footer>
</div>
<script>
function applyTheme(t){{ document.body.classList.toggle('dark', t==='dark');
  var b=document.getElementById('themeToggle'); if(b) b.textContent = (t==='dark'?'Light':'Dark'); }}
function toggleTheme(){{ var t=document.body.classList.contains('dark')?'light':'dark';
  try{{ localStorage.setItem('compass-theme', t); }}catch(e){{}} applyTheme(t); }}
(function(){{ var t='light'; try{{ t=localStorage.getItem('compass-theme')||'light'; }}catch(e){{}} applyTheme(t); }})();
</script>
</body></html>"""


def write_dashboard(store: Store) -> Path:
    store.home.mkdir(parents=True, exist_ok=True)
    out = store.home / "dashboard.html"
    out.write_text(render_dashboard_html(store), encoding="utf-8")
    return out
