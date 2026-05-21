"""app.py — the double-click Claude Compass window.

Thin paint over the tested :mod:`appmodel`. Qt is imported lazily inside
``main()`` so importing this module never requires PySide6 (the shipped .exe
bundles it). If PySide6 is missing, ``main()`` explains how to get it.
"""

from __future__ import annotations

import sys
import webbrowser

from .appmodel import (
    answer_question, approve, approve_all, build_snapshot, do_sync, forget,
    set_paused,
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


def main() -> int:
    try:
        from PySide6.QtWidgets import (
            QApplication, QCheckBox, QFrame, QHBoxLayout, QInputDialog, QLabel,
            QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget,
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
            self._build()
            self.refresh()

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
            qrow = QHBoxLayout()
            self._answer_edit = QLineEdit()
            self._answer_edit.setPlaceholderText("Answer the question above...")
            ans_btn = QPushButton("Save answer")
            ans_btn.clicked.connect(self._answer)
            qrow.addWidget(self._answer_edit, 1)
            qrow.addWidget(ans_btn)
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
            if snap.next_question_text:
                self._q_id = snap.next_question_id
                self._q_lbl.setText("Q: " + snap.next_question_text)
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
        def _answer(self):
            text = self._answer_edit.text().strip()
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
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
