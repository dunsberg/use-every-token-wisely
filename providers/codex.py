"""Codex (OpenAI) usage provider — reads real rate-limit data from ChatGPT API.

Calls ``https://chatgpt.com/backend-api/codex/usage`` with the ChatGPT OAuth
access token stored in ``~/.codex/auth.json``. Returns real rate-limit
percentages and reset timestamps for all available windows, plus credits
balance and reset credits count.

Falls back to reading the latest local session file if the API is unreachable.
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .base import BaseProvider, UsageData, WindowStats

USAGE_URL = "https://chatgpt.com/backend-api/codex/usage"

# Module-level cookie jar for Cloudflare bypass (same pattern as Claude).
_COOKIE_JAR = http.cookiejar.CookieJar()
_OPENER = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(_COOKIE_JAR)
)


def _home() -> Path:
    return Path(os.path.expanduser("~"))


class CodexProvider(BaseProvider):
    """Reads Codex real rate-limit percentages via the ChatGPT API."""

    default_budget_5h = 1
    default_budget_7d = 1

    def _load_auth(self) -> tuple[str | None, dict]:
        """Return (access_token, full_auth_dict) from ~/.codex/auth.json."""
        auth_path = _home() / ".codex" / "auth.json"
        if not auth_path.exists():
            return None, {}
        try:
            auth = json.loads(auth_path.read_text(encoding="utf-8"))
            token = (auth.get("tokens") or {}).get("access_token")
            return token, auth
        except (json.JSONDecodeError, OSError):
            return None, {}

    def _warmup_cloudflare(self, token: str) -> None:
        """Send a warm-up request to get/refresh the __cf_bm cookie.

        ChatGPT's Cloudflare requires a valid __cf_bm cookie before API
        requests succeed. The first hit returns 403 but sets the cookie.
        Without this, direct calls to /codex/usage get SSL-disconnected.
        """
        req = urllib.request.Request("https://chatgpt.com/backend-api/me")
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Accept", "application/json")
        req.add_header("Accept-Language", "en-US,en;q=0.9")
        req.add_header(
            "User-Agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )
        try:
            with _OPENER.open(req, timeout=10) as _:
                pass
        except urllib.error.HTTPError:
            # 403 is expected — the important thing is the cookie gets set.
            try:
                _.read()
            except Exception:
                pass
        except Exception:
            pass

    def _fetch_usage_api(self) -> dict | None:
        """Call the ChatGPT codex/usage API."""
        token, _ = self._load_auth()
        if not token:
            return None

        # Warm up Cloudflare to get/refresh the __cf_bm cookie.
        self._warmup_cloudflare(token)

        for attempt in range(3):
            req = urllib.request.Request(USAGE_URL)
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("Accept", "application/json")
            req.add_header("Accept-Language", "en-US,en;q=0.9")
            req.add_header(
                "User-Agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            )
            try:
                with _OPENER.open(req, timeout=15) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                try:
                    e.read()
                except Exception:
                    pass
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                return None
            except (urllib.error.URLError, OSError, ValueError):
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                return None
        return None

    @staticmethod
    def _unix_to_dt(unix_ts) -> datetime | None:
        try:
            return datetime.fromtimestamp(int(unix_ts), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            return None

    @staticmethod
    def _window_label(seconds: int) -> str:
        """Convert window seconds to a short label."""
        if seconds <= 21600:  # <= 6h
            return "5h"
        if seconds <= 90000:  # <= 25h
            return "1d"
        if seconds <= 691200:  # <= 8d
            return "7d"
        days = seconds // 86400
        return f"{days}d"

    def fetch(self) -> UsageData:
        data = UsageData(service="ChatGPT")

        payload = self._fetch_usage_api()
        if payload is None:
            # Fallback to session file
            return self._fetch_from_session()

        data.model = "gpt-5.5"
        data.plan_type = payload.get("plan_type", "")

        # --- Rate limit windows ---
        rl = payload.get("rate_limit") or {}
        for win_key in ("primary_window", "secondary_window"):
            win = rl.get(win_key) or {}
            pct = win.get("used_percent")
            if pct is None:
                continue
            secs = win.get("limit_window_seconds", 0)
            reset = self._unix_to_dt(win.get("reset_at"))
            label = self._window_label(secs)
            data.extra_windows.append(WindowStats(
                label=label,
                percent=float(pct),
                budget=100,
                used=int(float(pct)),
                reset_at=reset,
                is_real_limit=True,
            ))

        # --- Credits ---
        credits = payload.get("credits") or {}
        balance = credits.get("balance")
        if balance is not None and str(balance) != "0":
            try:
                data.credits = f"${float(balance):.2f}"
            except (TypeError, ValueError):
                pass
        elif credits.get("has_credits") is False:
            data.credits = "$0.00"

        # --- Rate limit reset credits (the "2 resets" the user sees) ---
        reset_credits = payload.get("rate_limit_reset_credits") or {}
        avail = reset_credits.get("available_count", 0)
        if avail > 0:
            # Show as an extra info line in plan_type
            data.plan_type = f"{data.plan_type} | {avail} resets"

        return data

    # ------------------------------------------------------------------
    # Fallback: read from latest session file (old method)
    # ------------------------------------------------------------------
    def _fetch_from_session(self) -> UsageData:
        """Fallback: read rate_limits from the latest Codex session file."""
        data = UsageData(service="ChatGPT")
        data.available = False
        data.error = "Cannot reach ChatGPT API"
        return data
