import os
import sys
import json
import time
import subprocess
import psutil
import urllib.request

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if 'scripts' in os.path.dirname(os.path.abspath(__file__)) else os.path.abspath('.')
LOCK_FILE = os.path.join(ROOT_DIR, 'system.lock')

# Flags to spawn detached process
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000
SPAWN_FLAGS = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW

print("1. Reading system.lock...")
pids = {}
if os.path.exists(LOCK_FILE):
    with open(LOCK_FILE, 'r') as f:
        pids = json.load(f)

old_b_pid = pids.get('backend_pid')
if old_b_pid and psutil.pid_exists(old_b_pid):
    print(f"Stopping old backend PID {old_b_pid}...")
    try:
        proc = psutil.Process(old_b_pid)
        for child in proc.children(recursive=True):
            try:
                child.kill()
            except Exception:
                pass
        proc.kill()
        proc.wait(timeout=3)
    except Exception as e:
        print(f"Error terminating old backend: {e}")

time.sleep(1)

# Check port 5000 is free
for conn in psutil.net_connections():
    if conn.laddr.port == 5000 and conn.status == 'LISTEN':
        print(f"Force killing process on port 5000 (PID {conn.pid})...")
        try:
            psutil.Process(conn.pid).kill()
        except Exception:
            pass

time.sleep(1)

print("2. Starting new backend process...")
backend_dir = os.path.join(ROOT_DIR, "webapp", "backend")
backend_log = open(os.path.join(backend_dir, "backend_runtime.log"), "a", encoding="utf-8")
py_exe = sys.executable or shutil.which("python") or "python"

env_vars = os.environ.copy()
env_vars["PORT"] = "5000"
env_vars["PYTHONUTF8"] = "1"
env_vars["PYTHONIOENCODING"] = "utf-8"

new_proc = subprocess.Popen(
    [py_exe, "app.py"],
    cwd=backend_dir,
    env=env_vars,
    stdin=subprocess.DEVNULL,
    stdout=backend_log,
    stderr=backend_log,
    creationflags=SPAWN_FLAGS,
    close_fds=False
)

print(f"New Backend PID: {new_proc.pid}")
pids['backend_pid'] = new_proc.pid

with open(LOCK_FILE, 'w') as f:
    json.dump(pids, f)

print("3. Waiting for backend to be ready...")
ready = False
for _ in range(25):
    time.sleep(0.5)
    try:
        req = urllib.request.urlopen("http://127.0.0.1:5000/health", timeout=1)
        if req.status == 200:
            ready = True
            break
    except Exception:
        pass

if ready:
    print("Backend is HEALTHY on port 5000!")
    # Test declarations route
    try:
        req = urllib.request.urlopen("http://127.0.0.1:5000/api/audit/declarations", timeout=1)
        print("Declarations route status:", req.status, req.read().decode('utf-8'))
    except Exception as e:
        print("Declarations route test error:", e)
else:
    print("Backend not ready yet, check logs.")
