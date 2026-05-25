"""app.py — the double-click Claude Compass window.

Thin paint over the tested :mod:`appmodel`. Qt is imported lazily inside
``main()`` so importing this module never requires PySide6 (the shipped .exe
bundles it). If PySide6 is missing, ``main()`` explains how to get it.
"""

from __future__ import annotations

import sys
import webbrowser

from .appmodel import (
    answer_question, approve, approve_all, build_snapshot, do_sync, edit, forget,
    quickstart, set_paused,
)
from . import startup
from .dashboard import _claude_logo_svg, write_dashboard
from .store import Store, default_home

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

_STATE_COLOUR = {"in_sync": _OK, "out_of_date": _WARN, "never": _IDLE,
                 "attention": _ERR, "paused": _IDLE}

# --- the fleet's elevated-brew look, tuned for Qt (no real blur, so glass is
# evoked with a warm palette, soft rounded cards, gradient accents, and a bold
# accent question card) — with a sleek dark mode. -----------------------------
_LIGHT = {
    "bg": "#F4EFE6", "ink": "#1C1712", "muted": "#5F564B", "card": "#FCF7EF",
    "line": "#E4DBCC", "orange": "#C8632F", "orange2": "#E0875C", "warn": "#9A6A12",
    "ok": "#2E7D63", "qcardbg": "#FBF1E9", "accentline": "#EAC3AC", "btn": "#FBF6EE",
    "btnhover": "#FFFFFF", "field": "#FFFCF8", "scroll": "#D9CFBE",
    "pend_bg": "#F7E8CC", "pend_fg": "#8A5A12", "src_bg": "#EDE6DB", "src_fg": "#5F564B",
    "ok_bg": "#DCEFE7", "shadow_a": 46,
}
_DARK = {
    "bg": "#17120E", "ink": "#F7F1E7", "muted": "#B7AEA2", "card": "#271F18",
    "line": "#3A322A", "orange": "#E0875C", "orange2": "#EE9E75", "warn": "#E7B45E",
    "ok": "#4FB592", "qcardbg": "#2E2018", "accentline": "#7A4F36", "btn": "#241D16",
    "btnhover": "#312820", "field": "#201913", "scroll": "#43392F",
    "pend_bg": "#3A2F1C", "pend_fg": "#E7B45E", "src_bg": "#2E2820", "src_fg": "#B7AEA2",
    "ok_bg": "#1E3A30", "shadow_a": 150,
}


