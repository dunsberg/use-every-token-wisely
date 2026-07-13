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

import base64
import ctypes
import ctypes.wintypes
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

    REFRESH_URL = "https://platform.claude.com/v1/oauth/token"
    CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"

    # ------------------------------------------------------------------
    # Tier 1: Claude Desktop encrypted cache (Windows only, most reliable)
    # ------------------------------------------------------------------

    @staticmethod
    def _dpapi_unprotect(data: bytes) -> bytes | None:
        """Decrypt data using Windows DPAPI CryptUnprotectData."""
        if sys.platform != "win32":
            return None
        try:
            class DATA_BLOB(ctypes.Structure):
                _fields_ = [
                    ("cbData", ctypes.wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_char)),
                ]

            blob_in = DATA_BLOB(
                len(data),
                ctypes.cast(
                    ctypes.create_string_buffer(data, len(data)),
                    ctypes.POINTER(ctypes.c_char),
                ),
            )
            blob_out = DATA_BLOB()
            if not ctypes.windll.crypt32.CryptUnprotectData(
                ctypes.byref(blob_in), None, None, None, None, 0,
                ctypes.byref(blob_out),
            ):
                return None
            result = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)
            return result
        except Exception:
            return None

    def _load_token_from_desktop_cache(self) -> str | None:
        """Decrypt Claude Desktop's Chromium os_crypt token cache (Windows).

        Claude Desktop stores long-lived OAuth tokens (weeks/months) in its
        config.json, encrypted with AES-256-GCM. The AES key is itself
        encrypted with Windows DPAPI and stored in Local State. This method
        decrypts both layers entirely locally — no network calls, no rate
        limits. Falls back gracefully on macOS or if files are missing.
        """
        if sys.platform != "win32":
            return None
        try:
            appdata = Path(os.environ.get("APPDATA", "")) / "Claude"
            local_state_path = appdata / "Local State"
            config_path = appdata / "config.json"
            if not local_state_path.exists() or not config_path.exists():
                return None

            # 1. Read Local State → os_crypt.encrypted_key → DPAPI decrypt.
            local_state = json.loads(
                local_state_path.read_text(encoding="utf-8")
            )
            enc_key_b64 = (
                local_state.get("os_crypt", {}).get("encrypted_key")
            )
            if not enc_key_b64:
                return None
            enc_key = base64.b64decode(enc_key_b64)
            if not enc_key.startswith(b"DPAPI"):
                return None
            aes_key = self._dpapi_unprotect(enc_key[5:])
            if not aes_key or len(aes_key) != 32:
                return None

            # 2. Read config.json → decrypt oauth:tokenCacheV2 (or V1).
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM

            aesgcm = AESGCM(aes_key)
            now_ms = int(time.time() * 1000)

            for cache_key in ("oauth:tokenCacheV2", "oauth:tokenCache"):
                blob_b64 = cfg.get(cache_key)
                if not blob_b64:
                    continue
                blob = base64.b64decode(blob_b64)
                if not blob.startswith(b"v10"):
                    continue
                nonce = blob[3:15]
                ciphertext_and_tag = blob[15:]
                try:
                    plaintext = aesgcm.decrypt(
                        nonce, ciphertext_and_tag, None
                    )
                except Exception:
                    continue
                data = json.loads(plaintext.decode("utf-8"))
                # data is keyed by "clientId:orgId:apiUrl:scopes"
                if isinstance(data, dict):
                    for _key, val in data.items():
                        if not isinstance(val, dict):
                            continue
                        token = val.get("token")
                        expires_at = val.get("expiresAt", 0)
                        # Prefer non-expired tokens with inference scope.
                        scopes = _key.split(":")[-1] if ":" in _key else ""
                        if token and ("inference" in scopes or "user:" in scopes):
                            if not expires_at or now_ms < expires_at:
                                return token
                    # Fallback: any non-expired token.
                    for _key, val in data.items():
                        if isinstance(val, dict):
                            token = val.get("token")
                            expires_at = val.get("expiresAt", 0)
                            if token and (not expires_at or now_ms < expires_at):
                                return token
        except Exception:
            return None
        return None

    # ------------------------------------------------------------------
    # Tier 2: ~/.claude/.credentials.json
    # ------------------------------------------------------------------

    def _load_credentials(self) -> dict | None:
        """Load the full credentials dict from disk."""
        creds_path = _home() / ".claude" / ".credentials.json"
        if not creds_path.exists():
            return None
        try:
            return json.loads(creds_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def _save_credentials(self, creds: dict) -> None:
        """Write credentials back to disk (after token refresh)."""
        creds_path = _home() / ".claude" / ".credentials.json"
        try:
            creds_path.write_text(
                json.dumps(creds, indent=2), encoding="utf-8"
            )
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Tier 3: Refresh token via platform.claude.com (last resort)
    # ------------------------------------------------------------------

    def _refresh_token(self, refresh_token: str) -> dict | None:
        """Exchange a refresh token for a new access token."""
        from urllib.parse import urlencode

        data = urlencode({
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.CLIENT_ID,
        }).encode("utf-8")

        req = urllib.request.Request(self.REFRESH_URL, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        req.add_header("Accept-Language", "en-US,en;q=0.9")
        req.add_header("User-Agent", "claude-code/2.1.207")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
            return None

    # ------------------------------------------------------------------
    # Orchestrator: try all three tiers in priority order
    # ------------------------------------------------------------------

    def _load_token(self) -> str | None:
        """Get a valid access token using a 3-tier fallback strategy.

        Tier 1: Claude Desktop's encrypted cache (long-lived, no network).
        Tier 2: ~/.claude/.credentials.json (if not expired).
        Tier 3: Refresh token via platform.claude.com (rate-limited).
        """
        now_ms = int(time.time() * 1000)

        # --- Tier 1: Desktop cache ---
        token = self._load_token_from_desktop_cache()
        if token:
            return token

        # --- Tier 2: CLI credentials file ---
        creds = self._load_credentials()
        if creds:
            oauth = creds.get("claudeAiOauth", {})
            access_token = oauth.get("accessToken")
            expires_at = oauth.get("expiresAt", 0)
            if access_token and now_ms < (expires_at - 60_000):
                return access_token

            # --- Tier 3: Refresh ---
            refresh_token = oauth.get("refreshToken")
            refresh_expires_at = oauth.get("refreshTokenExpiresAt", 0)
            if refresh_token and now_ms < refresh_expires_at:
                new_token = self._refresh_token(refresh_token)
                if new_token and "access_token" in new_token:
                    oauth["accessToken"] = new_token["access_token"]
                    oauth["expiresAt"] = (
                        now_ms + new_token.get("expires_in", 3600) * 1000
                    )
                    if "refresh_token" in new_token:
                        oauth["refreshToken"] = new_token["refresh_token"]
                    creds["claudeAiOauth"] = oauth
                    self._save_credentials(creds)
                    return new_token["access_token"]

            # Return stale token as last resort (better than nothing).
            if access_token:
                return access_token

        return None

    def _refresh_token(self, refresh_token: str) -> dict | None:
        """Exchange a refresh token for a new access token."""
        from urllib.parse import urlencode

        data = urlencode({
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.CLIENT_ID,
        }).encode("utf-8")

        req = urllib.request.Request(self.REFRESH_URL, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        req.add_header("Accept-Language", "en-US,en;q=0.9")
        req.add_header("User-Agent", "claude-code/2.1.207")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
            return None

    def _fetch_usage(self) -> dict | None:
        token = self._load_token()
        if not token:
            return None
        import time

        # claude.ai is fronted by Cloudflare. The __cf_bm cookie expires
        # after ~30 min, so long-running widgets will hit 403 challenges
        # repeatedly. On 403, clear the cookie jar and retry — the first
        # request gets challenged (sets a new cookie), the second succeeds.
        for attempt in range(4):
            req = urllib.request.Request(USAGE_URL)
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("Accept", "application/json")
            req.add_header("Accept-Language", "en-US,en;q=0.9")
            req.add_header("User-Agent", "claude-code/2.1.207")
            try:
                with _OPENER.open(req, timeout=15) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code == 403 and attempt < 3:
                    # Cloudflare challenge — clear stale cookies and retry.
                    _COOKIE_JAR.clear()
                    # Drain the error body so the connection can be reused.
                    try:
                        e.read()
                    except Exception:
                        pass
                    time.sleep(1.5 * (attempt + 1))
                    continue
                if e.code == 401 and attempt < 3:
                    # Token might be stale — reload and retry.
                    token = self._load_token()
                    if not token:
                        return None
                    try:
                        e.read()
                    except Exception:
                        pass
                    time.sleep(1)
                    continue
                return None
            except (urllib.error.URLError, OSError, ValueError):
                if attempt < 3:
                    time.sleep(1.5 * (attempt + 1))
                    continue
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

        # --- Fable 5 model-specific weekly window (third progress bar) ---
        fable_pct, fable_reset = self._pick_model(limits, "Fable")
        if fable_pct >= 0:
            data.window_model = WindowStats(
                label="F5",
                percent=float(fable_pct),
                budget=100,
                used=int(round(float(fable_pct))),
                reset_at=_parse_iso(fable_reset),
                is_real_limit=True,
            )

        data.window_7d = WindowStats(
            label="7d",
            percent=float(pct7),
            budget=100,
            used=int(round(float(pct7))),
            reset_at=_parse_iso(reset7),
            is_real_limit=True,
        )

        data.model = "claude-fable-5"
        data.plan_type = "Pro"

        # --- Credits balance ---
        spend = payload.get("spend") or {}
        balance = spend.get("balance")
        if balance is not None:
            # balance has amount_minor + exponent (cents with decimal places)
            amt = balance.get("amount_minor", 0)
            exp = balance.get("exponent", 2)
            data.credits = f"${amt / (10 ** exp):.2f}"
        else:
            # balance is null when out of credits
            extra = payload.get("extra_usage") or {}
            if extra.get("disabled_reason") == "out_of_credits":
                data.credits = "$0.00"
            elif extra.get("is_enabled"):
                # Compute from limit - used
                limit = extra.get("monthly_limit", 0)
                used = extra.get("used_credits", 0)
                exp = (spend.get("limit") or {}).get("exponent", 2)
                remaining = float(limit) - float(used)
                data.credits = f"${remaining / (10 ** exp):.2f}"

        return data
