"""Kimi (Moonshot AI) usage provider — reads real quota from the Kimi API.

Calls the Kimi membership API to get subscription usage ratio and rate-limit
reset times for both 5-hour and 7-day windows.

Endpoint: POST https://www.kimi.com/apiv2/kimi.gateway.membership.v2.MembershipService/GetSubscriptionStats
Auth: Bearer token from ~/.kimi-desktop bridge-store/token-store.json (plaintext)
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .base import BaseProvider, UsageData, WindowStats

STATS_URL = (
    "https://www.kimi.com/apiv2/"
    "kimi.gateway.membership.v2.MembershipService/GetSubscriptionStats"
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


class KimiProvider(BaseProvider):
    """Reads real Kimi subscription usage via the membership API."""

    default_budget_5h = 100
    default_budget_7d = 100

    def _load_token(self) -> tuple[str | None, str | None]:
        """Return (access_token, device_id) from Kimi's local files."""
        token_path = (
            _home()
            / "AppData"
            / "Roaming"
            / "kimi-desktop"
            / "bridge-store"
            / "token-store.json"
        )
        identity_path = _home() / ".kimi-webbridge" / "identity.json"
        if not token_path.exists():
            return None, None
        try:
            store = json.loads(token_path.read_text(encoding="utf-8"))
            token = store.get("tokens", {}).get("access_token")
        except (json.JSONDecodeError, OSError):
            token = None

        device_id = None
        if identity_path.exists():
            try:
                device_id = json.loads(
                    identity_path.read_text(encoding="utf-8")
                ).get("device_id")
            except (json.JSONDecodeError, OSError):
                pass
        return token, device_id

    def _fetch_stats(self) -> dict | None:
        token, device_id = self._load_token()
        if not token:
            return None

        req = urllib.request.Request(STATS_URL, data=b"{}", method="POST")
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Content-Type", "application/json")
        req.add_header("connect-protocol-version", "1")
        req.add_header("r-timezone", "Asia/Taipei")
        req.add_header("x-msh-platform", "windows")
        if device_id:
            req.add_header("x-msh-device-id", device_id)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
            return None

    def fetch(self) -> UsageData:
        data = UsageData(service="Kimi")

        payload = self._fetch_stats()
        if payload is None:
            data.available = False
            data.error = "Cannot reach Kimi API"
            return data

        balance = payload.get("subscriptionBalance") or {}
        used_ratio = balance.get("amountUsedRatio", 0)
        used_pct = float(used_ratio) * 100

        # 5h window
        rl5h = payload.get("ratelimitCode5h") or {}
        reset5 = _parse_iso(rl5h.get("resetTime"))
        data.extra_windows.append(WindowStats(
            label="5h",
            percent=used_pct,
            budget=100,
            used=int(round(used_pct)),
            reset_at=reset5,
            is_real_limit=True,
        ))

        # 7d window
        rl7d = payload.get("ratelimitCode7d") or {}
        reset7 = _parse_iso(rl7d.get("resetTime"))
        data.extra_windows.append(WindowStats(
            label="7d",
            percent=used_pct,
            budget=100,
            used=int(round(used_pct)),
            reset_at=reset7,
            is_real_limit=True,
        ))

        # Kimi Code (coding agent) usage — separate ratio from the main balance
        kimi_code_ratio = balance.get("kimiCodeUsedRatio", 0)
        kimi_code_pct = float(kimi_code_ratio) * 100
        if kimi_code_pct > 0:
            data.window_model = WindowStats(
                label="K3",
                percent=kimi_code_pct,
                budget=100,
                used=int(round(kimi_code_pct)),
                reset_at=reset7,  # shares the 7d reset
                is_real_limit=True,
            )

        # Plan type
        sub_data = ""
        try:
            store = json.loads(
                (_home() / "AppData/Roaming/kimi-desktop/bridge-store/token-store.json")
                .read_text(encoding="utf-8")
            )
            sub_data = store.get("tokens", {}).get("msh_user_subscription_data", "")
            if isinstance(sub_data, str):
                sub_data = json.loads(sub_data).get("currentMembershipLevel", "")
        except Exception:
            pass
        if sub_data == 25:
            data.plan_type = "Pro"
        elif sub_data == 10:
            data.plan_type = "Plus"
        else:
            data.plan_type = str(sub_data) if sub_data else ""

        return data
