# ⚡Use Every Token Wisely⚡

A small desktop widget that shows your AI usage quotas for Claude, ChatGPT, ZCode, Kimi, and Trae — so you have a rough idea of how much you have left before the next reset.

It's a personal project, fairly rough around the edges, but it works for my daily use. Feel free to try it or adapt it.

![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue)
![PySide6](https://img.shields.io/badge/GUI-PySide6-green)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow)
![Windows](https://img.shields.io/badge/platform-Windows-blue)
![macOS](https://img.shields.io/badge/platform-macOS-silver)

![Screenshot](docs/screenshot.png)

## Privacy

The widget runs locally. It reads credentials from each tool's own config files (the same files already on your disk) and connects only to the official provider endpoints to check quotas. No third-party servers, no telemetry, no tracking. Your keys don't leave your machine.

## Getting Started

```bash
git clone https://github.com/dunsberg/use-every-token-wisely.git
cd use-every-token-wisely
pip install -r requirements.txt
python main.py                     # python3 on Mac
```

For step-by-step instructions, desktop shortcuts, and boot auto-launch, see **[INSTALL.md](INSTALL.md)**.

## What It Does

- Shows 5-hour and 7-day usage windows for each service, with reset countdowns
- Refreshes automatically every 5 minutes (manual refresh via right-click)
- Translucent, frameless, stays on top — drag it wherever you want
- Collapsible cards — hide services you don't use
- Percentage text turns red when you're below 10% remaining

## Supported Services

| Service | Status | How It Reads Quotas |
|---------|--------|---------------------|
| **Claude** | Working | claude.ai OAuth usage API using credentials from local files |
| **ChatGPT** | Working | ChatGPT codex/usage API using the OAuth token from `~/.codex/auth.json` |
| **ZCode** | Working | BigModel quota API using the API key from `~/.zcode/v2/config.json` |
| **Kimi** | Working | Kimi membership API using the access token from `~/.kimi-desktop/` |
| **Trae** | Limited | Shows plan tier only — Trae's quota API uses proprietary signing that this widget can't replicate yet |

No API keys to configure — credentials are read from each tool's existing local install.

## Usage

- **Drag** to move the widget (position is saved)
- **Right-click** for menu: refresh, collapse/expand services, launch on startup, about, quit

## Requirements

- Python 3.12+ and PySide6
- Windows or macOS
- At least one of the supported tools installed and logged in

## Known Limitations

- Claude's API is behind Cloudflare; occasional failures can happen, but the widget retries automatically
- Trae quota data is not available (proprietary API signing)
- Codex's rate limit structure has changed over time; the widget adapts but may miss windows if the API changes again
- macOS support is implemented but not as thoroughly tested as Windows

Contributions and bug reports are welcome at the [issues page](https://github.com/dunsberg/use-every-token-wisely/issues).

## License

MIT — see [LICENSE](LICENSE)
