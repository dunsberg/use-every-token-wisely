# ⚡Use Every Token Wisely⚡

A translucent, always-on-top desktop widget that monitors your **real-time AI usage quotas** — so you always know how much runway you have left.

Supports **ZCODE**, **Claude**, **Codex**, and **TRAE**.

![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue)
![PySide6](https://img.shields.io/badge/GUI-PySide6-green)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow)
![Windows](https://img.shields.io/badge/platform-Windows-blue)

## Features

- 📊 **Real quota data** — reads actual rate-limit percentages from each platform, not estimates
- ⏱️ **5-hour & 7-day windows** — each service shows both windows with exact reset dates
- 🔄 **Auto-refresh every 5 minutes** with a live countdown (turns purple in the last 10 seconds)
- 🪟 **Frameless, translucent, always-on-top** — a clean outline floating on your desktop
- 🎨 **Service-themed colors** — ZCODE (blue), Claude (orange), Codex (black), TRAE (green)
- 🔴 **Low-quota alert** — percentage text turns red when remaining drops below 10%
- 📂 **Collapsible cards** — fold/unfold any service from the right-click menu
- 🚀 **Launch on startup** — optional auto-launch when you boot Windows
- 🖱️ **Drag to reposition** — position is saved automatically

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run it
python main.py
```

Or double-click the desktop shortcut (run `python create_shortcut.py` to create one).

## Supported Services

| Service | Color | Data Source |
|---------|-------|-------------|
| **ZCODE** | Blue | BigModel quota API (`open.bigmodel.cn`) — reads API key from `~/.zcode/v2/config.json` |
| **Claude** | Orange | claude.ai OAuth usage API (`claude.ai/api/oauth/usage`) — reads token from `~/.claude/.credentials.json` |
| **Codex** | Black | Real `rate_limits` from local session files (`~/.codex/sessions/`) |
| **TRAE** | Green | *Placeholder* — TRAE's quota API is protected by ByteDance's `ttnet` signing. Shows plan tier (Free/Pro); full quota data coming when a public API is available |

All credentials are read from your existing local installs — **no API keys to configure, no manual entry**. Nothing is sent anywhere except to the official quota endpoints each tool already uses.

## How Quotas Are Read

### ZCODE (BigModel / GLM)
Reads `~/.zcode/v2/config.json` for the API key, then calls the BigModel monitor API to get real 5-hour (`TOKENS_LIMIT unit=3`) and weekly (`TOKENS_LIMIT unit=6`) utilization percentages with reset timestamps.

### Claude (claude.ai Pro)
Reads `~/.claude/.credentials.json` for the OAuth access token, then calls `claude.ai/api/oauth/usage` to get real session (5h) and weekly (7d) utilization, plus per-model limits (e.g. Fable). Uses a persistent cookie jar to pass Cloudflare's bot detection.

### Codex (OpenAI)
Parses the most recent session file in `~/.codex/sessions/` for the last `token_count` event, which contains real `rate_limits` with `used_percent` and `resets_at` for both 5-hour (`primary`) and 7-day (`secondary`) windows.

### TRAE (ByteDance)
Reads the cached plan tier from `~/.trae-cn/` local storage. TRAE's live usage API (`api.trae.cn/trae/api/v2/pay/ide_user_ent_usage`) is protected by ByteDance's proprietary `ttnet` signing layer, which cannot be replicated in plain HTTP requests. Shows "Free Plan N/A" for free users; paid plan support is a work in progress.

## Usage

- **Left-drag** — move the widget; position is saved automatically
- **Right-click** — open the context menu:
  - **↻ Refresh now** — force a data refresh
  - **Service checkboxes** (ZCODE / Claude / Codex / TRAE) — expand/collapse each card
  - **🚀 Launch on startup** — toggle boot auto-launch
  - **ⓘ About** — project info
  - **✕ Quit** — exit

## Requirements

- Python 3.12+
- PySide6 (`pip install -r requirements.txt`)
- Windows (tested on Windows 11)
- At least one of: ZCODE, Claude Code, Codex, or TRAE installed locally

## License

MIT License — see [LICENSE](LICENSE)

## Links

- **Source:** [github.com/dunsberg/use-every-token-wisely](https://github.com/dunsberg/use-every-token-wisely)
- **Issues:** [github.com/dunsberg/use-every-token-wisely/issues](https://github.com/dunsberg/use-every-token-wisely/issues)