def _qss(dark: bool) -> str:
    c = _DARK if dark else _LIGHT
    grad = (f"qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {c['orange2']}, "
            f"stop:1 {c['orange']})")
    return f"""
QWidget {{ background: {c['bg']}; color: {c['ink']};
  font-family: 'Segoe UI', -apple-system, Roboto, Arial; font-size: 13px; }}
QLabel#title {{ font-size: 22px; font-weight: 700; color: {c['ink']}; }}
QLabel#sub {{ color: {c['muted']}; font-size: 12px; }}
QLabel#section {{ color: {c['muted']}; font-size: 11px; font-weight: 700; }}
QLabel#kicker {{ color: {c['orange']}; font-size: 10px; font-weight: 700; }}
QLabel#question {{ font-size: 16px; font-weight: 700; color: {c['ink']}; }}
QLabel#paused {{ color: {c['warn']}; font-weight: 700; }}
QFrame#card {{ background: transparent; border: 1px solid {c['line']}; border-radius: 14px; }}
QFrame#qcard {{ background: {c['qcardbg']}; border: 1px solid {c['accentline']};
  border-radius: 16px; }}
QFrame#statchip {{ background: transparent; border: 1px solid {c['accentline']};
  border-radius: 12px; }}
QLabel#statnum {{ color: {c['orange']}; font-size: 20px; font-weight: 700; }}
QLabel#statlbl {{ color: {c['muted']}; font-size: 10px; font-weight: 700; }}
QFrame#tick {{ background: {c['orange']}; border: none; border-radius: 1px; }}
QLabel#pillpend {{ color: {c['pend_fg']}; background: {c['pend_bg']}; border-radius: 8px;
  padding: 2px 9px; font-size: 11px; font-weight: 700; }}
QLabel#pillsrc {{ color: {c['src_fg']}; background: {c['src_bg']}; border-radius: 8px;
  padding: 2px 9px; font-size: 11px; font-weight: 700; }}
QLabel#modeauto {{ color: {c['ok']}; background: {c['ok_bg']}; border-radius: 8px;
  padding: 2px 9px; font-size: 10px; font-weight: 700; }}
QLabel#modesuggest {{ color: {c['pend_fg']}; background: {c['pend_bg']}; border-radius: 8px;
  padding: 2px 9px; font-size: 10px; font-weight: 700; }}
QLabel#modefixed {{ color: {c['src_fg']}; background: {c['src_bg']}; border-radius: 8px;
  padding: 2px 9px; font-size: 10px; font-weight: 700; }}
QProgressBar {{ background: {c['line']}; border: none; border-radius: 4px;
  max-height: 8px; min-height: 8px; }}
QProgressBar::chunk {{ border-radius: 4px;
  background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {c['orange2']}, stop:1 {c['orange']}); }}
QPushButton {{ background: {c['btn']}; border: 1px solid {c['line']}; border-radius: 10px;
  padding: 7px 14px; color: {c['ink']}; }}
QPushButton:hover {{ background: {c['btnhover']}; border-color: {c['orange']}; }}
QPushButton#primary {{ background: {grad}; color: white; border: none; font-weight: 700;
  padding: 8px 16px; }}
QPushButton#primary:hover {{ background: {c['orange']}; }}
QPushButton#small {{ padding: 3px 10px; border-radius: 8px; }}
QPushButton#pill {{ background: {c['btn']}; border: 1px solid {c['line']}; border-radius: 999px;
  padding: 6px 14px; color: {c['ink']}; }}
QPushButton#pill:hover {{ border-color: {c['orange']}; }}
QPushButton#pill:checked {{ background: {grad}; color: white; border: none; }}
QPushButton#toggle {{ background: {c['btn']}; border: 1px solid {c['line']}; border-radius: 10px;
  padding: 7px 14px; color: {c['muted']}; font-weight: 600; }}
QPushButton#toggle:hover {{ color: {c['ink']}; border-color: {c['orange']};
  background: {c['btnhover']}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {c['scroll']}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {c['muted']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QLineEdit {{ background: {c['field']}; border: 1px solid {c['line']}; border-radius: 10px;
  padding: 8px 10px; color: {c['ink']}; }}
QLineEdit:focus {{ border-color: {c['orange']}; }}
"""


def _missing_pyside_message() -> str:
    return (
        "Claude Compass's window needs PySide6.\n\n"
        "Install it with:\n    pip install --user PySide6\n\n"
        "Or use the command line instead:\n"
        "    python -m claude_compass dashboard\n"
    )


def _compass_tray_svg(size=64):
    """A clean compass glyph in Claude's orange. The tray icon uses this (rather
    than the Claude logo) so Compass is easy to tell apart from the other fleet
    tools at a glance — they'd otherwise all show the same asterisk. The Claude
    logo stays the brand mark in the window header and the README."""
    o = _ORANGE
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><title>Compass</title>'
        f'<circle cx="12" cy="12" r="10" fill="none" stroke="{o}" stroke-width="1.7"/>'
        f'<polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88" fill="{o}"/>'
        f'</svg>'
    )


