"""Entry point for the AI usage monitor desktop widget.

Usage:
    python main.py
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow, load_config


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("AI Usage Monitor")
    app.setQuitOnLastWindowClosed(True)

    # Tooltips are top-level windows and don't inherit widget stylesheets —
    # without explicit colors they render as an unreadable black bar.
    app.setStyleSheet(
        "QToolTip { color: #ffffff; background-color: #2b2b2b;"
        " border: 1px solid #555555; padding: 4px 6px; }"
    )

    config = load_config()
    window = MainWindow(config)
    window.show()
    # Refit after show() so all child widgets have real geometry.
    from PySide6.QtCore import QTimer
    QTimer.singleShot(50, window._refit)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
