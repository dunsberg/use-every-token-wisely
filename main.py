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

    config = load_config()
    window = MainWindow(config)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
