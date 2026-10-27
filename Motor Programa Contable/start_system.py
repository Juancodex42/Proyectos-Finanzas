import subprocess
import time
import webbrowser
import os
import sys
import json
import psutil

import shutil

# Hide Console Window & Process Flags
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000
SPAWN_FLAGS = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW

def get_silent_startupinfo():
    if sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE
        return si
    return None

def get_node_executable():
    node_which = shutil.which("node")
    if node_which and os.path.exists(node_which):
        return node_which
    prog_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    default_node = os.path.join(prog_files, "nodejs", "node.exe")
    if os.path.exists(default_node):
        return default_node
    return "node"

def ensure_desktop_shortcut(root_dir):
    """Garantiza que el acceso directo del escritorio siempre exista y corra 100% silencioso."""
    if not sys.platform.startswith("win"):
        return
    try:
        from pathlib import Path
        desktop = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
        shortcut = desktop / "Sistema Contable.lnk"
        launch_vbs = os.path.join(root_dir, "launch_silent.vbs")
        app_ico = os.path.join(root_dir, "app.ico")
        wscript_exe = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "system32", "wscript.exe")

        icon_clause = f"$s.IconLocation = '{app_ico},0';" if os.path.exists(app_ico) else ""
        ps_cmd = (
            f"$wsh = New-Object -ComObject WScript.Shell; "
            f"$s = $wsh.CreateShortcut('{shortcut}'); "
            f"$s.TargetPath = '{wscript_exe}'; "
            f"$s.Arguments = '\"{launch_vbs}\"'; "
            f"$s.WorkingDirectory = '{root_dir}'; "
            f"$s.WindowStyle = 7; "
            f"$s.Description = 'CryptoTax Pro - Sistema Contable'; "
            f"{icon_clause} "
            f"$s.Save();"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True,
            timeout=5,
            creationflags=CREATE_NO_WINDOW
        )
    except Exception:
        pass


def check_already_running(lock_file):
    if not os.path.exists(lock_file):
        return False, False, False

    backend_running = False
    frontend_running = False

    try:
        with open(lock_file, 'r') as f:
            pids = json.load(f)
        
        # Check backend
        if 'backend_pid' in pids:
            b_pid = pids['backend_pid']
            if psutil.pid_exists(b_pid):
                try:
                    proc = psutil.Process(b_pid)
                    cmd = " ".join(proc.cmdline()).lower()
                    if "python" in cmd and "app.py" in cmd:
                        backend_running = True
                except Exception:
                    pass
        
        # Check frontend
        if 'frontend_pid' in pids:
            f_pid = pids['frontend_pid']
            if psutil.pid_exists(f_pid):
                try:
                    proc = psutil.Process(f_pid)
                    cmd = " ".join(proc.cmdline()).lower()
                    if "node" in cmd or "npm" in cmd or "vite" in cmd:
                        frontend_running = True
                except Exception:
                    pass
    except Exception:
        pass

    return backend_running, frontend_running, (backend_running and frontend_running)

