"""QSS stylesheets and color tokens for the usage monitor.

Service color schemes on a frosted-glass base:
  - ZCODE  → blue + white
  - Claude → orange + white
  - Codex  → black + white
  - TRAE   → deep green + white

Progress bars show REMAINING usage (the unfilled portion), so a full bar means
plenty of quota left and a near-empty bar means almost used up. No red warning
color is used.
"""

from __future__ import annotations

# --- Service color tokens -----------------------------------------------------
# (primary, primary_light, border, card_bg, text colors)
SERVICE_COLORS = {
    "Zcode": {
        "primary": "#3b7dd8",
        "primary_light": "#6ba3e8",
        "border": "rgba(59, 125, 216, 0.25)",
        "card_bg": "rgba(240, 246, 253, 0.45)",
        "text_on_primary": "#ffffff",
        "text_dark": "#1a3658",
    },
    "Claude": {
        "primary": "#d97757",
        "primary_light": "#e8a07f",
        "border": "rgba(217, 119, 87, 0.25)",
        "card_bg": "rgba(253, 245, 240, 0.45)",
        "text_dark": "#6b3416",
    },
    "Codex": {
        "primary": "#1a1a1a",
        "primary_light": "#4a4a4a",
        "border": "rgba(26, 26, 26, 0.20)",
        "card_bg": "rgba(250, 250, 250, 0.45)",
        "text_dark": "#1a1a1a",
    },
    "Trae": {
        "primary": "#2e7d4f",
        "primary_light": "#4ea870",
        "border": "rgba(46, 125, 79, 0.25)",
        "card_bg": "rgba(237, 247, 240, 0.45)",
        "text_dark": "#1a4a2e",
    },
}

CARD_RADIUS = 12


def card_qss(service: str) -> str:
    """Return the QSS for a service card frame, keyed by service name."""
    c = SERVICE_COLORS[service]
    return f"""
        QFrame#card {{
            background-color: {c["card_bg"]};
            border: 1px solid {c["border"]};
            border-radius: {CARD_RADIUS}px;
        }}
        QLabel#serviceName {{
            color: {c["text_dark"]};
            font-size: 16px;
            font-weight: bold;
        }}
        QLabel#modelLabel {{
            color: rgba(0, 0, 0, 0.50);
            font-size: 12px;
        }}
        QLabel#planLabel {{
            color: {c["primary"]};
            font-size: 11px;
            font-weight: bold;
        }}
        QLabel#windowLabel {{
            color: rgba(0, 0, 0, 0.45);
            font-size: 11px;
            font-weight: bold;
        }}
        QLabel#detailLabel {{
            color: rgba(0, 0, 0, 0.55);
            font-size: 11px;
        }}
        QLabel#errorLabel {{
            color: #e84545;
            font-size: 11px;
        }}
        QLabel#freePlanLabel {{
            color: #e84545;
            font-size: 13px;
            font-style: italic;
            font-weight: bold;
        }}
    """


def progress_chunk_qss(service: str, remaining_pct: float) -> str:
    """QSS for one progress bar.

    ``remaining_pct`` is the REMAINING percentage (0-100). The filled chunk
    represents remaining quota in the service color. No warning color is used.
    """
    c = SERVICE_COLORS[service]
    fill = c["primary"]
    # Codex uses a dark bar, so its text needs to be light for legibility.
    text_color = "#f5ebd6" if service == "Codex" else "rgba(0,0,0,0.6)"
    return f"""
        QProgressBar {{
            background-color: rgba(0, 0, 0, 0.08);
            border: none;
            border-radius: 5px;
            color: {text_color};
            font-size: 11px;
            font-weight: bold;
            min-height: 18px;
            max-height: 18px;
        }}
        QProgressBar::chunk {{
            background-color: {fill};
            border-radius: 5px;
        }}
    """


WINDOW_QSS = """
    QLabel#title {
        color: rgba(0, 0, 0, 0.78);
        font-size: 16px;
        font-weight: bold;
    }
    QLabel#countdown {
        color: rgba(0, 0, 0, 0.50);
        font-size: 16px;
        font-weight: bold;
    }
    QLabel#countdown[pulse="true"] {
        color: #8b3df0;
    }
    QMenu {
        background-color: rgba(255, 255, 255, 0.95);
        border: 1px solid rgba(0, 0, 0, 0.15);
        border-radius: 6px;
        padding: 4px;
        color: #222;
        font-size: 13px;
    }
    QMenu::item {
        padding: 6px 26px;
        border-radius: 4px;
    }
    QMenu::item:selected {
        background-color: rgba(59, 125, 216, 0.15);
    }
    QMenu::separator {
        height: 1px;
        background: rgba(0, 0, 0, 0.08);
        margin: 4px 8px;
    }
"""
