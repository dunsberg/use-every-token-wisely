"""A single service usage card: name + model + two progress bars + details."""

from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import Qt, QRect, Signal
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
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


class ChunkProgressBar(QProgressBar):
    """A progress bar that draws its percentage text right-aligned to the
    **chunk's** right edge (the filled portion), not the bar's right edge.

    Standard QProgressBar can only center text or align it to the whole bar.
    This subclass overrides paintEvent to position text at the chunk boundary.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextVisible(False)  # we draw text ourselves

    def paintEvent(self, event: QPaintEvent) -> None:
        # Let the base class draw the background + chunk.
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        text = self.format()
        if not text or text == "%p":
            text = f"{self.value() / 10:.0f}%"
        # The chunk occupies value/maximum of the bar width.
        ratio = self.value() / self.maximum() if self.maximum() > 0 else 0
        chunk_right = int(self.width() * ratio)
        # Draw text right-aligned to chunk_right, with a small right margin.
        margin = 4
        text_width = painter.fontMetrics().horizontalAdvance(text)
        x = chunk_right - text_width - margin
        # Clamp so text never goes off the left edge.
        x = max(2, x)
        # Vertical center.
        fm_height = painter.fontMetrics().height()
        y = (self.height() - fm_height) // 2 + painter.fontMetrics().ascent()
        # Choose text color based on whether it falls on the chunk or the gap.
        # If x is within the chunk area, use light text; otherwise dark.
        # When remaining ≤ 10%, text turns red to draw attention.
        if ratio <= 0.10:
            painter.setPen(QPen(QColor("#e84545")))
        elif x < chunk_right:
            painter.setPen(QPen(QColor("#ffffff")))
        else:
            painter.setPen(QPen(QColor("rgba(0,0,0,0.6)")))
        painter.drawText(x, y, text)


def _format_tokens(n: int) -> str:
    """123456 -> '123K', 1500000 -> '1.5M'."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def _format_reset(dt: datetime | None) -> str:
    """Format a reset time as HH:MM (today) or MM/DD (other days)."""
    if dt is None:
        return "--"
    local = dt.astimezone()
    now = datetime.now().astimezone()
    if local.date() == now.date():
        return local.strftime("reset %H:%M")
    delta_days = (local.date() - now.date()).days
    if delta_days == 1:
        return local.strftime("reset tomorrow %H:%M")
    return local.strftime("reset %m/%d")


