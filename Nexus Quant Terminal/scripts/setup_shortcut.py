import os
import shutil
import subprocess

def setup():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 1. Icons and Scripts
    nexus_ico = os.path.join(root_dir, "static", "icons", "nexus_quant_icon.ico")
    if not os.path.exists(nexus_ico):
        nexus_ico = os.path.join(root_dir, "static", "favicon.ico")

    bat_path = os.path.join(root_dir, "run_nexus_terminal.bat")
    
    # Batch content
    bat_content = f"""@echo off
title Nexus Quant Terminal - Institutional Algorithmic Platform
cd /d "%~dp0"
echo Starting Nexus Quant Terminal Backend...
start cmd /c "python app.py"
echo Waiting for server to start...
set /a retries=0
:WAIT_SERVER
curl.exe -s -o NUL -m 1 http://127.0.0.1:5001/
if %ERRORLEVEL% equ 0 goto SERVER_READY
set /a retries+=1
if %retries% geq 25 goto SERVER_READY
python -c "import time; time.sleep(0.1)"
goto WAIT_SERVER

:SERVER_READY
echo Opening Nexus Quant Terminal in browser...
start "" "http://127.0.0.1:5001"
exit
"""
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(bat_content)
    print(f"  [OK] Batch script updated at {bat_path}")

    # 2. Desktop Shortcut Management
    desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
    old_shortcuts = [
        os.path.join(desktop, "Binarias Simulator.lnk"),
        os.path.join(desktop, "BinSim.lnk")
    ]
    
    for old_s in old_shortcuts:
        if os.path.exists(old_s):
            try:
                os.remove(old_s)
                print(f"  [CLEANED] Removed legacy shortcut: {os.path.basename(old_s)}")
            except Exception as e:
                print(f"  [WARN] Could not remove {old_s}: {e}")

    new_shortcut_path = os.path.join(desktop, "Nexus Quant Terminal.lnk")
    if os.path.exists(new_shortcut_path):
        try:
            os.remove(new_shortcut_path)
        except Exception:
            pass

    ico_to_use = os.path.join(root_dir, "static", "icons", "nexus_squircle_final.ico")
    if not os.path.exists(ico_to_use):
        ico_to_use = nexus_ico

    print("Creating Nexus Quant Terminal Desktop Shortcut via Windows Script Host...")
    vbs_path = os.path.join(root_dir, "_temp_shortcut.vbs")
    vbs_content = f"""Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = "{new_shortcut_path}"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "{bat_path}"
oLink.WorkingDirectory = "{root_dir}"
oLink.Description = "Nexus Quant Terminal - Institutional Algorithmic Platform"
oLink.IconLocation = "{ico_to_use}, 0"
oLink.Save
"""
    with open(vbs_path, "w", encoding="utf-8") as f:
        f.write(vbs_content)

    try:
        subprocess.run(["cscript", "//nologo", vbs_path], check=True)
        print(f"  [OK] Successfully created Desktop Shortcut: {new_shortcut_path}")
        print(f"  [ICON] Linked to: {ico_to_use}")
        
        # Notify Windows Shell and refresh cache
        import ctypes
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
        subprocess.run(["ie4uinit.exe", "-show"], capture_output=True)
    except Exception as e:
        print(f"  [ERROR] Failed to create shortcut: {e}")
    finally:
        if os.path.exists(vbs_path):
            try:
                os.remove(vbs_path)
            except Exception:
                pass

if __name__ == "__main__":
    setup()
