# Installation Guide

## Prerequisites

You need **Python 3.12 or newer** installed on your system.

### Check your Python version

```bash
python --version      # Windows
python3 --version     # macOS
```

If you don't have Python:
- **Windows:** Download from [python.org](https://www.python.org/downloads/) (check "Add Python to PATH" during install)
- **macOS:** `brew install python` or download from [python.org](https://www.python.org/downloads/)

You also need at least **one** of these AI tools installed locally (so the widget has data to read):
- [Zcode](https://z.ai)
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- [Codex](https://github.com/openai/codex)
- [Trae](https://www.trae.cn/)

---

## Step-by-step: Windows

### 1. Download the project

```bash
git clone https://github.com/dunsberg/use-every-token-wisely.git
cd use-every-token-wisely
```

Or download the ZIP from GitHub and extract it.

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

This installs PySide6 (the GUI framework). On Windows it also installs `pywin32` and `Pillow` for the desktop shortcut feature.

### 3. Run the widget

```bash
python main.py
```

The widget appears on your desktop. **Drag it** wherever you like — the position is saved automatically.

### 4. (Optional) Create a desktop shortcut

```bash
python create_shortcut.py
```

This creates a **⚡ Use Every Token Wisely** icon on your Desktop. Double-click to launch anytime.

### 5. (Optional) Enable launch on startup

Right-click the widget → **🚀 Launch on startup**. It will auto-start when you boot Windows.

---

## Step-by-step: macOS

### 1. Download the project

```bash
git clone https://github.com/dunsberg/use-every-token-wisely.git
cd use-every-token-wisely
```

### 2. Install dependencies

```bash
pip3 install -r requirements.txt
```

This installs PySide6 only. (The `pywin32`/`Pillow` packages are Windows-only and will be skipped automatically.)

### 3. Run the widget

```bash
python3 main.py
```

The widget appears on your desktop. **Drag it** to reposition.

### 4. (Optional) Create a desktop launcher

```bash
python3 create_shortcut.py
```

This creates a `Use Every Token Wisely.command` file on your Desktop. **The first time you open it**, right-click → **Open** to bypass macOS Gatekeeper.

### 5. (Optional) Enable launch on startup

Right-click the widget → **🚀 Launch on startup**. This creates a macOS LaunchAgent that auto-starts the widget on login.

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'PySide6'"
Run `pip install PySide6` (or `pip3 install PySide6` on Mac).

### The widget doesn't appear
It may have spawned off-screen. Delete `config.json` in the project folder and restart — this resets the window position to the default.

### A service shows "Cannot reach..." or "No data"
Make sure the corresponding tool is installed and you've logged in at least once:
- **Claude**: Run `claude` in terminal to initialize credentials
- **Zcode**: Open Zcode and log in
- **Codex**: Open Codex and start at least one session

### Claude shows "Cannot reach claude.ai/api/oauth/usage"
Cloudflare sometimes blocks automated requests. The widget retries automatically; if it persists, wait a few minutes and right-click → **Refresh now**.

### Trae shows "Free Plan N/A"
This is expected for free-tier Trae users. Trae's quota API is protected by ByteDance's proprietary signing layer. See the [README](README.md) for details.