class ServiceCard(QFrame):
    """Renders one service's usage with a 5h and 7d progress bar.

    Supports a collapsed state (toggled via the context menu) where only the
    header (service name + N/A) is shown, hiding the progress bars and details.
    """

    # Emitted whenever the collapse state changes, so the parent window can
    # resize itself to fit the new content height.
    collapseChanged = Signal()

    def __init__(self, service: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._service = service
        self._collapsed = False
        self.setObjectName("card")
        self.setStyleSheet(styles.card_qss(service))
        self._build()
        self._apply_data(UsageData(service=service, available=False, error="Loading..."))

    @property
    def is_collapsed(self) -> bool:
        return self._collapsed

    def set_collapsed(self, collapsed: bool) -> None:
        if self._collapsed == collapsed:
            return
        self._collapsed = collapsed
        # Show/hide everything except the header.
        self._body.setVisible(not collapsed)
        if collapsed:
            self.plan_label.setText("")
        else:
            # Restore on expand — will be re-applied by update_data.
            self.plan_label.setText(self._last_plan or "")
        self.collapseChanged.emit()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(7)

        # --- Header: service name + plan (always visible) ---
        header = QHBoxLayout()
        header.setSpacing(7)
        self.name_label = QLabel(self._service)
        self.name_label.setObjectName("serviceName")
        self.plan_label = QLabel("")
        self.plan_label.setObjectName("planLabel")
        header.addWidget(self.name_label)
        header.addStretch(1)
        header.addWidget(self.plan_label)
        layout.addLayout(header)

        # --- Body: progress bars + details (hidden when collapsed) ---
        self._body = QWidget()
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(7)

        # --- 5-hour window ---
        self._bar_5h, self._detail_5h = self._make_window_row("5h", body_layout)
        # --- 7-day window ---
        self._bar_7d, self._detail_7d = self._make_window_row("7d", body_layout)
        # --- Model-specific window (e.g. Fable 5) — hidden by default ---
        self._bar_model, self._detail_model = self._make_window_row("F5", body_layout)
        self._bar_model._row_widget.setVisible(False)
        # --- Extra dynamic windows (e.g. Codex) ---
        self._extra_bars: list = []
        self._extra_container = QWidget()
        self._extra_container.setVisible(False)
        extra_layout = QVBoxLayout(self._extra_container)
        extra_layout.setContentsMargins(0, 0, 0, 0)
        extra_layout.setSpacing(7)
        body_layout.addWidget(self._extra_container)

        # --- Free plan label (replaces bars when no quota) ---
        self.free_label = QLabel("Free Plan N/A")
        self.free_label.setObjectName("freePlanLabel")
        self.free_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.free_label.setVisible(False)
        body_layout.addWidget(self.free_label)

        # --- Credits balance (bottom of card) ---
        self.credits_label = QLabel("")
        self.credits_label.setObjectName("creditsLabel")
        self.credits_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.credits_label.setVisible(False)
        body_layout.addWidget(self.credits_label)

        # --- Error / status line ---
        self.error_label = QLabel("")
        self.error_label.setObjectName("errorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        body_layout.addWidget(self.error_label)

        layout.addWidget(self._body)
        self._last_model = ""
        self._last_plan = ""

    @property
    def is_free_plan(self) -> bool:
        return getattr(self, "_free_plan", False)

    def _make_window_row(self, label: str, parent_layout: QVBoxLayout):
        # Wrap each row in its own widget so we can hide it independently.
        row_widget = QWidget()
        row = QVBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(3)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        win_label = QLabel(label)
        win_label.setObjectName("windowLabel")
        win_label.setFixedWidth(24)
        bar = ChunkProgressBar()
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

        parent_layout.addWidget(row_widget)
        # Stash the row widget on the bar for easy access later.
        bar._row_widget = row_widget
        return bar, detail

    # ------------------------------------------------------------------
    def update_data(self, data: UsageData) -> None:
        self._apply_data(data)

    def _apply_data(self, data: UsageData) -> None:
        if not self._collapsed:
            self.plan_label.setText(data.plan_type.upper() if data.plan_type else "")
        self._last_plan = data.plan_type.upper() if data.plan_type else ""

        # --- Free plan / no quota: hide bars, show centered red italic label ---
        is_free = (
            not data.available
            and data.error
            and ("Free" in data.plan_type or "free" in (data.error or "").lower())
        )
        self._free_plan = is_free

        if is_free and not self._collapsed:
            self._bar_5h._row_widget.setVisible(False)
            self._bar_7d._row_widget.setVisible(False)
            self._bar_model._row_widget.setVisible(False)
            self._extra_container.setVisible(False)
            self.credits_label.setVisible(False)
            self.free_label.setVisible(True)
            self.error_label.setVisible(False)
            return

        # Normal mode: show bars, hide free label
        self.free_label.setVisible(False)

        if not data.available:
            self.error_label.setText(data.error or "No data")
            self.error_label.setVisible(True)
            self._bar_5h._row_widget.setVisible(False)
            self._bar_7d._row_widget.setVisible(False)
            self._bar_model._row_widget.setVisible(False)
            self._extra_container.setVisible(False)
            self.credits_label.setVisible(False)
            return

        self.error_label.setVisible(False)

        # --- 5h window (hide if no data for this window) ---
        w5 = data.window_5h
        if w5.reset_at is None and not w5.is_real_limit and w5.percent == 0:
            self._bar_5h._row_widget.setVisible(False)
        else:
            self._set_bar(self._bar_5h, w5.percent, "")
            self._detail_5h.setText(self._detail_text(w5))
            self._bar_5h._row_widget.setVisible(True)

        # --- 7d window (hide if no data for this window) ---
        w7 = data.window_7d
        if w7.reset_at is None and not w7.is_real_limit and w7.percent == 0:
            self._bar_7d._row_widget.setVisible(False)
        else:
            self._set_bar(self._bar_7d, w7.percent, "")
            self._detail_7d.setText(self._detail_text(w7))
            self._bar_7d._row_widget.setVisible(True)

        # --- Model-specific window (e.g. Fable 5) ---
        if data.window_model is not None:
            wm = data.window_model
            self._set_bar(self._bar_model, wm.percent, "")
            self._detail_model.setText(self._detail_text(wm))
            self._bar_model._row_widget.setVisible(True)
        else:
            self._bar_model._row_widget.setVisible(False)

        # --- Extra dynamic windows (e.g. Codex) ---
        self._render_extra_windows(data.extra_windows)

        # --- Credits balance ---
        if data.credits:
            self.credits_label.setText(f"Credits: {data.credits}")
            self.credits_label.setVisible(True)
        else:
            self.credits_label.setVisible(False)

    def _render_extra_windows(self, windows: list) -> None:
        """Dynamically create/show/hide progress bar rows for extra windows."""
        layout = self._extra_container.layout()
        # Remove old rows
        for bar, _detail in self._extra_bars:
            bar._row_widget.setParent(None)
            bar._row_widget.deleteLater()
        self._extra_bars.clear()

        if not windows:
            self._extra_container.setVisible(False)
            return

        for ws in windows:
            bar, detail = self._make_window_row(ws.label, layout)
            self._set_bar(bar, ws.percent, "")
            detail.setText(self._detail_text(ws))
            self._extra_bars.append((bar, detail))

        self._extra_container.setVisible(True)

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
        complement (remaining) so a full bar = plenty of quota left. The text
        is drawn by ChunkProgressBar right-aligned to the chunk's right edge.
        """
        used_pct = max(0.0, min(100.0, used_pct))
        remaining = 100.0 - used_pct
        bar.setValue(int(round(remaining * 10)))  # scale to 0..1000
        if fmt:
            bar.setFormat(fmt)
        else:
            bar.setFormat(f"{remaining:.0f}%")
        bar.setStyleSheet(styles.progress_chunk_qss(self._service, remaining))
