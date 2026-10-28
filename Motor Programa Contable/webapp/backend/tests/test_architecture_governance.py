"""
test_architecture_governance.py - Architectural Governance & Clean Architecture Guard.
Automates enforcement of Clean Architecture rules:
1. Max file length strictly <= 500 lines (target <= 450 lines) for all productive code.
2. Clean root directories across repo root, backend root, and frontend root.
3. Layered dependency boundaries (routes -> services -> db/connection).
"""
import os
import sys
import warnings
from pathlib import Path
import pytest

TESTS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = TESTS_DIR.parent
REPO_ROOT = BACKEND_DIR.parent.parent
FRONTEND_DIR = REPO_ROOT / "webapp" / "frontend"


def test_clean_architecture_file_length_limits():
    """
    Asserts that no productive Python or JS/JSX file exceeds the Clean Architecture
    strict limit of 500 lines (target <= 450 lines).
    """
    excluded_dirs = {
        ".git", "node_modules", "dist", "build", ".venv", "venv",
        "__pycache__", ".pytest_cache", ".mypy_cache", ".agents",
        "docs", "backups", "tests"
    }

    hard_violations = []
    soft_warnings = []
    
    # 1. Check Backend productive files
    for root, dirs, files in os.walk(BACKEND_DIR):
        dirs[:] = [d for d in dirs if d not in excluded_dirs]
        for f in files:
            if f.endswith(".py") and not f.startswith("test_"):
                fpath = Path(root) / f
                with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
                    line_count = sum(1 for _ in fp)
                if line_count > 500:
                    hard_violations.append((fpath.relative_to(REPO_ROOT), line_count))
                elif line_count > 450:
                    soft_warnings.append((fpath.relative_to(REPO_ROOT), line_count))

    # 2. Check Frontend productive files
    src_dir = FRONTEND_DIR / "src"
    if src_dir.exists():
        for root, dirs, files in os.walk(src_dir):
            dirs[:] = [d for d in dirs if d not in excluded_dirs]
            for f in files:
                if f.endswith((".js", ".jsx", ".ts", ".tsx")):
                    fpath = Path(root) / f
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
                        line_count = sum(1 for _ in fp)
                    if line_count > 500:
                        hard_violations.append((fpath.relative_to(REPO_ROOT), line_count))
                    elif line_count > 450:
                        soft_warnings.append((fpath.relative_to(REPO_ROOT), line_count))

    if soft_warnings:
        warn_msg = (
            f"Advisory target warning: {len(soft_warnings)} files between 450 and 500 lines:\n" +
            "\n".join(f"  {path}: {count} lines" for path, count in soft_warnings)
        )
        warnings.warn(warn_msg, UserWarning)

    assert not hard_violations, (
        f"Found {len(hard_violations)} files strictly exceeding the 500-line limit:\n" +
        "\n".join(f"  {path}: {count} lines" for path, count in hard_violations)
    )


def test_enforce_clean_roots_compliance():
    """
    Validates that the repository root, backend root, and frontend root
    contain zero unauthorized stray files using enforce_clean_roots.py.
    """
    scripts_dir = REPO_ROOT / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    import enforce_clean_roots
    violations, _ = enforce_clean_roots.audit_and_remediate(fix=False)

    assert not violations, (
        f"Detected {len(violations)} root directory violations:\n" +
        "\n".join(f"  [{loc}] {p}" for loc, p in violations)
    )


def test_layer_dependency_integrity():
    """
    Validates that services do not import directly from the HTTP routes layer.
    """
    services_dir = BACKEND_DIR / "services"
    forbidden_imports = []

    for py_file in services_dir.glob("*.py"):
        with open(py_file, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f, start=1):
                clean = line.strip()
                if clean.startswith("from routes") or clean.startswith("import routes"):
                    forbidden_imports.append((py_file.name, i, clean))

    assert not forbidden_imports, (
        "Clean Architecture violation: services cannot depend on routes:\n" +
        "\n".join(f"  {f}:{line} -> {code}" for f, line, code in forbidden_imports)
    )
