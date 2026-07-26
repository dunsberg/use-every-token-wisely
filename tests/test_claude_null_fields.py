"""Regression test: Claude fetch() must tolerate null fields in the usage API.

Reproduces the 2026-07-22 crash:
    TypeError: float() argument must be a string or a real number, not 'NoneType'
caused by extra_usage = {"is_enabled": true, "monthly_limit": null, ...}.

Run from the repo root: python tests/test_claude_null_fields.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from providers.claude import ClaudeProvider

# Mirrors the real 2026-07-22 response shape: several keys present but null.
PAYLOAD_WITH_NULLS = {
    "five_hour": {"utilization": None, "resets_at": None},
    "seven_day": {"utilization": None, "resets_at": None},
    "limits": [
        {"kind": "session", "percent": None, "resets_at": None, "scope": None},
        {"kind": "weekly_all", "percent": 8, "resets_at": "2026-07-28T16:59:59Z", "scope": None},
        {"kind": "weekly_scoped", "percent": None, "resets_at": None,
         "scope": {"model": {"display_name": "Fable"}}},
    ],
    "extra_usage": {
        "is_enabled": True,
        "monthly_limit": None,   # <- the actual crash trigger
        "used_credits": 0.0,
        "disabled_reason": None,
    },
    "spend": {"balance": None, "limit": None},
}


class TestNullTolerance(unittest.TestCase):
    def setUp(self):
        self.provider = ClaudeProvider()

    def test_fetch_with_null_fields_does_not_raise(self):
        with patch.object(ClaudeProvider, "_fetch_usage", return_value=PAYLOAD_WITH_NULLS):
            data = self.provider.fetch()
        self.assertTrue(data.available)
        # Null percents degrade to 0 rather than crashing.
        self.assertEqual(data.window_5h.percent, 0.0)
        self.assertEqual(data.window_7d.percent, 8.0)
        # Fable window present (kind matched) but null percent -> 0, no crash.
        self.assertIsNotNone(data.window_model)
        self.assertEqual(data.window_model.percent, 0.0)
        # monthly_limit null -> credits cannot be computed -> hidden ("").
        self.assertEqual(data.credits, "")

    def test_pick_model_with_null_percent(self):
        pct, reset = ClaudeProvider._pick_model(PAYLOAD_WITH_NULLS["limits"], "Fable")
        self.assertEqual(pct, 0.0)

    def test_normal_payload_still_works(self):
        payload = {
            "limits": [
                {"kind": "session", "percent": 81, "resets_at": None, "scope": None},
                {"kind": "weekly_all", "percent": 35, "resets_at": None, "scope": None},
            ],
            "extra_usage": {"is_enabled": False},
            "spend": {"balance": {"amount_minor": 250, "exponent": 2}},
        }
        with patch.object(ClaudeProvider, "_fetch_usage", return_value=payload):
            data = self.provider.fetch()
        self.assertEqual(data.window_5h.percent, 81.0)
        self.assertEqual(data.window_7d.percent, 35.0)
        self.assertEqual(data.credits, "$2.50")


if __name__ == "__main__":
    unittest.main(verbosity=2)
    sys.exit(0)
