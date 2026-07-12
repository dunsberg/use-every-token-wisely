"""ZCODE usage provider — reads the real BigModel quota from the same API
ZCODE itself uses.

ZCODE does not persist its 5h / 7d rate-limit percentages to disk; it fetches them
live from the BigModel monitor API on every UI refresh. We replicate that call
using the API key already stored in ``~/.zcode/v2/config.json``, so the widget
stays fully automatic — no manual key entry.

Endpoint: ``GET {baseHost}/api/monitor/usage/quota/limit``
  - baseHost is derived from the provider baseURL (e.g. ``open.bigmodel.cn``)
  - Authorization header = the coding-plan apiKey (sent as-is, no "Bearer" prefix)

Response ``data.limits[]`` contains several windows. The two relevant ones are:
  - ``TOKENS_LIMIT`` with ``unit == 3``  → the 5-hour window
  - ``TOKENS_LIMIT`` with ``unit == 6``  → the 7-day (weekly) window

Each carries ``percentage`` (0-100, how much is USED) and ``nextResetTime``
(epoch milliseconds). We expose ``remaining = 100 - percentage`` to match the
ZCODE UI, and store ``used = percentage`` so the progress bar reflects usage.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .base import BaseProvider, UsageData, WindowStats

#: Mapping of BigModel limit unit codes to our window labels.
UNIT_TO_LABEL = {
    3: "5h",  # TOKENS_LIMIT, unit=3 — rolling 5-hour window
    6: "7d",  # TOKENS_LIMIT, unit=6 — weekly window
}


def _home() -> Path:
    return Path(os.path.expanduser("~"))


class ZCodeProvider(BaseProvider):
    """Reads real BigModel rate-limit percentages via the monitor API."""

    # Budgets are nominal — ZCODE reports a real percentage, not token totals.
    default_budget_5h = 100
    default_budget_7d = 100

    def _load_api_key_and_host(self) -> tuple[str | None, str]:
        """Return (api_key, base_host) from the ZCODE v2 config, or (None, host)."""
        cfg_path = _home() / ".zcode" / "v2" / "config.json"
        default_host = "https://open.bigmodel.cn"
        if not cfg_path.exists():
            return None, default_host
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None, default_host

        provider = (cfg.get("provider") or {}).get(
            "builtin:bigmodel-coding-plan", {}
        )
        opts = provider.get("options", {})
        api_key = opts.get("apiKey")
        base_url = opts.get("baseURL", default_host)
        # Derive scheme + host from the baseURL (strip /api/anthropic etc.).
        parsed = urlparse(base_url)
        host = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else default_host
        return api_key, host

    def _fetch_quota(self) -> dict | None:
        api_key, host = self._load_api_key_and_host()
        if not api_key:
            return None
        url = f"{host}/api/monitor/usage/quota/limit"
        req = urllib.request.Request(url)
        req.add_header("Authorization", api_key)
        req.add_header("Accept", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
            return None

    @staticmethod
    def _epoch_ms_to_dt(ms) -> datetime | None:
        try:
            return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            return None

    def fetch(self) -> UsageData:
        data = UsageData(service="Zcode")

        payload = self._fetch_quota()
        if payload is None:
            data.available = False
            data.error = "Cannot reach BigModel quota API"
            return data

        result = payload.get("data") or {}
        level = result.get("level", "")
        if level:
            data.plan_type = level  # "pro", "free", etc.

        limits = result.get("limits") or []
        win5 = None
        win7 = None
        for lim in limits:
            if lim.get("type") != "TOKENS_LIMIT":
                continue
            unit = lim.get("unit")
            label = UNIT_TO_LABEL.get(unit)
            if label is None:
                continue
            pct = lim.get("percentage")
            reset = self._epoch_ms_to_dt(lim.get("nextResetTime"))
            if pct is None:
                continue
            used_pct = float(pct)
            ws = WindowStats(
                label=label,
                percent=used_pct,
                budget=100,
                used=int(round(used_pct)),
                reset_at=reset,
                is_real_limit=True,
            )
            if label == "5h":
                win5 = ws
            elif label == "7d":
                win7 = ws

        data.model = "GLM-5.2"
        data.window_5h = win5 or WindowStats(label="5h", is_real_limit=True)
        data.window_7d = win7 or WindowStats(label="7d", is_real_limit=True)
        return data
