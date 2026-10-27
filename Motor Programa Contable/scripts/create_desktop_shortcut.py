#!/usr/bin/env python3
"""
Create / Update Desktop Shortcut for Sistema Contable.
Creates a 100% silent desktop shortcut with the official app icon.
"""

import os
import sys
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LAUNCH_VBS = REPO_ROOT / "launch_silent.vbs"
APP_ICO = REPO_ROOT / "app.ico"
DESKTOP_DIR = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
SHORTCUT_PATH = DESKTOP_DIR / "Sistema Contable.lnk"


def create_or_update_shortcut(shortcut_path=SHORTCUT_PATH):
    """Creates or updates a Windows shortcut configured to run 100% silently."""
    if not sys.platform.startswith("win"):
        print("Este script solo aplica para sistemas Windows.")
        return False

    wscript_exe = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "system32", "wscript.exe")
    vbs_path = str(LAUNCH_VBS)
    icon_path = f"{APP_ICO},0" if APP_ICO.exists() else ""
    cwd = str(REPO_ROOT)

    ps_script = f"""
    $wsh = New-Object -ComObject WScript.Shell
    $s = $wsh.CreateShortcut('{shortcut_path}')
    $s.TargetPath = '{wscript_exe}'
    $s.Arguments = '"{vbs_path}"'
    $s.WorkingDirectory = '{cwd}'
    $s.WindowStyle = 7
    $s.Description = 'CryptoTax Pro - Sistema Contable'
    if ('{icon_path}') {{
        $s.IconLocation = '{icon_path}'
    }}
    $s.Save()
    """

    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            check=True,
            capture_output=True,
            text=True
        )
        print(f"[OK] Acceso directo silencioso creado/actualizado en: {shortcut_path}")
        return True
    except Exception as e:
        print(f"[ERROR] No se pudo crear el acceso directo: {e}")
        return False


if __name__ == "__main__":
    create_or_update_shortcut()