def load_ports(root_dir):
    backend_port = 5000
    frontend_port = 5173
    env_path = os.path.join(root_dir, "webapp", "backend", ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if '=' in line and not line.strip().startswith('#'):
                        parts = line.split('=', 1)
                        k = parts[0].strip()
                        v = parts[1].strip().strip("'").strip('"')
                        if k == 'BACKEND_PORT':
                            backend_port = int(v)
                        elif k == 'FRONTEND_PORT':
                            frontend_port = int(v)
        except Exception:
            pass
    return backend_port, frontend_port

def get_python_executable():
    """Locate python executable dynamically without user-specific hardcoded paths."""
    root_dir = os.path.dirname(os.path.abspath(__file__))
    venv_py = os.path.join(root_dir, '.venv', 'Scripts', 'python.exe')
    if os.path.exists(venv_py):
        return venv_py
    if sys.executable and os.path.exists(sys.executable):
        return sys.executable
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        py311 = os.path.join(local_app_data, "Programs", "Python", "Python311", "python.exe")
        if os.path.exists(py311):
            return py311
    system_py = shutil.which("python") or shutil.which("python3")
    if system_py:
        return system_py
    return "python" 

def start_hidden():
    ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
    lock_file = os.path.join(ROOT_DIR, 'system.lock')
    
    backend_port, frontend_port = load_ports(ROOT_DIR)
    
    backend_running, frontend_running, both_running = check_already_running(lock_file)
    
    if both_running:
        print("El sistema contable ya se encuentra en ejecución.")
        webbrowser.open(f"http://localhost:{frontend_port}")
        sys.exit(0)
        
    print("Iniciando Sistema Contable (Modo Silencioso)...")
    
    # Asegurar que el acceso directo del escritorio siempre exista y corra en silencio
    ensure_desktop_shortcut(ROOT_DIR)
    
    # 0. Update documentation dynamically in background (non-blocking)
    try:
        py_exe = get_python_executable()
        docs_script = os.path.join(ROOT_DIR, "scripts", "update_docs.py")
        if os.path.exists(docs_script):
            subprocess.Popen(
                [py_exe, docs_script],
                cwd=ROOT_DIR,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=SPAWN_FLAGS,
                startupinfo=get_silent_startupinfo()
            )
    except Exception as e:
        print(f"No se pudo actualizar la documentación: {e}")
    
    pids = {}
    if os.path.exists(lock_file):
        try:
            with open(lock_file, 'r') as f:
                pids = json.load(f)
        except Exception:
            pass

    # 1. Start Backend if not running
    if not backend_running:
        py_exe = get_python_executable()
        backend_dir = os.path.join(ROOT_DIR, "webapp", "backend")
        backend_log = open(os.path.join(backend_dir, "backend_runtime.log"), "a", encoding="utf-8")
        env_vars = os.environ.copy()
        env_vars["PORT"] = str(backend_port)
        env_vars["PYTHONUTF8"] = "1"
        env_vars["PYTHONIOENCODING"] = "utf-8"
        env_vars["PYTHONUNBUFFERED"] = "1"
        backend_proc = subprocess.Popen(
            [py_exe, "app.py"],
            cwd=backend_dir,
            env=env_vars,
            stdin=subprocess.DEVNULL,
            stdout=backend_log,
            stderr=backend_log,
            creationflags=SPAWN_FLAGS,
            startupinfo=get_silent_startupinfo()
        )
        backend_log.close()
        print(f"Backend PID: {backend_proc.pid} (Port: {backend_port}, Py: {py_exe})")
        pids['backend_pid'] = backend_proc.pid
    else:
        print("Backend ya se encuentra en ejecución.")

    # 2. Start Frontend if not running
    if not frontend_running:
        frontend_dir = os.path.join(ROOT_DIR, "webapp", "frontend")
        frontend_log = open(os.path.join(frontend_dir, "frontend_runtime.log"), "a", encoding="utf-8")
        node_exe = get_node_executable()
        vite_bin = os.path.join(frontend_dir, "node_modules", "vite", "bin", "vite.js")
        if os.path.exists(vite_bin):
            frontend_cmd = [node_exe, vite_bin, "--port", str(frontend_port)]
        else:
            frontend_cmd = ["npm.cmd", "run", "dev", "--", "--port", str(frontend_port)]
        frontend_env = os.environ.copy()
        frontend_env["CI"] = "true"
        frontend_proc = subprocess.Popen(
            frontend_cmd,
            cwd=frontend_dir,
            env=frontend_env,
            stdin=subprocess.DEVNULL,
            stdout=frontend_log,
            stderr=frontend_log,
            creationflags=SPAWN_FLAGS,
            startupinfo=get_silent_startupinfo()
        )
        frontend_log.close()
        print(f"Frontend PID: {frontend_proc.pid} (Port: {frontend_port})")
        pids['frontend_pid'] = frontend_proc.pid
    else:
        print("Frontend ya se encuentra en ejecución.")
    
    # SAVE PIDS
    with open(lock_file, 'w') as f:
        json.dump(pids, f)
        
    # 3. Wait for servers to spin up (active health check loop)
    import urllib.request
    backend_url = f"http://127.0.0.1:{backend_port}/health"
    frontend_url = f"http://127.0.0.1:{frontend_port}"
    
    t_start = time.time()
    while time.time() - t_start < 15.0:
        backend_ready = False
        frontend_ready = False
        try:
            with urllib.request.urlopen(backend_url, timeout=0.3) as resp:
                if resp.status == 200:
                    backend_ready = True
        except Exception:
            pass
            
        try:
            with urllib.request.urlopen(frontend_url, timeout=0.3) as resp:
                if resp.status in (200, 304):
                    frontend_ready = True
        except Exception:
            pass
            
        if backend_ready and frontend_ready:
            break
        time.sleep(0.1)
    
    # 4. Open Browser safely
    url = f"http://localhost:{frontend_port}"
    webbrowser.open(url)

if __name__ == "__main__":
    start_hidden()
