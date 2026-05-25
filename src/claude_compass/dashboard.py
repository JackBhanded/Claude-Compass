"""dashboard.py — Compass's status page, in the fleet's elevated-glass look.

`compass dashboard` renders this single self-contained HTML file (one Google-Fonts
link aside) and opens it. It's the window into everything Compass knows and is
doing — and, when served by the local helper (`compass dashboard`, which starts a
tiny 127.0.0.1 server), you can answer the next calibration question *right here*
and it saves + re-syncs with no command typed.

Design system (shared across the fleet): warm "Claude brew" identity, real Claude
logo, frosted glassmorphism over a soft drifting aurora, gradient accents,
restrained micro-animations, a sleek dark mode, and strong type hierarchy.
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from .hookconfig import HOOK_TAG, settings_path
from .questions import DEFAULT_QUESTIONS, QuestionBank
from .store import FACET_CATEGORIES, Store
from .surfaces import claude_code_home, discover_surfaces, load_extra_surfaces
from .sync import profile_fingerprint

__all__ = ["render_dashboard_html", "write_dashboard", "_claude_logo_svg"]

_ORANGE = "#D97757"  # official Claude logo coral (UI accent #C8632F is in the CSS)

_CLAUDE_LOGO_PATH = "M4.709 15.955l4.72-2.647.08-.23-.08-.128H9.2l-.79-.048-2.698-.073-2.339-.097-2.266-.122-.571-.121L0 11.784l.055-.352.48-.321.686.06 1.52.103 2.278.158 1.652.097 2.449.255h.389l.055-.157-.134-.098-.103-.097-2.358-1.596-2.552-1.688-1.336-.972-.724-.491-.364-.462-.158-1.008.656-.722.881.06.225.061.893.686 1.908 1.476 2.491 1.833.365.304.145-.103.019-.073-.164-.274-1.355-2.446-1.446-2.49-.644-1.032-.17-.619a2.97 2.97 0 01-.104-.729L6.283.134 6.696 0l.996.134.42.364.62 1.414 1.002 2.229 1.555 3.03.456.898.243.832.091.255h.158V9.01l.128-1.706.237-2.095.23-2.695.08-.76.376-.91.747-.492.584.28.48.685-.067.444-.286 1.851-.559 2.903-.364 1.942h.212l.243-.242.985-1.306 1.652-2.064.73-.82.85-.904.547-.431h1.033l.76 1.129-.34 1.166-1.064 1.347-.881 1.142-1.264 1.7-.79 1.36.073.11.188-.02 2.856-.606 1.543-.28 1.841-.315.833.388.091.395-.328.807-1.969.486-2.309.462-3.439.813-.042.03.049.061 1.549.146.662.036h1.622l3.02.225.79.522.474.638-.079.485-1.215.62-1.64-.389-3.829-.91-1.312-.329h-.182v.11l1.093 1.068 2.006 1.81 2.509 2.33.127.578-.322.455-.34-.049-2.205-1.657-.851-.747-1.926-1.62h-.128v.17l.444.649 2.345 3.521.122 1.08-.17.353-.608.213-.668-.122-1.374-1.925-1.415-2.167-1.143-1.943-.14.08-.674 7.254-.316.37-.729.28-.607-.461-.322-.747.322-1.476.389-1.924.315-1.53.286-1.9.17-.632-.012-.042-.14.018-1.434 1.967-2.18 2.945-1.726 1.845-.414.164-.717-.37.067-.662.401-.589 2.388-3.036 1.44-1.882.93-1.086-.006-.158h-.055L4.132 18.56l-1.13.146-.487-.456.061-.746.231-.243 1.908-1.312-.006.006z"  # noqa: E501


def _claude_logo_svg(size: int = 28) -> str:
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><title>Claude</title>'
        f'<path d="{_CLAUDE_LOGO_PATH}" fill="{_ORANGE}" fill-rule="nonzero"></path></svg>'
    )


# --- the shared design system (static; all colours live in CSS variables) ----
_CSS = """
  :root{
    --bg1:#F7F2E8; --bg2:#EDE3D1;
    --ink:#1C1712; --muted:#5F564B; --faint:#8C8174;
    --orange:#C8632F; --orange2:#E0875C; --amber:#B97E1E;
    --ok:#2E7D63; --okglow:rgba(46,125,99,.45);
    --line:rgba(43,39,34,.12);
    --glass:rgba(255,253,249,.38); --glass-strong:rgba(255,253,249,.60);
    --glass-blur:blur(34px) saturate(1.9);
    --sheen:inset 0 1px 0 rgba(255,255,255,.8), inset 0 0 0 1px rgba(255,255,255,.16);
    --shadow:var(--sheen), 0 1px 2px rgba(43,39,34,.05), 0 12px 32px -12px rgba(43,39,34,.24);
    --shadow-hi:var(--sheen), 0 1px 2px rgba(43,39,34,.06), 0 24px 54px -16px rgba(200,99,47,.46);
    --radius:18px; --radius-sm:12px;
    --grad:linear-gradient(135deg,var(--orange2),var(--orange));
    --aur1:rgba(217,119,87,.40); --aur2:rgba(217,167,87,.34); --aur3:rgba(63,143,119,.30);
  }
  body.dark{
    --bg1:#150F0B; --bg2:#1E1712;
    --ink:#F7F1E7; --muted:#B7AEA2; --faint:#7A7064;
    --orange:#E0875C; --orange2:#EE9E75; --amber:#E7B45E;
    --ok:#4FB592;
    --line:rgba(255,255,255,.10);
    --glass:rgba(38,31,25,.34); --glass-strong:rgba(46,38,30,.56);
    --glass-blur:blur(36px) saturate(1.7);
    --sheen:inset 0 1px 0 rgba(255,255,255,.14), inset 0 0 0 1px rgba(255,255,255,.05);
    --shadow:var(--sheen), 0 1px 2px rgba(0,0,0,.45), 0 16px 38px -14px rgba(0,0,0,.7);
    --shadow-hi:var(--sheen), 0 1px 2px rgba(0,0,0,.5), 0 28px 60px -18px rgba(232,145,111,.55);
    --aur1:rgba(232,145,111,.42); --aur2:rgba(217,167,87,.26); --aur3:rgba(63,143,119,.36);
  }
  *{box-sizing:border-box}
  html{scroll-behavior:smooth}
  body{margin:0;min-height:100vh;color:var(--ink);
    font:16px/1.6 "Instrument Sans",-apple-system,"Segoe UI",Roboto,sans-serif;
    background:
      radial-gradient(1100px 680px at 12% -8%, var(--aur1), transparent 60%),
      radial-gradient(900px 620px at 92% 4%, var(--aur2), transparent 58%),
      radial-gradient(1200px 800px at 70% 110%, var(--aur3), transparent 60%),
      linear-gradient(170deg,var(--bg1),var(--bg2));
    background-attachment:fixed;transition:color .4s ease, background .6s ease;}
  .aurora{position:fixed;inset:-20% -10% auto -10%;height:60vh;z-index:0;pointer-events:none;
    background:radial-gradient(420px 320px at 25% 30%, var(--aur1), transparent 70%),
      radial-gradient(380px 300px at 75% 20%, var(--aur2), transparent 70%);
    filter:blur(40px);opacity:.9;animation:drift 22s ease-in-out infinite alternate;}
  @keyframes drift{0%{transform:translate3d(-3%,-2%,0) scale(1)}100%{transform:translate3d(4%,3%,0) scale(1.12)}}
  .wrap{position:relative;z-index:1;max-width:920px;margin:0 auto;padding:0 22px 72px}
  header{display:flex;align-items:center;gap:14px;padding:40px 0 8px}
  .logo{display:inline-flex;width:46px;height:46px;align-items:center;justify-content:center;
    border-radius:14px;background:var(--glass-strong);box-shadow:var(--shadow);
    backdrop-filter:var(--glass-blur);-webkit-backdrop-filter:var(--glass-blur)}
  h1{font-size:27px;margin:0;font-weight:700;letter-spacing:-.4px;line-height:1.05;
    background:linear-gradient(120deg,var(--ink),var(--orange) 140%);
    -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
  body.dark h1{background:linear-gradient(120deg,#fff,var(--orange2));-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
  .sub{color:var(--muted);font-size:13.5px;margin-top:3px}
  .toggle{margin-left:auto;display:inline-flex;align-items:center;gap:8px;cursor:pointer;
    background:var(--glass);color:var(--muted);border-radius:999px;padding:9px 14px;font:inherit;
    font-size:13px;font-weight:600;box-shadow:var(--shadow);border:none;
    backdrop-filter:var(--glass-blur);-webkit-backdrop-filter:var(--glass-blur);
    transition:transform .2s ease, color .2s ease, box-shadow .3s ease}
  .toggle:hover{color:var(--ink);transform:translateY(-1px);box-shadow:var(--shadow-hi)}
  .toggle .ic{width:16px;height:16px;display:inline-block;transition:transform .5s cubic-bezier(.5,1.6,.4,1)}
  .toggle:hover .ic{transform:rotate(35deg)}
  .stats{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:24px 0 14px}
  @media(max-width:680px){.stats{grid-template-columns:repeat(2,1fr)}}
  .stat{position:relative;overflow:hidden;background:var(--glass);border-radius:var(--radius-sm);
    padding:16px 14px;text-align:center;box-shadow:var(--shadow);
    backdrop-filter:var(--glass-blur);-webkit-backdrop-filter:var(--glass-blur);
    transition:transform .25s cubic-bezier(.2,.8,.3,1), box-shadow .3s ease}
  .stat:hover{transform:translateY(-4px);box-shadow:var(--shadow-hi)}
  .stat::after{content:"";position:absolute;inset:0 0 auto 0;height:2px;background:var(--grad);
    transform:scaleX(0);transform-origin:left;transition:transform .4s ease}
  .stat:hover::after{transform:scaleX(1)}
  .stat .num{font-size:27px;font-weight:700;line-height:1.05;letter-spacing:-.5px;
    background:var(--grad);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
  .stat .lbl{font-size:10.5px;color:var(--muted);margin-top:6px;text-transform:uppercase;letter-spacing:.7px;font-weight:600}
  .progress{height:8px;background:rgba(43,39,34,.08);border-radius:999px;overflow:hidden;margin:4px 0 2px}
  body.dark .progress{background:rgba(255,255,255,.06)}
  .progress .bar{height:100%;width:0;border-radius:999px;background:var(--grad);
    box-shadow:0 0 14px rgba(217,119,87,.6);transition:width 1.1s cubic-bezier(.2,.8,.2,1)}
  .progress-cap{font-size:12px;color:var(--muted);margin:8px 2px 0}
  h2{font-size:12px;text-transform:uppercase;letter-spacing:1.2px;color:var(--muted);
    margin:34px 0 13px;font-weight:700;display:flex;align-items:center;gap:9px}
  h2::before{content:"";width:14px;height:2px;border-radius:2px;background:var(--grad)}
  .card{background:var(--glass);border-radius:var(--radius);padding:17px 19px;margin-bottom:12px;
    box-shadow:var(--shadow);backdrop-filter:var(--glass-blur);-webkit-backdrop-filter:var(--glass-blur);
    transition:transform .25s cubic-bezier(.2,.8,.3,1), box-shadow .3s ease}
  .card:hover{transform:translateY(-3px);box-shadow:var(--shadow-hi)}
  .catname{display:inline-flex;align-items:center;gap:7px;color:var(--orange);font-size:11.5px;font-weight:700;
    text-transform:uppercase;letter-spacing:.7px;margin-bottom:10px}
  .catname .d{width:6px;height:6px;border-radius:50%;background:var(--grad);box-shadow:0 0 8px var(--orange)}
  .facet{padding:7px 0;font-size:15px;font-weight:500;border-top:1px solid var(--line);display:flex;align-items:center;gap:8px;flex-wrap:wrap}
  .facet:first-of-type{border-top:none}
  .facet .txt{flex:1;min-width:60%}
  .pill{font-size:11px;font-weight:700;padding:2px 10px;border-radius:999px}
  .pill.pend{color:#8a5a12;background:rgba(217,167,87,.22);border:1px solid rgba(217,167,87,.5)}
  .pill.src{color:var(--muted);background:rgba(140,131,120,.16);border:1px solid var(--line)}
  body.dark .pill.pend{color:#f0c66a}
  .mode{margin-left:auto;font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;padding:2px 9px;border-radius:999px}
  .mode.auto{color:var(--ok);background:rgba(46,125,99,.14)}
  .mode.suggest{color:#8a5a12;background:rgba(217,167,87,.16)}
  body.dark .mode.suggest{color:#f0c66a}
  .mode.fixed{color:var(--muted);background:rgba(140,131,120,.16)}
  .banner{border-radius:var(--radius);padding:14px 17px;margin:14px 0;font-size:14px;font-weight:500;
    box-shadow:var(--shadow);backdrop-filter:var(--glass-blur);-webkit-backdrop-filter:var(--glass-blur);
    display:flex;gap:11px;align-items:flex-start;line-height:1.5}
  .banner .bi{font-size:18px;line-height:1.3}
  .banner.pending{background:rgba(46,125,99,.12);color:var(--ok)}
  body.dark .banner.pending{color:#7fd3b6}
  .banner.paused{background:rgba(185,126,30,.16);color:#8a5a12}
  body.dark .banner.paused{color:#f0c66a}
  .qcard{position:relative;overflow:hidden;background:var(--glass-strong);border:1px solid rgba(200,99,47,.4);
    border-radius:var(--radius);padding:18px 20px 18px 24px;box-shadow:var(--shadow-hi);margin-bottom:12px;
    backdrop-filter:var(--glass-blur);-webkit-backdrop-filter:var(--glass-blur)}
  .qcard::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--grad)}
  .qkicker{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--orange);margin-bottom:7px;display:flex;align-items:center;gap:7px}
  .qtext{font-size:18px;font-weight:700;line-height:1.4;letter-spacing:-.2px}
  .answer{margin-top:15px}
  .chips{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px}
  .chip{font:inherit;font-size:13px;font-weight:600;cursor:pointer;color:var(--ink);background:var(--glass);
    border:1px solid var(--line);border-radius:999px;padding:8px 15px;
    backdrop-filter:var(--glass-blur);-webkit-backdrop-filter:var(--glass-blur);
    transition:transform .15s ease, border-color .2s ease, color .2s ease, background .25s ease, box-shadow .3s ease}
  .chip:hover{transform:translateY(-2px);border-color:rgba(200,99,47,.5)}
  .chip.sel{color:#fff;background:var(--grad);border-color:transparent;box-shadow:0 8px 20px -8px rgba(200,99,47,.65)}
  .answer-row{display:flex;gap:9px}
  #ans{flex:1;min-width:0;font:inherit;font-size:14.5px;color:var(--ink);background:var(--glass-strong);
    border:1px solid var(--line);border-radius:12px;padding:11px 14px;outline:none;
    backdrop-filter:var(--glass-blur);-webkit-backdrop-filter:var(--glass-blur);
    transition:border-color .2s ease, box-shadow .25s ease}
  #ans::placeholder{color:var(--faint)}
  #ans:focus{border-color:rgba(200,99,47,.55);box-shadow:0 0 0 4px rgba(200,99,47,.15)}
  .save{font:inherit;font-size:14px;font-weight:700;cursor:pointer;color:#fff;border:none;background:var(--grad);
    border-radius:12px;padding:0 19px;white-space:nowrap;box-shadow:0 9px 24px -8px rgba(200,99,47,.7);
    transition:transform .15s ease, box-shadow .3s ease, opacity .2s ease}
  .save:hover:not(:disabled){transform:translateY(-2px)}
  .save:disabled{opacity:.45;cursor:default}
  .skip{margin-top:11px;display:flex;gap:14px;align-items:center}
  .linkbtn{background:none;border:none;color:var(--muted);font:inherit;font-size:12.5px;cursor:pointer;text-decoration:underline;text-underline-offset:3px;padding:0}
  .linkbtn:hover{color:var(--ink)}
  .qnote{font-size:12px;color:var(--faint)}
  .surface{display:flex;align-items:center;gap:14px}
  .surface-body{flex:1;min-width:0}
  .surface-label{font-weight:600;font-size:14.5px}
  .surface-path{color:var(--muted);font-size:11.5px;margin-top:3px;font-family:"JetBrains Mono",ui-monospace,Consolas,monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .surface-state{text-align:right;white-space:nowrap}
  .state-label{font-weight:700;font-size:13px}
  .state-time{color:var(--muted);font-size:11.5px;margin-top:2px}
  .dot{width:11px;height:11px;border-radius:50%;flex:none;position:relative}
  .dot.ok{background:var(--ok);box-shadow:0 0 0 4px rgba(46,125,99,.14)}
  .dot.warn{background:var(--amber);box-shadow:0 0 0 4px rgba(185,126,30,.14)}
  .dot.idle{background:var(--faint);box-shadow:0 0 0 4px rgba(140,131,120,.12)}
  .dot.ok::after{content:"";position:absolute;inset:0;border-radius:50%;background:var(--ok);animation:pulse 2s ease-out infinite}
  @keyframes pulse{0%{transform:scale(1);opacity:.7}100%{transform:scale(2.6);opacity:0}}
  .hookbar{display:flex;align-items:center;gap:13px;font-weight:500}
  .digest{background:var(--glass-strong);border-radius:var(--radius);padding:17px 19px;white-space:pre-wrap;
    font-size:13.5px;line-height:1.7;font-family:"JetBrains Mono",ui-monospace,Consolas,monospace;color:var(--ink);
    overflow-x:auto;box-shadow:var(--shadow);backdrop-filter:var(--glass-blur);-webkit-backdrop-filter:var(--glass-blur)}
  body.dark .digest{color:#d8cfc2}
  .empty{text-align:center;color:var(--muted)}
  .empty code{display:inline-block;margin-top:8px;background:var(--glass);padding:6px 12px;border-radius:8px;color:var(--ink)}
  footer{color:var(--muted);font-size:12.5px;text-align:center;margin-top:40px}
  footer code{background:var(--glass);padding:2px 8px;border-radius:6px}
  .toast{position:fixed;left:50%;bottom:26px;transform:translateX(-50%) translateY(20px);z-index:5;
    background:var(--glass-strong);color:var(--ink);font-weight:600;font-size:14px;padding:12px 18px;border-radius:14px;
    box-shadow:var(--shadow-hi);backdrop-filter:var(--glass-blur);-webkit-backdrop-filter:var(--glass-blur);
    opacity:0;pointer-events:none;transition:opacity .3s ease, transform .3s ease}
  .toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
  .reveal{opacity:0;transform:translateY(16px)}
  .reveal.in{opacity:1;transform:none;transition:opacity .6s ease, transform .6s cubic-bezier(.2,.8,.3,1)}
  @media(prefers-reduced-motion:reduce){.aurora{animation:none}.reveal{opacity:1;transform:none}.dot.ok::after{animation:none}.progress .bar{transition:none}}
"""

_JS = """
  var SUN='<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4.2"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.4 1.4M17.6 17.6L19 19M19 5l-1.4 1.4M6.4 17.6L5 19"/></svg>';
  var MOON='<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z"/></svg>';
  function applyTheme(t){var d=t==='dark';document.body.classList.toggle('dark',d);
    var i=document.getElementById('themeIc'),x=document.getElementById('themeTxt');
    if(i)i.innerHTML=d?SUN:MOON; if(x)x.textContent=d?'Light':'Dark';}
  function toggleTheme(){var t=document.body.classList.contains('dark')?'light':'dark';
    try{localStorage.setItem('compass-theme',t);}catch(e){}applyTheme(t);}
  (function(){var t='light';try{t=localStorage.getItem('compass-theme')||'light';}catch(e){}applyTheme(t);
    var b=document.getElementById('themeToggle'); if(b)b.addEventListener('click',toggleTheme);})();
  function toast(msg){var t=document.getElementById('toast');if(!t)return;t.textContent=msg;t.classList.add('show');setTimeout(function(){t.classList.remove('show');},2600);}
  var reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
  function countUp(el){var tgt=+el.dataset.count,suf=el.dataset.suffix||'',d=1100,s=performance.now();
    function f(now){var p=Math.min((now-s)/d,1);var e=1-Math.pow(1-p,3);el.textContent=Math.round(tgt*e)+suf;if(p<1)requestAnimationFrame(f);}requestAnimationFrame(f);}
  window.addEventListener('load',function(){
    document.querySelectorAll('.bar').forEach(function(b){setTimeout(function(){b.style.width=b.dataset.pct+'%';},250);});
    if(reduce){document.querySelectorAll('[data-count]').forEach(function(el){el.textContent=el.dataset.count+(el.dataset.suffix||'');});
      document.querySelectorAll('.reveal').forEach(function(el){el.classList.add('in');});}
    else{var io=new IntersectionObserver(function(es){es.forEach(function(en){if(en.isIntersecting){en.target.classList.add('in');
      en.target.querySelectorAll('[data-count]').forEach(countUp);io.unobserve(en.target);}});},{threshold:.15});
      var i=0;document.querySelectorAll('.reveal').forEach(function(el){el.style.transitionDelay=(i++*40)+'ms';io.observe(el);});}
    wireAnswer();
  });
  function wireAnswer(){
    var ans=document.getElementById('ans'), save=document.getElementById('saveBtn'),
        chips=document.querySelectorAll('.chip'), skip=document.getElementById('skipBtn'),
        card=document.getElementById('qcard'); if(!card||!ans||!save)return;
    var qid=card.dataset.qid, live=(location.protocol==='http:'||location.protocol==='https:');
    function refresh(){save.disabled=ans.value.trim().length===0;}
    chips.forEach(function(c){c.addEventListener('click',function(){chips.forEach(function(x){x.classList.remove('sel');});
      c.classList.add('sel');ans.value=c.dataset.v;refresh();ans.focus();});});
    ans.addEventListener('input',function(){chips.forEach(function(x){if(x.dataset.v!==ans.value)x.classList.remove('sel');});refresh();});
    ans.addEventListener('keydown',function(e){if(e.key==='Enter'&&!save.disabled)save.click();});
    save.addEventListener('click',function(){var text=ans.value.trim();if(!text)return;save.disabled=true;
      if(live){fetch('answer',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:qid,text:text})})
        .then(function(r){if(!r.ok)throw 0;toast('Saved \\u2713  synced to your sessions');setTimeout(function(){location.reload();},900);})
        .catch(function(){save.disabled=false;toast('Could not save \\u2014 is the dashboard still running?');});}
      else{var cmd='compass answer '+qid+' "'+text.replace(/"/g,'\\\\"')+'"';
        try{navigator.clipboard.writeText(cmd);toast('Copied the command \\u2014 paste it in your terminal');}
        catch(e){toast(cmd);} save.disabled=false;}});
    if(skip)skip.addEventListener('click',function(){if(live){fetch('skip',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:qid})})
      .then(function(){location.reload();}).catch(function(){});}else{card.style.opacity='.45';skip.textContent='Skipped';}});
  }
"""


def _fmt_time(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%a %d %b, %I:%M %p").lstrip("0")
    except (ValueError, TypeError):
        return iso or "—"


def _surface_state(current_fp: str, entry) -> "tuple[str, str]":
    if not entry:
        return "idle", "Never synced"
    status = entry.get("status", "")
    if status in ("tampered", "conflict"):
        return "warn", "Needs your eyes"
    if entry.get("profile_hash") == "(paused)":
        return "idle", "Paused (removed)"
    if entry.get("profile_hash") == current_fp:
        return "ok", "In sync"
    return "warn", "Out of date"


def _answer_card(next_q, esc) -> str:
    if not next_q:
        return ""
    chips = ""
    for opt in (getattr(next_q, "options", None) or [])[:4]:
        if not opt or not opt.strip():
            continue
        chips += f'<button class="chip" data-v="{esc(opt)}">{esc(opt)}</button>'
    chips_html = f'<div class="chips">{chips}</div>' if chips else ""
    return f"""
  <h2 class="reveal">Next calibration</h2>
  <div class="qcard reveal" id="qcard" data-qid="{esc(next_q.id)}">
    <div class="qkicker"><span>&#9737;</span> One thoughtful question</div>
    <div class="qtext">{esc(next_q.text)}</div>
    <div class="answer">
      {chips_html}
      <div class="answer-row">
        <input id="ans" type="text" placeholder="&hellip;or write your own answer" autocomplete="off" aria-label="Your answer">
        <button class="save" id="saveBtn" disabled>Save answer</button>
      </div>
      <div class="skip"><button class="linkbtn" id="skipBtn">Skip for now</button>
        <span class="qnote">Saved here updates every Claude session automatically.</span></div>
    </div>
  </div>"""


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

    n_total_q = len(DEFAULT_QUESTIONS)
    n_answered = min(qb.answered_count(), n_total_q)
    calib_pct = round(n_answered / n_total_q * 100) if n_total_q else 0
    n_surf = len(surfaces)
    n_insync = sum(1 for s in surfaces
                   if _surface_state(current_fp, manifest.get(s.key))[0] == "ok")

    sp = settings_path(claude_code_home())
    hook_on = sp.exists() and HOOK_TAG in sp.read_text(encoding="utf-8", errors="ignore")
    now = datetime.now(timezone.utc).astimezone().strftime("%a %d %b %Y, %I:%M %p").lstrip("0")

    # profile facets grouped by category
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
                tags = ""
                if not f.approved:
                    tags += '<span class="pill pend">pending review</span>'
                elif f.source != "you":
                    tags += f'<span class="pill src">{esc(f.source)}</span>'
                mode = getattr(f, "mode", "") or ""
                if mode in ("auto", "suggest", "fixed") and f.approved:
                    tags += f'<span class="mode {mode}">{mode}</span>'
                rows.append(f'<div class="facet"><span class="txt">{esc(f.text)}</span>{tags}</div>')
            groups.append(f'<div class="card reveal"><div class="catname"><span class="d"></span>'
                          f'{esc(label)}</div>{"".join(rows)}</div>')
        facets_html = "".join(groups)
    else:
        facets_html = ('<div class="card reveal empty"><p>Your profile is empty.</p>'
                       '<code>compass ask</code></div>')

    # surfaces
    if surfaces:
        rows = []
        for surf in surfaces:
            cls, label = _surface_state(current_fp, manifest.get(surf.key))
            last = _fmt_time(manifest.get(surf.key, {}).get("last_sync", ""))
            colour = {"ok": "var(--ok)", "warn": "var(--amber)", "idle": "var(--faint)"}[cls]
            rows.append(f'<div class="card surface reveal"><span class="dot {cls}"></span>'
                        f'<div class="surface-body"><div class="surface-label">{esc(surf.label)}</div>'
                        f'<div class="surface-path">{esc(str(surf.path))}</div></div>'
                        f'<div class="surface-state"><div class="state-label" style="color:{colour}">'
                        f'{esc(label)}</div><div class="state-time">{esc(last)}</div></div></div>')
        surfaces_html = "".join(rows)
    else:
        surfaces_html = ('<div class="card reveal empty"><p>No Claude memory surfaces found.</p>'
                         f'<div class="surface-path">Looked in: {esc(str(claude_code_home()))}</div></div>')

    paused_banner = ('<div class="banner paused reveal"><span class="bi">&#9208;</span>'
                     '<div><b>PAUSED</b> — Compass is not influencing your sessions. '
                     'Run <code>compass resume</code> to turn it back on.</div></div>') if paused else ""

    pending_banner = ""
    if pending and not paused:
        pending_banner = (f'<div class="banner pending reveal"><span class="bi">&#9737;</span>'
                          f'<div><b>{len(pending)} note(s) inferred from your history are waiting for '
                          'your review.</b> They are not shared with any session until you approve '
                          'them — run <code>compass approve --all</code>.</div></div>')

    hook_cls = "ok" if hook_on else "idle"
    hook_text = ("On — every session refreshes automatically" if hook_on
                 else "Off — turn on with: compass install-hook")
    answer_html = _answer_card(next_q, esc) if not paused else ""

    activity = "\n".join(reversed(events)) if events else \
        "No activity yet — answer a question or run a sync and it'll appear here."
    pending_lbl = (", " + str(len(pending)) + " pending") if pending else ""

    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Claude Compass</title>'
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">'
        f'<style>{_CSS}</style></head><body>'
        '<div class="aurora" aria-hidden="true"></div>'
        '<div class="wrap">'
        '<header class="reveal">'
        f'<span class="logo">{_claude_logo_svg(28)}</span>'
        '<div><h1>Claude Compass</h1>'
        '<div class="sub">Every Claude session, attuned to how you like to work.</div></div>'
        '<button class="toggle" id="themeToggle" aria-label="Toggle light and dark theme">'
        '<span class="ic" id="themeIc"></span><span id="themeTxt">Dark</span></button>'
        '</header>'
        '<div class="stats reveal">'
        f'<div class="stat"><div class="num" data-count="{len(approved)}">0</div><div class="lbl">live notes</div></div>'
        f'<div class="stat"><div class="num" data-count="{len(pending)}">0</div><div class="lbl">pending</div></div>'
        f'<div class="stat"><div class="num" data-count="{calib_pct}" data-suffix="%">0</div><div class="lbl">calibrated</div></div>'
        f'<div class="stat"><div class="num">{n_insync}/{n_surf}</div><div class="lbl">in sync</div></div>'
        f'<div class="stat"><div class="num">{"On" if hook_on else "Off"}</div><div class="lbl">auto-sync</div></div>'
        '</div>'
        f'<div class="progress" title="Calibration"><div class="bar" data-pct="{calib_pct}"></div></div>'
        f'<div class="progress-cap">Calibration &middot; {n_answered} of {n_total_q} questions answered</div>'
        f'{paused_banner}{pending_banner}'
        f'<h2 class="reveal">Your profile &middot; {len(approved)} live{pending_lbl}</h2>'
        f'{facets_html}'
        f'{answer_html}'
        '<h2 class="reveal">Claude memory surfaces</h2>'
        f'{surfaces_html}'
        '<h2 class="reveal">Auto-sync</h2>'
        f'<div class="card hookbar reveal"><span class="dot {hook_cls}"></span><div>{esc(hook_text)}</div></div>'
        '<h2 class="reveal">What every session is reading</h2>'
        f'<div class="digest reveal">{esc(profile_text)}</div>'
        '<h2 class="reveal">Recent activity</h2>'
        f'<div class="digest reveal">{esc(activity)}</div>'
        f'<footer class="reveal">Snapshot taken {esc(now)} &middot; re-run <code>compass dashboard</code> to refresh</footer>'
        '</div><div class="toast" id="toast"></div>'
        f'<script>{_JS}</script></body></html>'
    )


def write_dashboard(store: Store) -> Path:
    store.home.mkdir(parents=True, exist_ok=True)
    out = store.home / "dashboard.html"
    out.write_text(render_dashboard_html(store), encoding="utf-8")
    return out
