"""A single service usage card: name + model + two progress bars + details."""

from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from providers.base import UsageData
from ui import styles


def _format_tokens(n: int) -> str:
    """123456 -> '123K', 1500000 -> '1.5M'."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def _format_reset(dt: datetime | None) -> str:
    """Format a reset time as HH:MM (today) or weekday."""
    if dt is None:
        return "--"
    local = dt.astimezone()
    now = datetime.now().astimezone()
    if local.date() == now.date():
        return local.strftime("reset %H:%M")
    delta_days = (local.date() - now.date()).days
    if delta_days == 1:
        return local.strftime("reset tomorrow")
    if 0 < delta_days <= 7:
        return local.strftime("reset %a")
    return local.strftime("reset %m/%d")


class ServiceCard(QFrame):
    """Renders one service's usage with a 5h and 7d progress bar."""

    def __init__(self, service: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._service = service
        self.setObjectName("card")
        self.setStyleSheet(styles.card_qss(service))
        self._build()
        self._apply_data(UsageData(service=service, available=False, error="Loading..."))

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(7)

        # --- Header: service name + model + plan ---
        header = QHBoxLayout()
        header.setSpacing(7)
        self.name_label = QLabel(self._service)
        self.name_label.setObjectName("serviceName")
        self.model_label = QLabel("")
        self.model_label.setObjectName("modelLabel")
        self.plan_label = QLabel("")
        self.plan_label.setObjectName("planLabel")
        header.addWidget(self.name_label)
        header.addWidget(self.model_label, 1)
        header.addWidget(self.plan_label)
        layout.addLayout(header)

        # --- 5-hour window ---
        self._bar_5h, self._detail_5h = self._make_window_row("5h", layout)
        # --- 7-day window ---
        self._bar_7d, self._detail_7d = self._make_window_row("7d", layout)

        # --- Error / status line ---
        self.error_label = QLabel("")
        self.error_label.setObjectName("errorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

    def _make_window_row(self, label: str, parent_layout: QVBoxLayout):
        row = QVBoxLayout()
        row.setSpacing(3)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        win_label = QLabel(label)
        win_label.setObjectName("windowLabel")
        win_label.setFixedWidth(24)
        bar = QProgressBar()
        bar.setTextVisible(True)
        bar.setRange(0, 1000)  # use 0..1000 for smoother rounding
        bar.setValue(0)
        bar.setFormat("")
        top.addWidget(win_label)
        top.addWidget(bar, 1)
        row.addLayout(top)

        detail = QLabel("")
        detail.setObjectName("detailLabel")
        detail.setContentsMargins(30, 0, 0, 0)
        row.addWidget(detail)

        parent_layout.addLayout(row)
        return bar, detail

    # ------------------------------------------------------------------
    def update_data(self, data: UsageData) -> None:
        self._apply_data(data)

    def _apply_data(self, data: UsageData) -> None:
        self.model_label.setText(data.model)
        self.plan_label.setText(data.plan_type.upper() if data.plan_type else "")

        if not data.available:
            self.error_label.setText(data.error or "No data")
            self.error_label.setVisible(True)
            self._set_bar(self._bar_5h, 0.0, "")
            self._set_bar(self._bar_7d, 0.0, "")
            self._detail_5h.setText("")
            self._detail_7d.setText("")
            return

        self.error_label.setVisible(False)

        # --- 5h window ---
        w5 = data.window_5h
        self._set_bar(self._bar_5h, w5.percent, "")
        self._detail_5h.setText(self._detail_text(w5))

        # --- 7d window ---
        w7 = data.window_7d
        self._set_bar(self._bar_7d, w7.percent, "")
        self._detail_7d.setText(self._detail_text(w7))

    def _detail_text(self, w) -> str:
        if w.is_real_limit:
            remaining = max(0.0, 100.0 - w.percent)
            return f"{remaining:.0f}% remaining · {_format_reset(w.reset_at)}"
        return (
            f"{_format_tokens(w.used)} / {_format_tokens(w.budget)} tokens"
            f"  ·  {_format_reset(w.reset_at)}"
        )

    def _set_bar(self, bar: QProgressBar, used_pct: float, fmt: str) -> None:
        """Set the progress bar to show REMAINING usage.

        ``used_pct`` is the percentage already consumed; the bar fills with the
        complement (remaining) so a full bar = plenty of quota left. The text on
        the bar shows the remaining percentage.
        """
        used_pct = max(0.0, min(100.0, used_pct))
        remaining = 100.0 - used_pct
        bar.setValue(int(round(remaining * 10)))  # scale to 0..1000
        if fmt:
            bar.setFormat(fmt)
        else:
            bar.setFormat(f"{remaining:.0f}% left")
        bar.setStyleSheet(styles.progress_chunk_qss(self._service, remaining))
        bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
