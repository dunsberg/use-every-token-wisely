"""Frameless, translucent, always-on-top main window for the usage monitor.

Features:
  - Frameless + translucent (frosted-glass) + always-on-top
  - Draggable anywhere on the widget; position saved to config
  - 5-minute auto refresh with a live MM:SS countdown
  - Right-click context menu: budgets, opacity, refresh now, quit
"""

from __future__ import annotations

import json
import os
import shutil
import sys
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
from providers.trae import TraeProvider
from providers.zcode import ZCodeProvider
from ui import styles
from ui.usage_card import ServiceCard

REFRESH_INTERVAL_SEC = 5 * 60  # 5 minutes
COUNTDOWN_TICK_MS = 1000
PULSE_THRESHOLD = 10  # last N seconds: countdown pulses


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


IS_MAC = sys.platform == "darwin"

# --- Autostart: cross-platform --------------------------------------------
_MAC_PLIST_NAME = "com.dunsberg.use-every-token-wisely.plist"


def _mac_launchagent_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / _MAC_PLIST_NAME


def _win_startup_lnk_path() -> Path:
    return Path(os.path.expandvars(
        r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
    )) / "Use Every Token Wisely.lnk"


def _desktop_lnk_path() -> Path:
    if IS_MAC:
        return Path.home() / "Desktop" / "Use Every Token Wisely.command"
    return Path.home() / "Desktop" / "Use Every Token Wisely.lnk"


def is_autostart_enabled() -> bool:
    if IS_MAC:
        return _mac_launchagent_path().exists()
    return _win_startup_lnk_path().exists()


def set_autostart(enabled: bool) -> None:
    """Enable/disable boot launch — cross-platform."""
    if IS_MAC:
        _set_autostart_mac(enabled)
    else:
        _set_autostart_windows(enabled)


def _set_autostart_mac(enabled: bool) -> None:
    plist_path = _mac_launchagent_path()
    if enabled:
        project_dir = Path(__file__).resolve().parent.parent
        main_py = project_dir / "main.py"
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.dunsberg.use-every-token-wisely</string>
    <key>ProgramArguments</key>
    <array>
        <string>{sys.executable}</string>
        <string>{main_py}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{project_dir}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/dev/null</string>
    <key>StandardErrorPath</key>
    <string>/dev/null</string>
