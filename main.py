"""Entry point for the AI usage monitor desktop widget.

Usage:
    python main.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QLockFile
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow, load_config


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("AI Usage Monitor")
    app.setQuitOnLastWindowClosed(True)

    # Single-instance guard: exit quietly if another copy is already running.
    # QLockFile records PID/hostname and auto-recovers from stale locks left
    # by crashes. Keep the reference alive for the app's whole lifetime.
    lock = QLockFile(str(Path(__file__).resolve().parent / ".instance.lock"))
    if not lock.tryLock(100):
        return 0

    config = load_config()
    window = MainWindow(config)
    window.show()
    # Refit after show() so all child widgets have real geometry.
    from PySide6.QtCore import QTimer
    QTimer.singleShot(50, window._refit)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
