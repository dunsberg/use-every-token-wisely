"""Create a desktop shortcut for the usage monitor widget."""

import os
import sys
from pathlib import Path

try:
    import winreg
except ImportError:
    winreg = None

import pythoncom
from win32com.shell import shell

# Paths
PROJECT_DIR = Path(__file__).resolve().parent
PYTHON_EXE = sys.executable
MAIN_PY = PROJECT_DIR / "main.py"
SHORTCUT_PATH = Path.home() / "Desktop" / "Use Every Token Wisely.lnk"
ICON_PATH = PROJECT_DIR / "icon.ico"


def main():
    # Create a simple .ico icon if it doesn't exist
    if not ICON_PATH.exists():
        _create_icon()

    pythoncom.CoInitialize()
    shell_link = pythoncom.CoCreateInstance(
        shell.CLSID_ShellLink,
        None,
        pythoncom.CLSCTX_INPROC_SERVER,
        shell.IID_IShellLink,
    )
    shell_link.SetPath(str(PYTHON_EXE))
    shell_link.SetArguments(f'"{MAIN_PY}"')
    shell_link.SetWorkingDirectory(str(PROJECT_DIR))
    shell_link.SetDescription("AI usage monitor for ZCODE, Claude, Codex, TRAE")
    if ICON_PATH.exists():
        shell_link.SetIconLocation(str(ICON_PATH), 0)

    persist_file = shell_link.QueryInterface(pythoncom.IID_IPersistFile)
    persist_file.Save(str(SHORTCUT_PATH), 0)

    print(f"Shortcut created: {SHORTCUT_PATH}")
    print(f"  Target: {PYTHON_EXE} \"{MAIN_PY}\"")
    print(f"  WorkDir: {PROJECT_DIR}")
    print("Double-click the desktop icon to launch.")


def _create_icon():
    """Generate a simple lightning-bolt icon."""
    try:
        from PIL import Image, ImageDraw

        img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Yellow lightning bolt
        points = [(140, 20), (90, 140), (120, 140), (100, 236), (180, 100),
                  (140, 100)]
        draw.polygon(points, fill=(255, 204, 0, 255))
        img.save(str(ICON_PATH), format="ICO", sizes=[(256, 256), (48, 48), (32, 32), (16, 16)])
        print(f"Icon created: {ICON_PATH}")
    except ImportError:
        # No PIL — skip icon, shortcut will use default Python icon
        print("PIL not installed, using default icon")


if __name__ == "__main__":
    main()
