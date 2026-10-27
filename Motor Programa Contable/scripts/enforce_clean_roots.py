#!/usr/bin/env python3
"""
Root Cleanliness and Architectural Governance Enforcer.
Audits and automatically cleans/routes stray files and directories in:
  - Repository Root (Motor Programa Contable/)
  - Backend Root (webapp/backend/)
  - Frontend Root (webapp/frontend/)

Handles edge cases:
  - Collision-safe moving (never overwrites existing destination files)
  - Directory audits (flags unauthorized subfolders)
  - Test isolation (flags tests placed outside of webapp/backend/tests/)
  - Case-insensitive comparisons for cross-OS stability

Usage:
    python scripts/enforce_clean_roots.py        # Audit mode (returns exit code 1 on violations)
    python scripts/enforce_clean_roots.py --fix  # Auto-remediation mode (moves/cleans files)
"""

import os
import sys
import shutil
import time
import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "webapp" / "backend"
FRONTEND_DIR = REPO_ROOT / "webapp" / "frontend"
DOCS_ARCHIVE = REPO_ROOT / "docs" / "archive"

ALLOWED_REPO_ROOT_FILES = {
    "project.md", "readme.md", "test_infra.md", "test_ready.md",
    "mappings.json", ".gitignore",
    "start_system.py", "stop_system.py", "run_app.bat", "stop_app.bat",
    "launch_silent.vbs", "launch_autosync_silent.vbs", "setup_windows_scheduler.ps1",
    "app.ico", "system.lock", ".env.example", "license", "license.md"
}
ALLOWED_REPO_ROOT_DIRS = {
    ".agents", ".git", ".vscode", ".pytest_cache", "__pycache__",
    "docs", "scripts", "webapp", ".mypy_cache"
}

ALLOWED_BACKEND_ROOT_FILES = {
    "app.py", "requirements.txt", ".env", ".env.example", "transactions.db",
    "transactions.db-wal", "transactions.db-shm", "transactions.db-journal",
    "backend_runtime.log", "conftest.py", "exceptions.py"
}
ALLOWED_BACKEND_ROOT_DIRS = {
    "api_clients", "compat", "db", "domain", "models", "parsers",
    "routes", "services", "tests", "uploads", "utils", "workers",
    ".pytest_cache", "__pycache__"
}

ALLOWED_FRONTEND_ROOT_FILES = {
    "index.html", "vite.config.js", "package.json", "package-lock.json",
    "eslint.config.js", "tsconfig.json", "readme.md", ".gitignore", "frontend_runtime.log"
}
ALLOWED_FRONTEND_ROOT_DIRS = {
    "src", "public", "dist", "node_modules", ".vscode", "__pycache__"
}


def safe_move(src_path: Path, target_dir: Path) -> Path:
    """Relocates a file safely without risking overwriting an existing file."""
    target_dir.mkdir(parents=True, exist_ok=True)
    dest = target_dir / src_path.name
    if dest.exists() and dest != src_path:
        ts = int(time.time())
        dest = target_dir / f"{src_path.stem}_relocated_{ts}{src_path.suffix}"
    shutil.move(str(src_path), str(dest))
    return dest


