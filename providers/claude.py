"""Claude (claude.ai Pro) usage provider — reads real subscription rate limits.

Claude Code's session limits are NOT persisted to disk; the app fetches them live
from the ``api/oauth/usage`` endpoint on claude.ai using the OAuth access token
stored in ``~/.claude/.credentials.json``. We replicate that call, so the widget
stays fully automatic.

Endpoint: ``GET https://claude.ai/api/oauth/usage``
  - Authorization: ``Bearer <accessToken>``
  - Returns utilization for a 5-hour (session) window, a 7-day (weekly_all)
    window, and optionally per-model (weekly_scoped) limits.

The response carries a top-level ``five_hour`` / ``seven_day`` summary plus a
``limits[]`` array with per-window and per-model breakdowns. We surface the
session (5h) and weekly_all (7d) percentages, plus the Fable model-specific
weekly limit when present.
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .base import BaseProvider, UsageData, WindowStats

USAGE_URL = "https://claude.ai/api/oauth/usage"

# Module-level cookie jar + opener, so Cloudflare's __cf_bm cookie persists
# across the widget's lifetime. The first request after startup may hit a 403
# challenge, but once the cookie is set all subsequent requests succeed.
_COOKIE_JAR = http.cookiejar.CookieJar()
_OPENER = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(_COOKIE_JAR)
)


def _home() -> Path:
    return Path(os.path.expanduser("~"))


def _parse_iso(raw) -> datetime | None:
    if not raw:
        return None
    try:
        s = str(raw).strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


class ClaudeProvider(BaseProvider):
    """Reads real claude.ai Pro subscription rate limits via the OAuth API."""

    # Budgets are nominal — Claude reports a real utilization percentage.
    default_budget_5h = 100
    default_budget_7d = 100

    def _load_token(self) -> str | None:
        creds_path = _home() / ".claude" / ".credentials.json"
        if not creds_path.exists():
            return None
        try:
            creds = json.loads(creds_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        oauth = creds.get("claudeAiOauth", {})
        return oauth.get("accessToken")

    def _fetch_usage(self) -> dict | None:
        token = self._load_token()
        if not token:
            return None
        import time

        # claude.ai is fronted by Cloudflare. The exact header combination that
        # passes is: Authorization + Accept + Accept-Language + User-Agent set
        # to "claude-code/...". Do NOT send Origin/Referer — that turns the
        # request into a CORS request and triggers a 401 demanding
        # 'anthropic-dangerous-direct-browser-access'. The module-level cookie
        # jar persists __cf_bm so that after the first 403 challenge, subsequent
        # requests succeed reliably.
        for attempt in range(3):
            req = urllib.request.Request(USAGE_URL)
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("Accept", "application/json")
            req.add_header("Accept-Language", "en-US,en;q=0.9")
            req.add_header("User-Agent", "claude-code/2.1.207")
            try:
                with _OPENER.open(req, timeout=15) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code == 403 and attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                return None
            except (urllib.error.URLError, OSError, ValueError):
                return None
        return None

    @staticmethod
    def _pick_model(limits: list, display_name: str) -> tuple[float, str | None]:
        """Find a weekly_scoped limit for a specific model display name."""
        for lim in limits:
            scope = lim.get("scope") or {}
            model = scope.get("model") or {}
            if (
                lim.get("kind") == "weekly_scoped"
                and (model.get("display_name") or "") == display_name
            ):
                return float(lim.get("percent", 0)), lim.get("resets_at")
        return -1.0, None

    def fetch(self) -> UsageData:
        data = UsageData(service="Claude")

        payload = self._fetch_usage()
        if payload is None:
            data.available = False
            data.error = "Cannot reach claude.ai/api/oauth/usage"
            return data

        limits = payload.get("limits") or []

        # --- 5-hour session window ---
        session = next(
            (l for l in limits if l.get("kind") == "session"), None
        )
        if session is None:
            fh = payload.get("five_hour") or {}
            pct5 = fh.get("utilization", 0)
            reset5 = fh.get("resets_at")
        else:
            pct5 = session.get("percent", 0)
            reset5 = session.get("resets_at")
        data.window_5h = WindowStats(
            label="5h",
            percent=float(pct5),
            budget=100,
            used=int(round(float(pct5))),
            reset_at=_parse_iso(reset5),
            is_real_limit=True,
        )

        # --- 7-day weekly window (all models) ---
        weekly = next(
            (l for l in limits if l.get("kind") == "weekly_all"), None
        )
        if weekly is None:
            sd = payload.get("seven_day") or {}
            pct7 = sd.get("utilization", 0)
            reset7 = sd.get("resets_at")
        else:
            pct7 = weekly.get("percent", 0)
            reset7 = weekly.get("resets_at")

        # Check if there's a model-scoped weekly limit (e.g. Fable) that is
        # higher than the all-models limit — if so, the all-models window is the
        # binding one, but we note the Fable-specific figure in plan_type.
        fable_pct, _ = self._pick_model(limits, "Fable")
        model_note = ""
        if fable_pct >= 0:
            model_note = f"+Fable {fable_pct:.0f}%"

        data.window_7d = WindowStats(
            label="7d",
            percent=float(pct7),
            budget=100,
            used=int(round(float(pct7))),
            reset_at=_parse_iso(reset7),
            is_real_limit=True,
        )

        data.model = "claude-fable-5"
        sub = (payload.get("extra_usage") or {}).get("disabled_reason", "")
        data.plan_type = "Pro" + (f" {model_note}" if model_note else "")
        if sub == "out_of_credits":
            data.plan_type += " · no credits"

        return data
