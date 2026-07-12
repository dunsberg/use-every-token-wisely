"""Codex (OpenAI) usage provider — reads real rate-limit data from local session files.

Codex session files live at ``~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl``. Each
line is ``{"timestamp": ..., "type": ..., "payload": {...}}``. Token usage lives
only on lines where ``type == "event_msg"`` and ``payload.type == "token_count"``,
which expose real ``rate_limits`` with ``used_percent`` and ``resets_at`` (Unix
seconds) for both a 5-hour (``primary``) and a 7-day (``secondary``) window.

We only read the most-recently-modified session file and grab its last
``token_count`` event — no need to scan the full 833 MB history.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .base import BaseProvider, UsageData, WindowStats, parse_iso_timestamp


def _home() -> Path:
    return Path(os.path.expanduser("~"))


class CodexProvider(BaseProvider):
    """Reads Codex real rate-limit percentages from the latest session file."""

    default_budget_5h = 1  # Codex reports a real percentage; budget is nominal.
    default_budget_7d = 1

    def _latest_session_file(self) -> Path | None:
        sessions_dir = _home() / ".codex" / "sessions"
        if not sessions_dir.exists():
            return None
        candidates = sorted(
            sessions_dir.rglob("rollout-*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return candidates[0] if candidates else None

    def _last_token_count(self, path: Path) -> tuple[dict, dict] | None:
        """Return (last_token_count_line, last_turn_context_line) or None.

        We stream the file once, keeping references to the last matching lines.
        """
        last_tc: dict | None = None
        last_ctx_model = ""
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ltype = obj.get("type")
                    payload = obj.get("payload") or {}
                    if ltype == "turn_context":
                        model = payload.get("model")
                        if model:
                            last_ctx_model = model
                    elif (
                        ltype == "event_msg"
                        and payload.get("type") == "token_count"
                    ):
                        last_tc = obj
        except OSError:
            return None

        if last_tc is None:
            return None
        return last_tc, {"model": last_ctx_model}

    @staticmethod
    def _unix_to_dt(unix_ts) -> datetime | None:
        try:
            return datetime.fromtimestamp(int(unix_ts), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            return None

    def fetch(self) -> UsageData:
        data = UsageData(service="Codex")

        path = self._latest_session_file()
        if path is None:
            data.available = False
            data.error = "No Codex sessions found"
            return data

        result = self._last_token_count(path)
        if result is None:
            data.available = False
            data.error = "No token_count event in latest session"
            return data

        tc_line, ctx = result
        payload = tc_line.get("payload") or {}
        data.model = ctx.get("model", "")
        data.plan_type = payload.get("rate_limits", {}).get("plan_type", "")

        rate_limits = payload.get("rate_limits") or {}
        primary = rate_limits.get("primary") or {}
        secondary = rate_limits.get("secondary") or {}

        # Primary = 5-hour window.
        used_pct_5h = primary.get("used_percent")
        reset_5h = self._unix_to_dt(primary.get("resets_at"))
        if used_pct_5h is not None:
            data.window_5h = WindowStats(
                label="5h",
                percent=float(used_pct_5h),
                budget=100,
                used=int(float(used_pct_5h)),  # store as 0-100 for display
                reset_at=reset_5h,
                is_real_limit=True,
            )

        # Secondary = 7-day window.
        used_pct_7d = secondary.get("used_percent")
        reset_7d = self._unix_to_dt(secondary.get("resets_at"))
        if used_pct_7d is not None:
            data.window_7d = WindowStats(
                label="7d",
                percent=float(used_pct_7d),
                budget=100,
                used=int(float(used_pct_7d)),
                reset_at=reset_7d,
                is_real_limit=True,
            )

        # Fallback: if rate_limits missing but token counts exist, show raw tokens.
        if used_pct_5h is None and used_pct_7d is None:
            info = payload.get("info") or {}
            ttu = info.get("total_token_usage") or {}
            total_tokens = ttu.get("total_tokens", 0)
            data.window_5h = WindowStats(
                label="5h",
                used=total_tokens,
                budget=self.budget_5h,
                percent=round(total_tokens / self.budget_5h * 100, 1)
                if self.budget_5h
                else 0.0,
            )

        return data
