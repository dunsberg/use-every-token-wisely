# Contributing

Thanks for your interest in improving this project! It's a small personal project, but all contributions are welcome.

## How to Submit a PR

1. **Fork** the repo on GitHub
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/use-every-token-wisely.git
   cd use-every-token-wisely
   ```
3. **Create a branch** for your changes:
   ```bash
   git checkout -b fix/short-description
   ```
4. **Make your changes** and test them:
   ```bash
   pip install -r requirements.txt
   python main.py
   ```
5. **Commit** with a clear message:
   ```bash
   git add -A
   git commit -m "Fix: short description of what changed"
   ```
6. **Push** to your fork:
   ```bash
   git push origin fix/short-description
   ```
7. **Open a PR** on GitHub — go to your fork, click "Compare & pull request"

## Code Style

- Python 3.12+ (uses `X | None` type hints, not `Optional[X]`)
- PySide6 for GUI
- Keep it simple — this is a small widget, not a framework
- Comments in English

## Project Structure

```
main.py                  # Entry point
providers/               # One file per service (claude.py, codex.py, etc.)
  base.py                # UsageData / WindowStats data classes + BaseProvider
ui/                      # All GUI code
  main_window.py         # Window, tray icon, menu, timers
  usage_card.py          # Service card widget + progress bars
  styles.py              # QSS stylesheets + color tokens
create_shortcut.py       # Desktop shortcut creator (Windows + macOS)
```

## Adding a New Service

1. Create `providers/yourservice.py` with a class extending `BaseProvider`
2. Implement `fetch()` to return a `UsageData` object
3. Add a color scheme in `ui/styles.py` under `SERVICE_COLORS`
4. Add it to the provider list in `ui/main_window.py`

## Reporting Bugs

Open an [issue](https://github.com/dunsberg/use-every-token-wisely/issues) with:
- What happened
- What you expected
- Which services you have installed
- Windows or macOS, Python version
