"""TRAE (ByteDance AI IDE) usage provider — placeholder for Free users.

TRAE's real-time usage percentages come from ``api.trae.cn/trae/api/v2/pay/
ide_user_ent_usage``, but that endpoint is protected by ByteDance's ``ttnet``
private signing layer which cannot be replicated in plain Python. Until a public
API or a signing workaround is available, this provider reads the cached plan
tier from the local TRAE globalStorage and shows N/A for the progress bars.

When the user upgrades to a paid plan, we can revisit the ttnet authentication.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .base import BaseProvider, UsageData, WindowStats


def _home() -> Path:
    return Path(os.path.expanduser("~"))


class TraeProvider(BaseProvider):
    """Placeholder provider — reads cached plan tier, shows N/A for usage."""

    default_budget_5h = 100
    default_budget_7d = 100

    def _read_plan_tier(self) -> str:
        """Read the cached plan tier from TRAE CN's globalStorage."""
        storage = (
            _home()
            / "AppData"
            / "Roaming"
            / "Trae CN"
            / "User"
            / "globalStorage"
            / "storage.json"
        )
        if not storage.exists():
            return ""
        try:
            raw = json.loads(storage.read_text(encoding="utf-8"))
            server_data = raw.get("iCubeServerData://icube.cloudide", "")
            if isinstance(server_data, str):
                server_data = json.loads(server_data)
            ent = server_data.get("entitlementInfo", {})
            tier = ent.get("identityStr", "")
            return tier  # "Free", "Pro", etc.
        except (json.JSONDecodeError, OSError, KeyError, TypeError):
            return ""

    def fetch(self) -> UsageData:
        data = UsageData(service="TRAE")
        data.model = "Doubao / GLM"
        plan = self._read_plan_tier()
        data.plan_type = plan or "Free"
        # Free plan has no quota API access (ttnet-protected). Show N/A.
        if plan in ("", "Free"):
            data.available = False
            data.error = "Free plan — N/A"
        else:
            # Paid plan: ttnet signing still blocks us, but we note the tier.
            data.available = False
            data.error = f"{plan} — quota API blocked"
        return data