def _make_tray_icon():
    """Build the tray QIcon from the compass glyph (rendered SVG), with a dot
    fallback if SVG rendering isn't available."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon, QPainter, QPixmap
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    try:
        from PySide6.QtCore import QByteArray
        from PySide6.QtSvg import QSvgRenderer
        r = QSvgRenderer(QByteArray(_compass_tray_svg(64).encode("utf-8")))
        p = QPainter(pm)
        r.render(p)
        p.end()
    except Exception:
        from PySide6.QtGui import QColor
        p = QPainter(pm)
        p.setBrush(QColor(_ORANGE))
        p.setPen(Qt.NoPen)
        p.drawEllipse(8, 8, 48, 48)
        p.end()
    return QIcon(pm)


def main(start_in_tray: bool = False) -> int:
    try:
        from PySide6.QtWidgets import (
            QApplication, QCheckBox, QFrame, QHBoxLayout, QInputDialog, QLabel,
            QLineEdit, QMenu, QPushButton, QScrollArea, QSystemTrayIcon,
            QVBoxLayout, QWidget,
        )
    except ImportError:
        sys.stderr.write(_missing_pyside_message())
        return 1
    try:
        from PySide6.QtSvgWidgets import QSvgWidget
        _have_svg = True
    except ImportError:
        _have_svg = False

    store = Store(default_home())
    store.init()

    class CompassWindow(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Claude Compass")
            self.setMinimumSize(720, 700)
            self.resize(760, 760)
            from PySide6.QtCore import QSettings
            self._settings = QSettings("Jack", "ClaudeCompass")
            self._dark = self._settings.value("dark", False, type=bool)
            self.setStyleSheet(_qss(self._dark))
            self._tray = None      # set by main() if a system tray is available
            self._build()
            self.refresh()

        def closeEvent(self, event):
            # Closing the window hides to the tray (keeps Compass alive in the
            # background); the tray's Quit really exits.
            if self._tray is not None and self._tray.isVisible():
                event.ignore()
                self.hide()
                try:
                    self._tray.showMessage(
                        "Claude Compass",
                        "Still here in your tray - right-click the icon for options.")
                except Exception:
                    pass
            else:
                event.accept()

        def _build(self):
            from PySide6.QtCore import Qt
            root = QVBoxLayout(self)
            root.setContentsMargins(22, 20, 22, 18)
            root.setSpacing(12)

            header = QHBoxLayout()
            if _have_svg:
                logo = QSvgWidget()
                logo.load(_claude_logo_svg(30).encode("utf-8"))
                logo.setFixedSize(30, 30)
                header.addWidget(logo)
            titles = QVBoxLayout(); titles.setSpacing(0)
            t = QLabel("Claude Compass"); t.setObjectName("title")
            sub = QLabel("Every Claude session, attuned to how you like to work.")
            sub.setObjectName("sub")
            titles.addWidget(t); titles.addWidget(sub)
            header.addLayout(titles); header.addStretch(1)
            self._paused_lbl = QLabel(""); self._paused_lbl.setObjectName("paused")
            header.addWidget(self._paused_lbl)
            self._theme_btn = QPushButton("Light" if self._dark else "Dark")
            self._theme_btn.setObjectName("toggle")
            self._theme_btn.setCursor(Qt.PointingHandCursor)
            self._theme_btn.clicked.connect(self._toggle_theme)
            header.addWidget(self._theme_btn)
            root.addLayout(header)

            # At-a-glance stats + a slim calibration bar (mirrors the dashboard).
            from PySide6.QtWidgets import QProgressBar
            self._stat_lbls = {}
            stats = QHBoxLayout(); stats.setSpacing(10)
            for key, cap in (("live", "LIVE NOTES"), ("pending", "PENDING"),
                             ("calib", "CALIBRATED"), ("insync", "IN SYNC")):
                chip = QFrame(); chip.setObjectName("statchip")
                cl = QVBoxLayout(chip); cl.setContentsMargins(10, 8, 10, 8); cl.setSpacing(1)
                num = QLabel("—"); num.setObjectName("statnum"); num.setAlignment(Qt.AlignHCenter)
                cap_l = QLabel(cap); cap_l.setObjectName("statlbl"); cap_l.setAlignment(Qt.AlignHCenter)
                cl.addWidget(num); cl.addWidget(cap_l)
                self._stat_lbls[key] = num
                stats.addWidget(chip)
            root.addLayout(stats)
            self._progress = QProgressBar()
            self._progress.setRange(0, 100); self._progress.setValue(0)
            self._progress.setTextVisible(False)
            root.addWidget(self._progress)

            # The next calibration question, in a bold accent card — answer it
            # right here: pick a chip or type your own.
            self._qcard = QFrame(); self._qcard.setObjectName("qcard")
            qlay = QVBoxLayout(self._qcard)
            qlay.setContentsMargins(18, 14, 18, 16); qlay.setSpacing(9)
            kick = QLabel("NEXT CALIBRATION"); kick.setObjectName("kicker")
            qlay.addWidget(kick)
            self._q_lbl = QLabel(""); self._q_lbl.setObjectName("question")
            self._q_lbl.setWordWrap(True)
            qlay.addWidget(self._q_lbl)
            # Clickable answer pills (rebuilt each refresh for the current question).
            self._pills_holder = QWidget()
            self._pills_layout = QHBoxLayout(self._pills_holder)
            self._pills_layout.setContentsMargins(0, 0, 0, 0)
            self._pills_layout.setSpacing(6)
            self._pill_buttons = []
            self._q_multi = False
            qlay.addWidget(self._pills_holder)
            qrow = QHBoxLayout()
            self._answer_edit = QLineEdit()
            self._answer_edit.setPlaceholderText("…or type your own answer")
            self._answer_edit.returnPressed.connect(self._answer)
            ans_btn = QPushButton("Save answer"); ans_btn.setObjectName("primary")
            ans_btn.clicked.connect(self._answer)
            qrow.addWidget(self._answer_edit, 1)
            qrow.addWidget(ans_btn)
            qs_btn = QPushButton("Use recommended")
            qs_btn.clicked.connect(self._quickstart)
            qrow.addWidget(qs_btn)
            qlay.addLayout(qrow)
            root.addWidget(self._qcard)
            self._apply_shadow(self._qcard, blur=30, dy=9)

            self._body = QVBoxLayout(); self._body.setSpacing(8)
            container = QWidget(); container.setLayout(self._body)
            scroll = QScrollArea(); scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            scroll.setWidget(container)
            root.addWidget(scroll, 1)

            self._status = QLabel(""); self._status.setObjectName("sub")
            root.addWidget(self._status)

            actions = QHBoxLayout()
            self._pause_btn = QPushButton("Pause")
            self._pause_btn.clicked.connect(self._toggle_pause)
            dash_btn = QPushButton("Open dashboard")
            dash_btn.clicked.connect(self._open_dashboard)
            sync_btn = QPushButton("Sync now"); sync_btn.setObjectName("primary")
            sync_btn.clicked.connect(self._sync)
            actions.addWidget(self._pause_btn)
            actions.addStretch(1)
            actions.addWidget(dash_btn)
            actions.addWidget(sync_btn)
            root.addLayout(actions)

        def _clear_body(self):
            while self._body.count():
                item = self._body.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()

        def _apply_shadow(self, w, blur=24, dy=6):
            try:
                from PySide6.QtGui import QColor
                from PySide6.QtWidgets import QGraphicsDropShadowEffect
                eff = QGraphicsDropShadowEffect(self)
                eff.setBlurRadius(blur); eff.setXOffset(0); eff.setYOffset(dy)
                a = (_DARK if self._dark else _LIGHT)["shadow_a"]
                eff.setColor(QColor(0, 0, 0, a))
                w.setGraphicsEffect(eff)
            except Exception:
                pass

        def _section(self, text):
            from PySide6.QtCore import Qt
            from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget
            row = QWidget()
            h = QHBoxLayout(row); h.setContentsMargins(2, 8, 0, 0); h.setSpacing(8)
            tick = QFrame(); tick.setObjectName("tick"); tick.setFixedSize(14, 3)
            lbl = QLabel(text); lbl.setObjectName("section")
            h.addWidget(tick, 0, Qt.AlignVCenter); h.addWidget(lbl); h.addStretch(1)
            self._body.addWidget(row)

        def refresh(self):
            from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel,
                                           QPushButton, QVBoxLayout, QWidget)
            snap = build_snapshot(store)
            self._clear_body()

            self._paused_lbl.setText("PAUSED" if snap.paused else "")

            # Update the at-a-glance stats + calibration bar.
            from .questions import DEFAULT_QUESTIONS, QuestionBank
            n_live = sum(1 for x in snap.facets if x.approved)
            n_pend = sum(1 for x in snap.facets if not x.approved)
            n_insync = sum(1 for sv in snap.surfaces if sv.state == "in_sync")
            total_q = len(DEFAULT_QUESTIONS)
            answered = min(QuestionBank(store).answered_count(), total_q)
            pct = round(answered / total_q * 100) if total_q else 0
            self._stat_lbls["live"].setText(str(n_live))
            self._stat_lbls["pending"].setText(str(n_pend))
            self._stat_lbls["calib"].setText(f"{pct}%")
            self._stat_lbls["insync"].setText(f"{n_insync}/{len(snap.surfaces)}")
            self._progress.setValue(pct)

            # Rebuild the answer pills for the current question.
            while self._pills_layout.count():
                it = self._pills_layout.takeAt(0)
                w = it.widget()
                if w:
                    w.deleteLater()
            self._pill_buttons = []
            self._q_multi = snap.next_question_multi
            if snap.next_question_text:
                self._q_id = snap.next_question_id
                self._qcard.setVisible(True)
                self._q_lbl.setText(snap.next_question_text)
                for opt in snap.next_question_options:
                    b = QPushButton(opt); b.setObjectName("pill")
                    if snap.next_question_multi:
                        b.setCheckable(True)
                    else:
                        b.clicked.connect(lambda _=False, o=opt: self._pick(o))
                    self._pill_buttons.append(b)
                    self._pills_layout.addWidget(b)
                self._pills_layout.addStretch(1)
            else:
                self._q_id = None
                self._qcard.setVisible(False)

            # Surfaces
            self._section("CLAUDE MEMORY SURFACES")
            if snap.surfaces:
                for sv in snap.surfaces:
                    f = QFrame(); f.setObjectName("card")
                    lay = QHBoxLayout(f); lay.setContentsMargins(14, 8, 14, 8)
                    dot = QLabel("●")
                    dot.setStyleSheet(f"color:{_STATE_COLOUR.get(sv.state, _IDLE)};")
                    lay.addWidget(dot)
                    lay.addWidget(QLabel(sv.label), 1)
                    st = QLabel(sv.detail)
                    st.setStyleSheet(f"color:{_STATE_COLOUR.get(sv.state, _IDLE)};")
                    lay.addWidget(st)
                    self._body.addWidget(f)
            else:
                self._body.addWidget(QLabel("  No Claude memory surfaces found yet."))

            # Profile facets
            live = sum(1 for x in snap.facets if x.approved)
            pend = sum(1 for x in snap.facets if not x.approved)
            self._section(f"YOUR PROFILE - {live} live"
                          + (f", {pend} pending review" if pend else ""))
            if not snap.facets:
                self._body.addWidget(QLabel("  Empty — answer a question to begin."))
            for fv in snap.facets:
                f = QFrame(); f.setObjectName("card")
                lay = QHBoxLayout(f); lay.setContentsMargins(14, 8, 14, 8); lay.setSpacing(8)
                label = QLabel(fv.text); label.setWordWrap(True)
                lay.addWidget(label, 1)
                if not fv.approved:
                    p = QLabel("pending review"); p.setObjectName("pillpend"); lay.addWidget(p)
                elif fv.source != "you":
                    p = QLabel(fv.source); p.setObjectName("pillsrc"); lay.addWidget(p)
                mode = (getattr(fv, "mode", "") or "")
                if fv.approved and mode in ("auto", "suggest", "fixed"):
                    m = QLabel(mode); m.setObjectName("mode" + mode); lay.addWidget(m)
                if not fv.approved:
                    appr = QPushButton("Approve"); appr.setObjectName("small")
                    appr.clicked.connect(lambda _=False, i=fv.index: self._approve(i))
                    lay.addWidget(appr)
                edb = QPushButton("Edit"); edb.setObjectName("small")
                edb.clicked.connect(lambda _=False, i=fv.index, t=fv.text: self._edit(i, t))
                lay.addWidget(edb)
                rm = QPushButton("Forget"); rm.setObjectName("small")
                rm.clicked.connect(lambda _=False, i=fv.index: self._forget(i))
                lay.addWidget(rm)
                self._body.addWidget(f)

            # Recent activity
            self._section("RECENT ACTIVITY")
            if snap.recent:
                f = QFrame(); f.setObjectName("card")
                lay = QVBoxLayout(f); lay.setContentsMargins(14, 8, 14, 8); lay.setSpacing(1)
                for line in reversed(snap.recent):
                    r = QLabel(line)
                    r.setStyleSheet(f"color:{_MUTED}; font-family:Consolas,monospace; font-size:11px;")
                    lay.addWidget(r)
                self._body.addWidget(f)
            else:
                self._body.addWidget(QLabel("  No syncs yet."))

            self._body.addStretch(1)
            self._pause_btn.setText("Resume" if snap.paused else "Pause")

        # -- actions -- #
        def _toggle_theme(self):
            self._dark = not self._dark
            try:
                self._settings.setValue("dark", self._dark)
            except Exception:
                pass
            self.setStyleSheet(_qss(self._dark))
            self._theme_btn.setText("Light" if self._dark else "Dark")

        def _quickstart(self):
            n = quickstart(store)
            self._status.setText(f"  Filled {n} recommended defaults — tweak any below.")
            self.refresh()

        def _pick(self, option):
            # Single-select pill: clicking answers immediately.
            if self._q_id:
                answer_question(store, self._q_id, option)
                self._answer_edit.clear()
                do_sync(store)
                self._status.setText("  Saved and synced. ")
                self.refresh()

        def _answer(self):
            # Save button: commits checked multi-select pills + any typed text.
            parts = [b.text() for b in self._pill_buttons
                     if b.isCheckable() and b.isChecked()]
            typed = self._answer_edit.text().strip()
            if typed:
                parts.append(typed)
            text = ", ".join(parts)
            if self._q_id and text:
                answer_question(store, self._q_id, text)
                self._answer_edit.clear()
                do_sync(store)
                self._status.setText("  Saved and synced. ")
                self.refresh()

        def _approve(self, index):
            approve(store, index)
            do_sync(store)
            self._status.setText("  Approved and synced.")
            self.refresh()

        def _edit(self, index, current):
            from PySide6.QtWidgets import QInputDialog
            new, ok = QInputDialog.getText(self, "Edit note",
                                           "Update this note:", text=current)
            if ok and new.strip():
                edit(store, index, new.strip())   # edits + re-syncs
                self._status.setText("  Updated and synced.")
                self.refresh()

        def _forget(self, index):
            forget(store, index)   # removes + re-syncs (gone everywhere)
            self._status.setText("  Removed - and gone from your sessions too.")
            self.refresh()

        def _toggle_pause(self):
            now_paused = self._pause_btn.text() == "Resume"
            set_paused(store, not now_paused)
            self._status.setText("  Resumed." if now_paused else "  Paused - pulled out of your sessions.")
            self.refresh()

        def _sync(self):
            reports = do_sync(store)
            changed = sum(1 for r in reports if r.result.changed)
            self._status.setText(f"  Synced {changed} surface(s)." if changed
                                 else "  Already up to date.")
            self.refresh()

        def _open_dashboard(self):
            out = write_dashboard(store)
            try:
                webbrowser.open(out.as_uri())
            except Exception:
                pass
            self._status.setText(f"  Dashboard: {out}")

    app = QApplication.instance() or QApplication(sys.argv)

    # Single-instance guard: if Compass is already running, don't open a second
    # window — just bow out quietly. (So a second double-click does nothing.)
    try:
        from PySide6.QtCore import QSharedMemory
        _lock = QSharedMemory("ClaudeCompassSingleInstance")
        if not _lock.create(1):
            return 0
        app._compass_lock = _lock   # keep it alive for the process lifetime
    except Exception:
        pass

    win = CompassWindow()

    if QSystemTrayIcon.isSystemTrayAvailable():
        from PySide6.QtGui import QAction
        app.setQuitOnLastWindowClosed(False)   # closing the window hides to tray

        def _show():
            win.showNormal(); win.raise_(); win.activateWindow()

        tray = QSystemTrayIcon(_make_tray_icon())
        tray.setToolTip("Claude Compass")
        menu = QMenu()
        a_open = QAction("Open Compass", menu); a_open.triggered.connect(_show)
        a_sync = QAction("Sync now", menu); a_sync.triggered.connect(win._sync)
        a_dash = QAction("Open dashboard", menu); a_dash.triggered.connect(win._open_dashboard)
        a_pause = QAction("Pause", menu); a_pause.triggered.connect(win._toggle_pause)
        a_quit = QAction("Quit", menu); a_quit.triggered.connect(app.quit)
        for a in (a_open, a_sync, a_dash, a_pause):
            menu.addAction(a)

        # Start with Windows (per-user, no admin). Only meaningful for the
        # packaged .exe, so it's greyed out when running from source.
        a_startup = QAction("Run at startup", menu)
        a_startup.setCheckable(True)
        a_startup.setChecked(startup.is_enabled())
        a_startup.setEnabled(startup.is_frozen())

        def _toggle_startup(checked: bool) -> None:
            ok = startup.enable() if checked else startup.disable()
            if not ok:                       # registry wrote nothing — reflect reality
                a_startup.setChecked(startup.is_enabled())
        a_startup.toggled.connect(_toggle_startup)
        menu.addAction(a_startup)

        menu.addSeparator(); menu.addAction(a_quit)

        # Show "Resume" when paused, "Pause" when running — refreshed each open.
        def _refresh_pause_label():
            a_pause.setText("Resume" if store.is_paused() else "Pause")
        menu.aboutToShow.connect(_refresh_pause_label)
        _refresh_pause_label()

        tray.setContextMenu(menu)
        tray.activated.connect(
            lambda reason: _show() if reason == QSystemTrayIcon.DoubleClick else None)
        tray.show()
        win._tray = tray
        if not start_in_tray:
            win.show()
    else:
        win.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

# Fleet UI: elevated Claude-brew + dark mode (shared design system).
