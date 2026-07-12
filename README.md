# ⚡Use Every Token Wisely⚡

> 🔒 This widget runs **entirely on your computer**. It does **not** route through any
> third-party server, does **not** collect telemetry or analytics, and your API keys and
> tokens **never leave your machine** — they are read from each tool's own local config
> files and used only to authenticate against that provider's **official endpoints**.
>
> Connects directly to official provider endpoints only when required to retrieve quota information.

A translucent, always-on-top desktop widget that monitors your **real-time AI usage quotas** — so you always know how much runway you have left.

Supports **ZCode**, **Claude**, **Codex**, and **Trae**. Works on **Windows** and **macOS**.

![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue)
![PySide6](https://img.shields.io/badge/GUI-PySide6-green)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow)
![Windows](https://img.shields.io/badge/platform-Windows-blue)
![macOS](https://img.shields.io/badge/platform-macOS-silver)
![No Tracking](https://img.shields.io/badge/privacy-no_tracking-brightgreen)

![Screenshot](docs/screenshot.png)

## 30-Second Start

```bash
git clone https://github.com/dunsberg/use-every-token-wisely.git
cd use-every-token-wisely
pip install -r requirements.txt    # pip3 on Mac
python main.py                     # python3 on Mac
```

That's it. The widget appears on your desktop. Drag it wherever you like.

> 📖 **New here?** See the **[detailed installation guide](INSTALL.md)** for step-by-step instructions, desktop shortcuts, and boot auto-launch.

## Features

- 📊 **Real quota data** — reads actual rate-limit percentages from each platform, not estimates
- ⏱️ **5-hour & 7-day windows** — each service shows both windows with exact reset dates
- 🔄 **Auto-refresh every 5 minutes** with a live countdown (turns purple in the last 10 seconds)
- 🪟 **Frameless, translucent, always-on-top** — a clean outline floating on your desktop
- 🎨 **Service-themed colors** — ZCode (blue), Claude (orange), Codex (black), Trae (green)
- 🔴 **Low-quota alert** — percentage text turns red when remaining drops below 10%
- 📂 **Collapsible cards** — fold/unfold any service from the right-click menu
- 🚀 **Launch on startup** — optional auto-launch on boot (Windows Startup folder / macOS LaunchAgent)
- 🖱️ **Drag to reposition** — position is saved automatically

## Quick Start

### Windows

```bash
pip install -r requirements.txt
python main.py
```

Or double-click the desktop shortcut:
```bash
python create_shortcut.py
```

### macOS

```bash
pip install -r requirements.txt
python3 main.py
```

Or create a desktop launcher:
```bash
python3 create_shortcut.py
```
This creates a `Use Every Token Wisely.command` file on your Desktop. The first time you run it, right-click → **Open** to bypass Gatekeeper.

## Supported Services

| Service | Color | Data Source |
|---------|-------|-------------|
| **ZCode** | Blue | BigModel quota API (`open.bigmodel.cn`) — reads API key from `~/.zcode/v2/config.json` |
| **Claude** | Orange | claude.ai OAuth usage API (`claude.ai/api/oauth/usage`) — reads token from `~/.claude/.credentials.json` |
| **Codex** | Black | Real `rate_limits` from local session files (`~/.codex/sessions/`) |
| **Trae** | Green | *Placeholder* — Trae's quota API is protected by ByteDance's `ttnet` signing. Shows plan tier (Free/Pro); full quota data coming when a public API is available |

All credentials are read from your existing local installs — **no API keys to configure, no manual entry**. The widget connects directly to each provider's official quota endpoint when needed; it does not route through any third-party server, does not collect telemetry, and your keys never leave your device.

## How Quotas Are Read

### ZCode (BigModel / GLM)
Reads `~/.zcode/v2/config.json` for the API key, then calls the BigModel monitor API to get real 5-hour (`TOKENS_LIMIT unit=3`) and weekly (`TOKENS_LIMIT unit=6`) utilization percentages with reset timestamps.

### Claude (claude.ai Pro)
Reads `~/.claude/.credentials.json` for the OAuth access token, then calls `claude.ai/api/oauth/usage` to get real session (5h) and weekly (7d) utilization, plus per-model limits (e.g. Fable). Uses a persistent cookie jar to pass Cloudflare's bot detection.

### Codex (OpenAI)
Parses the most recent session file in `~/.codex/sessions/` for the last `token_count` event, which contains real `rate_limits` with `used_percent` and `resets_at` for both 5-hour (`primary`) and 7-day (`secondary`) windows.

### Trae (ByteDance)
Reads the cached plan tier from Trae's local Electron storage (`AppData/Roaming/Trae CN/` on Windows, `~/Library/Application Support/Trae CN/` on macOS). Trae's live usage API (`api.trae.cn/trae/api/v2/pay/ide_user_ent_usage`) is protected by ByteDance's proprietary `ttnet` signing layer, which cannot be replicated in plain HTTP requests. Shows "Free Plan N/A" for free users; paid plan support is a work in progress.

## Usage

- **Left-drag** — move the widget; position is saved automatically
- **Right-click** — open the context menu:
  - **↻ Refresh now** — force a data refresh
  - **Service checkboxes** (ZCode / Claude / Codex / Trae) — expand/collapse each card
  - **🚀 Launch on startup** — toggle boot auto-launch
  - **ⓘ About** — project info
  - **✕ Quit** — exit

## Requirements

- Python 3.12+
- PySide6 (`pip install -r requirements.txt`)
- **Windows** (tested on Windows 11) or **macOS** (tested on macOS 14+)
- At least one of: ZCode, Claude Code, Codex, or Trae installed locally

## FAQ

<details>
<summary><b>The widget doesn't appear on screen</b></summary>

It may have spawned off-screen (common after changing monitors). Delete `config.json` in the project folder and restart — this resets the window position.
</details>

<details>
<summary><b>A service shows "No data" or "Cannot reach..."</b></summary>

Make sure the corresponding tool is installed and you've logged in at least once. The widget reads credentials from each tool's local config — if you haven't used the tool yet, there's nothing to read.
</details>

<details>
<summary><b>Claude keeps showing an error</b></summary>

Cloudflare occasionally blocks the usage API request. The widget retries automatically with backoff. If it persists for more than a few minutes, right-click → **Refresh now**. Make sure your Claude Code is updated and you're logged in.
</details>

<details>
<summary><b>Trae shows "Free Plan N/A"</b></summary>

This is expected. Trae's live quota API is protected by ByteDance's proprietary `ttnet` signing layer, which can't be replicated in a standalone Python script. The widget shows your cached plan tier instead. Paid-plan quota support is a work in progress.
</details>

<details>
<summary><b>The progress bars show different numbers than the tool's own UI</b></summary>

The widget refreshes every 5 minutes. The numbers may lag behind what you see in each tool's live UI. Right-click → **Refresh now** for an immediate update.
</details>

<details>
<summary><b>How do I uninstall?</b></summary>

If you enabled **Launch on startup**, right-click the widget and uncheck it first. Then just delete the project folder. On Windows, also delete the desktop shortcut if you created one.
</details>

## License

MIT License — see [LICENSE](LICENSE)

## Links

- **Source:** [github.com/dunsberg/use-every-token-wisely](https://github.com/dunsberg/use-every-token-wisely)
- **Issues:** [github.com/dunsberg/use-every-token-wisely/issues](https://github.com/dunsberg/use-every-token-wisely/issues)
