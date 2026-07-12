"""Frameless, translucent, always-on-top main window for the usage monitor.

Features:
  - Frameless + translucent (frosted-glass) + always-on-top
  - Draggable anywhere on the widget; position saved to config
  - 5-minute auto refresh with a live MM:SS countdown
  - Right-click context menu: budgets, opacity, refresh now, quit
"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QPoint, QTimer, Qt
from PySide6.QtGui import QAction, QColor, QMouseEvent, QPainter, QPainterPath, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from providers.base import BaseProvider
from providers.claude import ClaudeProvider
from providers.codex import CodexProvider
from providers.zcode import ZCodeProvider
from ui import styles
from ui.usage_card import ServiceCard

REFRESH_INTERVAL_SEC = 5 * 60  # 5 minutes
COUNTDOWN_TICK_MS = 1000
PULSE_THRESHOLD = 5  # last N seconds: countdown pulses


class FrostedFrame(QFrame):
    """A nearly-transparent rounded frame that paints its own frosted background.

    On Windows, QSS ``background-color`` on a frameless window renders as an
    opaque rectangle regardless of alpha. By overriding ``paintEvent`` and
    drawing a rounded rect with a very low-alpha fill + a subtle border, we get
    a true see-through frosted-glass panel.
    """

    def __init__(self, radius: int = 16, parent=None):
        super().__init__(parent)
        self._radius = radius
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setAutoFillBackground(False)
        # Transparent so our paintEvent is the only source of background.
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0, 0))
        self.setPalette(pal)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(float(rect.x()), float(rect.y()),
                            float(rect.width()), float(rect.height()),
                            float(self._radius), float(self._radius))
        # Only draw the outline — no fill, fully transparent background.
        painter.setPen(QColor(255, 255, 255, 90))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)


def _config_path() -> Path:
    return Path(__file__).resolve().parent.parent / "config.json"


def load_config() -> dict:
    p = _config_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_config(cfg: dict) -> None:
    try:
        _config_path().write_text(
            json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass


class MainWindow(QMainWindow):
    def __init__(self, config: dict):
        super().__init__()
        self._config = config
        self._seconds_to_refresh = REFRESH_INTERVAL_SEC
        self._drag_offset: QPoint | None = None

        # Per-service budget config.
        budgets = self._config.get("budgets", {})

        self._providers: list[tuple[str, BaseProvider, ServiceCard]] = []
        for name, provider_cls in [
            ("ZCODE", ZCodeProvider),
            ("Claude", ClaudeProvider),
            ("Codex", CodexProvider),
        ]:
            b = budgets.get(name, {})
            provider = provider_cls(
                budget_5h=b.get("5h"),
                budget_7d=b.get("7d"),
            )
            card = ServiceCard(name)
            self._providers.append((name, provider, card))

        self._setup_window()
        self._setup_timers()
        self.refresh_now()

    # ------------------------------------------------------------------ window
    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        opacity = self._config.get("opacity", 0.92)
        self.setWindowOpacity(float(opacity))

        root = FrostedFrame(radius=16)
        root.setStyleSheet(styles.WINDOW_QSS)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 14, 18, 16)
        layout.setSpacing(10)

        # Title (centered on its own line).
        title = QLabel("Use Every Token Wisely")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Countdown on its own line, centered, below the title.
        self.countdown_label = QLabel("↻ --:--")
        self.countdown_label.setObjectName("countdown")
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.countdown_label)

        # Service cards.
        for _name, _provider, card in self._providers:
            layout.addWidget(card)

        container = QWidget()
        cl = QVBoxLayout(container)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.addWidget(root)
        self.setCentralWidget(container)

        self.setFixedSize(360, 0)  # width fixed; height auto from layout
        self.adjustSize()

        # Restore position.
        pos = self._config.get("position")
        if isinstance(pos, list) and len(pos) == 2:
            self.move(int(pos[0]), int(pos[1]))

    # ------------------------------------------------------------------ timers
    def _setup_timers(self) -> None:
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._on_refresh_tick)
        self._refresh_timer.start(COUNTDOWN_TICK_MS)

        self._countdown_timer = QTimer(self)
        self._countdown_timer.timeout.connect(self._on_refresh_tick)
        self._countdown_timer.start(COUNTDOWN_TICK_MS)

    def _on_refresh_tick(self) -> None:
        self._seconds_to_refresh -= 1
        if self._seconds_to_refresh <= 0:
            self.refresh_now()
        else:
            self._update_countdown_label()

    def _update_countdown_label(self) -> None:
        m, s = divmod(self._seconds_to_refresh, 60)
        self.countdown_label.setText(f"↻ {m:02d}:{s:02d}")
        # Pulse in the last 5 seconds: toggle a red property for styling +
        # nudge the label horizontally for a subtle shake.
        if self._seconds_to_refresh <= PULSE_THRESHOLD:
            self.countdown_label.setProperty("pulse", True)
            # alternate offset every tick for a gentle shake
            offset = 2 if (self._seconds_to_refresh % 2 == 0) else -2
            self.countdown_label.setContentsMargins(10 + offset, 0, 10 - offset, 0)
        else:
            self.countdown_label.setProperty("pulse", False)
            self.countdown_label.setContentsMargins(10, 0, 10, 0)
        # Refresh stylesheet to apply the pulse property selector.
        self.countdown_label.setStyleSheet(
            self.countdown_label.styleSheet()
        )
        self.countdown_label.style().unpolish(self.countdown_label)
        self.countdown_label.style().polish(self.countdown_label)

    # ------------------------------------------------------------------ refresh
    def refresh_now(self) -> None:
        self._seconds_to_refresh = REFRESH_INTERVAL_SEC
        self.countdown_label.setText("↻ refreshing...")
        QApplication.processEvents()
        for _name, provider, card in self._providers:
            try:
                data = provider.fetch()
            except Exception as exc:  # noqa: BLE001 — keep widget alive
                from providers.base import UsageData  # noqa: F404

                data = UsageData(
                    service=_name, available=False, error=f"Error: {exc}"
                )
            card.update_data(data)
        self._update_countdown_label()

    # ------------------------------------------------------------------ drag
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None:
            self._drag_offset = None
            self._config["position"] = [self.x(), self.y()]
            save_config(self._config)
            event.accept()

    # ------------------------------------------------------------------ menu
    def contextMenuEvent(self, event) -> None:  # type: ignore[override]
        menu = QMenu(self)
        menu.setStyleSheet(styles.WINDOW_QSS)

        refresh_action = QAction("↻ Refresh now", menu)
        refresh_action.triggered.connect(self.refresh_now)
        menu.addAction(refresh_action)

        menu.addSeparator()

        opacity_menu = QMenu("Opacity", menu)
        for pct in (70, 80, 90, 100):
            act = QAction(f"{pct}%", opacity_menu)
            act.triggered.connect(lambda checked=False, p=pct: self._set_opacity(p / 100))
            opacity_menu.addAction(act)
        menu.addMenu(opacity_menu)

        budget_menu = QMenu("Set budgets...", menu)
        for name in ("ZCODE", "Claude", "Codex"):
            act = QAction(f"{name}...", budget_menu)
            act.triggered.connect(lambda checked=False, n=name: self._edit_budget(n))
            budget_menu.addAction(act)
        menu.addMenu(budget_menu)

        menu.addSeparator()

        about_action = QAction("ⓘ About", menu)
        about_action.triggered.connect(self._show_about)
        menu.addAction(about_action)

        quit_action = QAction("✕ Quit", menu)
        quit_action.triggered.connect(self.close)
        menu.addAction(quit_action)

        menu.exec(event.globalPos())

    def _show_about(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        msg = QMessageBox(self)
        msg.setWindowTitle("About")
        msg.setText(
            "<h3>Use Every Token Wisely</h3>"
            "<p>AI usage monitor for ZCODE · Claude · Codex</p>"
            "<p>Open source under MIT License</p>"
        )
        msg.setStyleSheet(styles.WINDOW_QSS)
        msg.exec()

    def _set_opacity(self, value: float) -> None:
        self.setWindowOpacity(value)
        self._config["opacity"] = value
        save_config(self._config)

    def _edit_budget(self, service: str) -> None:
        from PySide6.QtWidgets import QInputDialog

        cur = self._config.setdefault("budgets", {}).get(service, {})
        cur_5h = cur.get("5h", 0)
        text, ok = QInputDialog.getText(
            self,
            f"{service} budget",
            f"5-hour budget (tokens).\nCurrent: {cur_5h}\n"
            "(Note: Codex uses real rate limits; this only affects Claude/ZCODE)",
            text=str(cur_5h),
        )
        if ok and text.strip().isdigit():
            budgets = self._config.setdefault("budgets", {})
            svc = budgets.setdefault(service, {})
            svc["5h"] = int(text.strip())
            save_config(self._config)
            self.reload_providers()

    def reload_providers(self) -> None:
        budgets = self._config.get("budgets", {})
        new_providers: list[tuple[str, BaseProvider, ServiceCard]] = []
        for name, provider, card in self._providers:
            b = budgets.get(name, {})
            provider.budget_5h = b.get("5h", provider.budget_5h)
            provider.budget_7d = b.get("7d", provider.budget_7d)
            new_providers.append((name, provider, card))
        self._providers = new_providers
        self.refresh_now()

    # ------------------------------------------------------------------ close
    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._config["position"] = [self.x(), self.y()]
        save_config(self._config)
        super().closeEvent(event)
