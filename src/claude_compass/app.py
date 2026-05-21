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

_QSS = f"""
QWidget {{ background: {_CREAM}; color: {_INK};
  font-family: 'Segoe UI', -apple-system, Roboto, Arial; font-size: 13px; }}
QLabel#title {{ font-size: 20px; font-weight: 600; }}
QLabel#sub {{ color: {_MUTED}; font-size: 12px; }}
QLabel#section {{ color: {_MUTED}; font-size: 11px; font-weight: 600; }}
QLabel#paused {{ color: #6b4e12; font-weight: 600; }}
QFrame#card {{ background: {_CARD}; border: 1px solid {_LINE}; border-radius: 12px; }}
QPushButton {{ background: {_CARD}; border: 1px solid {_LINE}; border-radius: 9px;
  padding: 7px 14px; }}
QPushButton:hover {{ background: #fff; }}
QPushButton#primary {{ background: {_ORANGE}; color: white; border: none; font-weight: 600; }}
QPushButton#primary:hover {{ background: #c8633f; }}
QPushButton#small {{ padding: 3px 10px; }}
QPushButton#pill {{ background: #fff; border: 1px solid {_LINE}; border-radius: 999px;
  padding: 5px 13px; }}
QPushButton#pill:hover {{ border-color: {_ORANGE}; }}
QPushButton#pill:checked {{ background: {_ORANGE}; color: white; border: none; }}
QScrollArea {{ border: none; }}
QLineEdit {{ background: #fff; border: 1px solid {_LINE}; border-radius: 8px; padding: 6px; }}
"""


def _missing_pyside_message() -> str:
    return (
        "Claude Compass's window needs PySide6.\n\n"
        "Install it with:\n    pip install --user PySide6\n\n"
        "Or use the command line instead:\n"
        "    python -m claude_compass dashboard\n"
    )


def _make_tray_icon():
    """Build a QIcon from the Claude logo (rendered SVG), with a dot fallback."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon, QPainter, QPixmap
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    try:
        from PySide6.QtCore import QByteArray
        from PySide6.QtSvg import QSvgRenderer
        r = QSvgRenderer(QByteArray(_claude_logo_svg(64).encode("utf-8")))
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
            self.setMinimumSize(580, 680)
            self.setStyleSheet(_QSS)
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
            root.addLayout(header)

            # Ask-a-question row
            self._q_lbl = QLabel(""); self._q_lbl.setObjectName("sub")
            self._q_lbl.setWordWrap(True)
            root.addWidget(self._q_lbl)
            # Clickable answer pills (rebuilt each refresh for the current question).
            self._pills_holder = QWidget()
            self._pills_layout = QHBoxLayout(self._pills_holder)
            self._pills_layout.setContentsMargins(0, 0, 0, 0)
            self._pills_layout.setSpacing(6)
            self._pill_buttons = []
            self._q_multi = False
            root.addWidget(self._pills_holder)
            qrow = QHBoxLayout()
            self._answer_edit = QLineEdit()
            self._answer_edit.setPlaceholderText("...or type your own answer")
            ans_btn = QPushButton("Save")
            ans_btn.clicked.connect(self._answer)
            qrow.addWidget(self._answer_edit, 1)
            qrow.addWidget(ans_btn)
            qs_btn = QPushButton("Use recommended answers")
            qs_btn.clicked.connect(self._quickstart)
            qrow.addWidget(qs_btn)
            root.addLayout(qrow)

            self._body = QVBoxLayout(); self._body.setSpacing(8)
            container = QWidget(); container.setLayout(self._body)
            scroll = QScrollArea(); scroll.setWidgetResizable(True)
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

        def _section(self, text):
            lbl = QLabel(text); lbl.setObjectName("section")
            self._body.addWidget(lbl)

        def refresh(self):
            from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel,
                                           QPushButton, QVBoxLayout, QWidget)
            snap = build_snapshot(store)
            self._clear_body()

            self._paused_lbl.setText("PAUSED" if snap.paused else "")
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
                self._q_lbl.setText("Q: " + snap.next_question_text)
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
                self._q_lbl.setText("No questions right now — your profile's looking great.")

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
                lay = QHBoxLayout(f); lay.setContentsMargins(14, 6, 14, 6)
                txt = fv.text
                if fv.source != "you":
                    txt += f"   ({fv.source})"
                label = QLabel(txt); label.setWordWrap(True)
                if not fv.approved:
                    label.setStyleSheet(f"color:{_WARN};")
                lay.addWidget(label, 1)
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
