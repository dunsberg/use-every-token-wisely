# Use Every Token Wisely

A translucent, always-on-top desktop widget that monitors your real-time AI usage quotas for **ZCODE**, **Claude**, and **Codex** — so you always know how much runway you have left.

![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue)
![PySide6](https://img.shields.io/badge/GUI-PySide6-green)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow)

## Features

- 📊 **Real quota data** — reads actual rate-limit percentages, not estimates
- ⏱️ **5-hour & 7-day windows** — each service shows both windows with reset times
- 🔄 **Auto-refresh every 5 minutes** with a live countdown
- 🪟 **Frameless, translucent, always-on-top** — stays on your desktop without getting in the way
- 🎨 **Service-themed colors** — ZCODE (blue), Claude (orange), Codex (black/white)
- 🖱️ **Drag to reposition**, right-click for menu (opacity, budgets, about, quit)

## How It Works

The widget reads your usage data automatically — **no API keys to configure, no manual entry**:

| Service | Data Source |
|---------|------------|
| **ZCODE** | BigModel quota API (`open.bigmodel.cn/api/monitor/usage/quota/limit`) using the API key from your local ZCODE config |
| **Claude** | claude.ai OAuth usage API (`claude.ai/api/oauth/usage`) using the OAuth token from your Claude credentials |
| **Codex** | Real `rate_limits` data from your local Codex session files (`~/.codex/sessions/`) |

All credentials are read from your existing local installs — nothing is sent anywhere except to the official quota endpoints that each tool already uses.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run it
python main.py
```

That's it. The widget appears on your desktop. Drag it wherever you like.

## Requirements

- Python 3.12+
- PySide6 (`pip install PySide6`)
- Windows (tested on Windows 11)
- At least one of: ZCODE, Claude Code, or Codex installed locally

## Usage

- **Left-drag** — move the widget around; position is saved automatically
- **Right-click** — open the context menu:
  - **Refresh now** — force a data refresh
  - **Opacity** — adjust window transparency (70%–100%)
  - **Set budgets** — set token budgets for Claude/ZCODE (Codex uses real limits)
  - **About** — project info
  - **Quit** — exit

## How Quotas Are Read

### ZCODE (BigModel / GLM)
Reads `~/.zcode/v2/config.json` for the API key, then calls the BigModel monitor API to get real 5-hour (`TOKENS_LIMIT unit=3`) and weekly (`TOKENS_LIMIT unit=6`) utilization percentages.

### Claude (claude.ai Pro)
Reads `~/.claude/.credentials.json` for the OAuth access token, then calls `claude.ai/api/oauth/usage` to get real session (5h) and weekly (7d) utilization, plus per-model limits (e.g. Fable).

### Codex (OpenAI)
Parses the most recent session file in `~/.codex/sessions/` for the last `token_count` event, which contains real `rate_limits` with `used_percent` and `resets_at` for both 5-hour and 7-day windows.

## Configuration

On first run, a `config.json` is created in the project directory to remember:
- Window position
- Opacity setting
- Custom token budgets (for Claude/ZCODE)

## License

[MIT](LICENSE) © Mingsberg Hui

## Contact

Open an issue at [github.com/studio1008/use-every-token-wisely/issues](https://github.com/studio1008/use-every-token-wisely/issues)