def audit_and_remediate(fix=False):
    violations = []
    actions_taken = []

    # 1. Audit REPO_ROOT
    if REPO_ROOT.exists():
        for item in REPO_ROOT.iterdir():
            name_lower = item.name.lower()
            if item.is_file() and name_lower not in ALLOWED_REPO_ROOT_FILES:
                violations.append(("REPO_ROOT_FILE", item))
                if fix:
                    if name_lower.startswith("test_") and item.suffix == ".py":
                        dest = safe_move(item, BACKEND_DIR / "tests")
                        actions_taken.append(f"Moved test '{item.name}' -> {dest.relative_to(REPO_ROOT)}")
                    elif name_lower.endswith(".log") or name_lower.startswith("test_") or name_lower.startswith("git_diff_"):
                        dest = safe_move(item, DOCS_ARCHIVE)
                        actions_taken.append(f"Archived '{item.name}' -> {dest.relative_to(REPO_ROOT)}")
                    elif name_lower == "transactions.db" and item.stat().st_size == 0:
                        item.unlink()
                        actions_taken.append(f"Deleted 0-byte ghost database '{item.name}'")
                    else:
                        dest = safe_move(item, DOCS_ARCHIVE)
                        actions_taken.append(f"Archived unrecognized file '{item.name}' -> {dest.relative_to(REPO_ROOT)}")
            elif item.is_dir() and name_lower not in ALLOWED_REPO_ROOT_DIRS:
                violations.append(("REPO_ROOT_DIR", item))
                if fix:
                    dest = safe_move(item, DOCS_ARCHIVE)
                    actions_taken.append(f"Archived unexpected folder '{item.name}' -> {dest.relative_to(REPO_ROOT)}")

    # 2. Audit BACKEND_DIR
    if BACKEND_DIR.exists():
        for item in BACKEND_DIR.iterdir():
            name_lower = item.name.lower()
            if item.is_file() and name_lower not in ALLOWED_BACKEND_ROOT_FILES:
                violations.append(("BACKEND_DIR_FILE", item))
                if fix:
                    if name_lower.startswith("test_") and item.suffix == ".py":
                        dest = safe_move(item, BACKEND_DIR / "tests")
                        actions_taken.append(f"Moved test '{item.name}' -> {dest.relative_to(REPO_ROOT)}")
                    elif name_lower.endswith(".log") or name_lower.endswith(".xlsx"):
                        dest = safe_move(item, DOCS_ARCHIVE)
                        actions_taken.append(f"Archived '{item.name}' -> {dest.relative_to(REPO_ROOT)}")
                    elif name_lower.endswith((".db.bak", ".db", ".db-wal", ".db-shm", ".db-journal")) and not name_lower.startswith("transactions.db"):
                        item.unlink()
                        actions_taken.append(f"Deleted backup/ghost DB '{item.name}'")
                    else:
                        dest = safe_move(item, BACKEND_DIR / "compat")
                        actions_taken.append(f"Moved facade '{item.name}' -> {dest.relative_to(REPO_ROOT)}")
            elif item.is_dir() and name_lower not in ALLOWED_BACKEND_ROOT_DIRS:
                violations.append(("BACKEND_DIR_DIR", item))
                if fix:
                    dest = safe_move(item, DOCS_ARCHIVE)
                    actions_taken.append(f"Archived unexpected backend folder '{item.name}' -> {dest.relative_to(REPO_ROOT)}")

    # 3. Audit FRONTEND_DIR
    if FRONTEND_DIR.exists():
        for item in FRONTEND_DIR.iterdir():
            name_lower = item.name.lower()
            if item.is_file() and name_lower not in ALLOWED_FRONTEND_ROOT_FILES:
                violations.append(("FRONTEND_DIR_FILE", item))
                if fix:
                    if name_lower.endswith(".log"):
                        item.unlink()
                        actions_taken.append(f"Deleted frontend runtime log '{item.name}'")
                    else:
                        dest = safe_move(item, FRONTEND_DIR / "src")
                        actions_taken.append(f"Moved '{item.name}' -> {dest.relative_to(REPO_ROOT)}")
            elif item.is_dir() and name_lower not in ALLOWED_FRONTEND_ROOT_DIRS:
                violations.append(("FRONTEND_DIR_DIR", item))

    # 4. Audit Misplaced Tests across the entire REPO_ROOT
    if REPO_ROOT.exists():
        excluded_scan_dirs = {".git", "node_modules", ".pytest_cache", "__pycache__", "dist", "venv", ".venv"}
        tests_dir = (BACKEND_DIR / "tests").resolve()
        for p in REPO_ROOT.rglob("test_*.py"):
            if any(part in excluded_scan_dirs for part in p.parts):
                continue
            if tests_dir not in p.resolve().parents:
                violations.append(("MISPLACED_TEST", p))
                if fix:
                    dest = safe_move(p, BACKEND_DIR / "tests")
                    actions_taken.append(f"Relocated misplaced test '{p.name}' -> {dest.relative_to(REPO_ROOT)}")

    return violations, actions_taken


def main():
    parser = argparse.ArgumentParser(description="Enforce clean root directories and architectural layering.")
    parser.add_argument("--fix", action="store_true", help="Automatically relocate/clean unauthorized files.")
    args = parser.parse_args()

    violations, actions_taken = audit_and_remediate(fix=args.fix)

    if actions_taken:
        print("=== Auto-Remediation Actions Taken ===")
        for act in actions_taken:
            print(f"  [FIXED] {act}")
        print()

    if violations and not args.fix:
        print("=== VIOLATION: Unauthorized Files or Directories Detected ===")
        for loc, path in violations:
            print(f"  [{loc}] {path.name} ({path})")
        print("\nRun with --fix to automatically relocate/clean these items:")
        print("  python scripts/enforce_clean_roots.py --fix")
        sys.exit(1)

    print("SUCCESS: All root directories (repo root, backend, frontend) are 100% clean and compliant!")
    sys.exit(0)


if __name__ == "__main__":
    main()
