"""Create a desktop shortcut for the usage monitor widget (cross-platform).

- Windows: creates a .lnk shortcut via pywin32 COM, with a lightning-bolt icon.
- macOS: creates a .command shell script on the Desktop with execute permission.
"""

import os
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
PYTHON_EXE = sys.executable
MAIN_PY = PROJECT_DIR / "main.py"


def main():
    if sys.platform == "darwin":
        _create_mac_shortcut()
    else:
        _create_windows_shortcut()


# --------------------------------------------------------------------------
# macOS
# --------------------------------------------------------------------------
def _create_mac_shortcut():
    shortcut_path = Path.home() / "Desktop" / "Use Every Token Wisely.command"
    script = f"""#!/bin/bash
cd "{PROJECT_DIR}"
"{PYTHON_EXE}" "{MAIN_PY}"
"""
    shortcut_path.write_text(script, encoding="utf-8")
    os.chmod(shortcut_path, 0o755)  # make executable
    print(f"Shortcut created: {shortcut_path}")
    print("Double-click the .command file to launch.")
    print("(You may need to right-click → Open the first time to bypass Gatekeeper.)")


# --------------------------------------------------------------------------
# Windows
# --------------------------------------------------------------------------
def _create_windows_shortcut():
    import pythoncom
    from win32com.shell import shell

    shortcut_path = Path.home() / "Desktop" / "Use Every Token Wisely.lnk"
    icon_path = PROJECT_DIR / "icon.ico"

    if not icon_path.exists():
        _create_icon_windows(icon_path)

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
    if icon_path.exists():
        shell_link.SetIconLocation(str(icon_path), 0)

    persist_file = shell_link.QueryInterface(pythoncom.IID_IPersistFile)
    persist_file.Save(str(shortcut_path), 0)

    print(f"Shortcut created: {shortcut_path}")
    print("Double-click the desktop icon to launch.")


def _create_icon_windows(icon_path: Path):
    """Generate a simple lightning-bolt icon (Windows only, needs Pillow)."""
    try:
        from PIL import Image, ImageDraw

        img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        points = [(140, 20), (90, 140), (120, 140), (100, 236),
                  (180, 100), (140, 100)]
        draw.polygon(points, fill=(255, 204, 0, 255))
        img.save(str(icon_path), format="ICO",
                 sizes=[(256, 256), (48, 48), (32, 32), (16, 16)])
        print(f"Icon created: {icon_path}")
    except ImportError:
        print("Pillow not installed, using default icon")


if __name__ == "__main__":
    main()
