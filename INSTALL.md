# Installation

## Prerequisites

Python 3.12 or newer. If you don't have it:
- **Windows:** [python.org](https://www.python.org/downloads/) — check "Add Python to PATH" during install
- **macOS:** `brew install python` or [python.org](https://www.python.org/downloads/)

You'll also need at least one of these installed and logged in: [ZCode](https://z.ai), [Claude Code](https://docs.anthropic.com/en/docs/claude-code), [Codex](https://github.com/openai/codex), or [Trae](https://www.trae.cn/).

## Windows

```bash
git clone https://github.com/dunsberg/use-every-token-wisely.git
cd use-every-token-wisely
pip install -r requirements.txt
python main.py
```

For a desktop shortcut (so you don't need the terminal each time):

```bash
python create_shortcut.py
```

To auto-start on boot: right-click the widget → **Launch on startup**.

## macOS

```bash
git clone https://github.com/dunsberg/use-every-token-wisely.git
cd use-every-token-wisely
pip3 install -r requirements.txt
python3 main.py
```

For a desktop launcher:

```bash
python3 create_shortcut.py
```

This creates a `.command` file. The first time, right-click → **Open** to bypass Gatekeeper.

## Troubleshooting

**Widget doesn't appear** — It may be off-screen. Delete `config.json` and restart to reset the position.

**"No module named 'PySide6'"** — Run `pip install PySide6` (`pip3` on Mac).

**A service shows "No data"** — Make sure that tool is installed and you've logged in at least once. The widget reads credentials from each tool's local config, so if you haven't used it yet, there's nothing to read.

**Claude keeps erroring** — Cloudflare sometimes blocks the request. The widget retries on its own; if it's stuck, try right-click → **Refresh now**.

**Trae shows "Free Plan N/A"** — Expected. Trae's quota API uses proprietary signing this widget can't replicate yet.
