"""Data models and base provider for the usage monitor."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class WindowStats:
    """One rate-limit / usage window (e.g. 5-hour or 7-day).

    For Codex, ``percent`` is the real rate-limit percentage reported by the
    platform and ``used`` / ``budget`` are derived from it (or empty when the
    platform only exposes the percentage). For Claude / ZCODE there is no real
    quota, so we compute ``used`` as total tokens in a rolling window and let
    ``budget`` come from the user's configured budget.
    """

    label: str  # "5h" or "7d"
    used: int = 0  # tokens consumed in this window
    budget: int = 0  # token budget (user-configured)
    percent: float = 0.0  # used / budget * 100, or real rate-limit %
    reset_at: datetime | None = None  # when the window resets
    is_real_limit: bool = False  # True if percent comes from the platform

    @property
    def over_threshold(self) -> bool:
        return self.percent >= 80.0


@dataclass
class UsageData:
    """Aggregated usage for a single service, consumed by the UI."""

    service: str  # "ZCODE" / "Claude" / "Codex"
    model: str = ""
    plan_type: str = ""  # e.g. "plus" for Codex
    window_5h: WindowStats = field(default_factory=lambda: WindowStats("5h"))
    window_7d: WindowStats = field(default_factory=lambda: WindowStats("7d"))
    available: bool = True  # False if no data could be read
    error: str = ""


def parse_iso_timestamp(raw: str) -> datetime | None:
    """Parse an ISO-8601 timestamp (possibly ending with ``Z``) to aware datetime."""
    if not raw:
        return None
    try:
        s = raw.strip()
        # Python's fromisoformat handles most cases; normalize trailing Z.
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


class BaseProvider(ABC):
    """Base class for service-specific usage providers."""

    #: Default token budgets used until the user overrides them in config.json.
    default_budget_5h: int = 200_000
    default_budget_7d: int = 2_000_000

    def __init__(self, budget_5h: int | None = None, budget_7d: int | None = None):
        self.budget_5h = budget_5h or self.default_budget_5h
        self.budget_7d = budget_7d or self.default_budget_7d

    @abstractmethod
    def fetch(self) -> UsageData:
        """Read local data and return aggregated usage."""
        ...