</dict>
</plist>
"""
        plist_path.write_text(plist_content, encoding="utf-8")
    else:
        if plist_path.exists():
            plist_path.unlink()


def _set_autostart_windows(enabled: bool) -> None:
    startup = _win_startup_lnk_path()
    if enabled:
        desktop = _desktop_lnk_path()
        if desktop.exists():
            shutil.copy2(desktop, startup)
        else:
            try:
                project_dir = Path(__file__).resolve().parent.parent
                create_script = project_dir / "create_shortcut.py"
                import subprocess
                subprocess.run(
                    [sys.executable, str(create_script)],
                    capture_output=True, timeout=15,
                )
                if desktop.exists():
                    shutil.copy2(desktop, startup)
            except Exception:
                pass
    else:
        if startup.exists():
            startup.unlink()


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
            ("Zcode", ZCodeProvider),
            ("Claude", ClaudeProvider),
            ("Codex", CodexProvider),
            ("Trae", TraeProvider),
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
        # On macOS, frameless windows are opaque by default — we need
        # WA_TranslucentBackground so the FrostedFrame's rounded outline
        # is actually see-through. On Windows this causes rendering bugs.
        if IS_MAC:
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        root = FrostedFrame(radius=16)
        root.setStyleSheet(styles.WINDOW_QSS)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 14, 18, 16)
        layout.setSpacing(10)

        # Title (centered on its own line).
        title = QLabel("⚡Use Every Token Wisely⚡")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Countdown on its own line, centered, below the title.
        self.countdown_label = QLabel('<span style="color: rgba(0,0,0,0.50);">Refresh in: --:--</span>')
        self.countdown_label.setObjectName("countdown")
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.countdown_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self.countdown_label)

        # Service cards.
        for _name, _provider, card in self._providers:
            layout.addWidget(card)
            card.collapseChanged.connect(self._refit)

        container = QWidget()
        if IS_MAC:
            container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        cl = QVBoxLayout(container)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.addWidget(root)
        self.setCentralWidget(container)

        self._root = root
        self.setFixedWidth(360)  # width fixed; height refits on content change
        self._refit()

        # Restore position — clamp to available screen geometry to avoid
        # the widget landing off-screen on different display layouts.
        pos = self._config.get("position")
        if isinstance(pos, list) and len(pos) == 2:
            x, y = int(pos[0]), int(pos[1])
            screen = self.screen().availableGeometry()
            x = max(screen.left(), min(x, screen.right() - self.width()))
            y = max(screen.top(), min(y, screen.bottom() - self.height()))
            self.move(x, y)

    def _refit(self) -> None:
        """Recalculate the window height to match current content.

        Called on startup and whenever a card is collapsed/expanded, so the
        window shrinks/grows instead of leaving empty space.
        """
        self.adjustSize()
        # adjustSize on a QMainWindow can be unreliable with fixed width;
        # force the height from the central widget's size hint.
        sh = self.centralWidget().sizeHint()
        if sh.height() > 0:
            self.setFixedHeight(sh.height())

    # ------------------------------------------------------------------ timers
    def _setup_timers(self) -> None:
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._on_refresh_tick)
        self._refresh_timer.start(COUNTDOWN_TICK_MS)

    def _on_refresh_tick(self) -> None:
        self._seconds_to_refresh -= 1
        if self._seconds_to_refresh <= 0:
            self.refresh_now()
        else:
            self._update_countdown_label()

    def _update_countdown_label(self) -> None:
        m, s = divmod(self._seconds_to_refresh, 60)
        time_str = f"{m:02d}:{s:02d}"
        if self._seconds_to_refresh <= PULSE_THRESHOLD:
            # Only the number turns purple; "Refresh in:" stays normal.
            html = (
                f'<span style="color: rgba(0,0,0,0.50);">Refresh in: </span>'
                f'<span style="color: #8b3df0; font-weight: bold;">{time_str}</span>'
            )
            self.countdown_label.setText(html)
            # Gentle shake
            offset = 2 if (self._seconds_to_refresh % 2 == 0) else -2
            self.countdown_label.setContentsMargins(10 + offset, 0, 10 - offset, 0)
        else:
            html = (
                f'<span style="color: rgba(0,0,0,0.50);">Refresh in: </span>'
                f'<span style="color: rgba(0,0,0,0.50); font-weight: bold;">{time_str}</span>'
            )
            self.countdown_label.setText(html)
            self.countdown_label.setContentsMargins(10, 0, 10, 0)

    # ------------------------------------------------------------------ refresh
    def refresh_now(self) -> None:
        self._seconds_to_refresh = REFRESH_INTERVAL_SEC
        self.countdown_label.setText('<span style="color: rgba(0,0,0,0.50);">Refresh in: refreshing...</span>')
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

        # Agent visibility toggles — checkbox shows expanded (✓) vs collapsed.
        for name, _provider, card in self._providers:
            act = QAction(name, menu)
            act.setCheckable(True)
            act.setChecked(not card.is_collapsed)
            act.triggered.connect(
                lambda checked=False, c=card: c.set_collapsed(not c.is_collapsed)
            )
            menu.addAction(act)

        menu.addSeparator()

        # Boot launch toggle
        autostart_action = QAction("🚀 Launch on startup", menu)
        autostart_action.setCheckable(True)
        autostart_action.setChecked(is_autostart_enabled())
        autostart_action.triggered.connect(
            lambda checked=False: set_autostart(autostart_action.isChecked())
        )
        menu.addAction(autostart_action)

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
            "<h3 align='center'>⚡Use Every Token Wisely⚡</h3>"
            "<p align='center'>Real-time AI usage monitor for</p>"
            "<p align='center'><b>Zcode · Claude · Codex · Trae</b></p>"
            "<br>"
            "<p align='center'>github.com/dunsberg/use-every-token-wisely</p>"
            "<p align='center'><b>MIT License</b></p>"
        )
        msg.setStyleSheet(styles.WINDOW_QSS)
        msg.exec()

    # ------------------------------------------------------------------ close
    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._config["position"] = [self.x(), self.y()]
        save_config(self._config)
        super().closeEvent(event)
