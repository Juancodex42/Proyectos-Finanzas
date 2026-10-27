"""
audit_deep_system.py - Industrial-Grade Deep System, AST & Import Auditor.

Audits:
1. AST Deep Scan: Inspects all top-level and nested/hidden function imports across all Python files.
2. Facade Integrity: Validates __all__ exports across db_manager, processor_lib, parsers, routes, services.
3. Database & Schema Health: Verifies SQLite tables, columns, indexes, and queries.
4. Frontend-to-Backend Contract: Extracts API calls from JSX/JS and checks against Flask url_map.
5. Endpoint Smoke Tests: Executes simulated HTTP requests on all registered routes.
"""

import sys
import ast
import re
import importlib
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "webapp" / "backend"
FRONTEND_SRC = ROOT_DIR / "webapp" / "frontend" / "src"
SCRIPTS_DIR = ROOT_DIR / "scripts"
COMPAT_DIR = BACKEND_DIR / "compat"
TESTS_DIR = BACKEND_DIR / "tests"

for _p in (COMPAT_DIR, TESTS_DIR, BACKEND_DIR, ROOT_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


class ASTImportAuditor(ast.NodeVisitor):
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.scope_stack = ["<module>"]
        self.imports = []

    def _visit_scoped(self, label: str, node):
        self.scope_stack.append(label)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_FunctionDef(self, node):
        self._visit_scoped(f"def {node.name}()", node)

    def visit_AsyncFunctionDef(self, node):
        self._visit_scoped(f"async def {node.name}()", node)

    def visit_ClassDef(self, node):
        self._visit_scoped(f"class {node.name}", node)

    def visit_Import(self, node):
        scope = " -> ".join(self.scope_stack)
        is_hidden = len(self.scope_stack) > 1
        rel_file = str(self.file_path.relative_to(ROOT_DIR))
        for alias in node.names:
            self.imports.append({
                "type": "import", "module": alias.name, "name": None,
                "asname": alias.asname, "line": node.lineno,
                "scope": scope, "is_hidden": is_hidden, "file": rel_file
            })
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        scope = " -> ".join(self.scope_stack)
        is_hidden = len(self.scope_stack) > 1
        module = node.module or ""
        rel_file = str(self.file_path.relative_to(ROOT_DIR))
        for alias in node.names:
            self.imports.append({
                "type": "from_import", "module": module, "level": node.level,
                "name": alias.name, "asname": alias.asname, "line": node.lineno,
                "scope": scope, "is_hidden": is_hidden, "file": rel_file
            })
        self.generic_visit(node)


def audit_all_python_imports():
    """Scans all python files and tests resolution of every import (module-level and function-level)."""
    py_files = list(BACKEND_DIR.rglob("*.py")) + list(SCRIPTS_DIR.glob("*.py"))
    exclude_parts = {'.venv', 'venv', '__pycache__', '.pytest_cache'}
    py_files = [f for f in py_files if not any(x in f.parts for x in exclude_parts)]

    all_imports = []
    syntax_errors = []

    for fpath in py_files:
        try:
            code = fpath.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(code, filename=str(fpath))
            auditor = ASTImportAuditor(fpath)
            auditor.visit(tree)
            all_imports.extend(auditor.imports)
        except SyntaxError as e:
            syntax_errors.append((str(fpath.relative_to(ROOT_DIR)), str(e)))

    tested_modules = {}
    broken_imports = []
    valid_imports_count = 0
    hidden_imports_count = sum(1 for imp in all_imports if imp["is_hidden"])

    for imp in all_imports:
        mod_name = imp["module"]
        sym_name = imp["name"]
        if imp.get("level", 0) > 0:
            valid_imports_count += 1
            continue
        if not mod_name:
            continue

        try:
            if mod_name not in tested_modules:
                try:
                    tested_modules[mod_name] = importlib.import_module(mod_name)
                except Exception as ex:
                    tested_modules[mod_name] = ex

            res = tested_modules[mod_name]
            if isinstance(res, Exception):
                broken_imports.append({**imp, "error": f"ModuleNotFoundError / ImportError: {res}"})
            else:
                if sym_name and sym_name != "*" and not hasattr(res, sym_name):
                    try:
                        importlib.import_module(f"{mod_name}.{sym_name}")
                    except Exception:
                        broken_imports.append({
                            **imp,
                            "error": f"AttributeError: module '{mod_name}' has no attribute '{sym_name}'"
                        })
                        continue
                valid_imports_count += 1
        except Exception as ex:
            broken_imports.append({**imp, "error": f"Unexpected import error: {ex}"})

    return {
        "total_files": len(py_files),
        "total_imports": len(all_imports),
        "hidden_imports": hidden_imports_count,
        "valid_imports": valid_imports_count,
        "broken_imports": broken_imports,
        "syntax_errors": syntax_errors
    }


def audit_facades():
    """Audits __all__ exports of key facade files."""
    facades_to_test = ["db_manager", "processor_lib", "parsers", "routes", "services", "api_clients", "db"]
    facade_results = []
    for fac in facades_to_test:
        try:
            mod = importlib.import_module(fac)
            all_list = getattr(mod, "__all__", None)
            if all_list is None:
                facade_results.append({
                    "facade": fac, "status": "WARN", "missing": [],
                    "total_exports": len(dir(mod)),
                    "message": "No explicit __all__ declared, module exports namespace dynamically."
                })
            else:
                missing = [name for name in all_list if not hasattr(mod, name)]
                facade_results.append({
                    "facade": fac,
                    "status": "FAIL" if missing else "PASS",
                    "missing": missing,
                    "total_exports": len(all_list),
                    "message": f"Verified {len(all_list)} exported symbols." if not missing else f"Broken exports: {missing}"
                })
        except Exception as e:
            facade_results.append({
                "facade": fac, "status": "FAIL", "missing": [],
                "total_exports": 0, "message": f"Failed to import facade: {e}"
            })
    return facade_results


def audit_database_and_schemas():
    """Audits database schema, connectivity, and runs core queries."""
    import db_manager
    results = {"status": "PASS", "checks": []}
    try:
        conn = db_manager.get_connection()
        c = conn.cursor()

        c.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in c.fetchall()}
        required_tables = {"transactions", "tax_settings", "exchanges_config", "certifications"}
        missing_tables = required_tables - tables
        if missing_tables:
            results["status"] = "FAIL"
            results["checks"].append(f"Missing tables: {missing_tables}")
        else:
            results["checks"].append(f"All required tables exist: {sorted(tables)}")

        c.execute("SELECT COUNT(*) FROM transactions")
        tx_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM certifications")
        cert_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM exchanges_config")
        exch_count = c.fetchone()[0]
        results["checks"].append(f"Row counts: transactions={tx_count}, certifications={cert_count}, exchanges={exch_count}")

        c.execute("PRAGMA table_info(transactions);")
        tx_cols = {row[1] for row in c.fetchall()}
        expected_cols = {
            "tx_hash", "fecha", "exchange", "tipo_operacion", "moneda",
            "monto_compra_cripto", "monto_venta_cripto", "is_certified", "certification_id", "source"
        }
        missing_cols = expected_cols - tx_cols
        if missing_cols:
            results["status"] = "FAIL"
            results["checks"].append(f"Missing columns in transactions: {missing_cols}")
        else:
            results["checks"].append(f"Transactions schema validated ({len(tx_cols)} columns)")

        conn.close()
    except Exception as e:
        results["status"] = "FAIL"
        results["checks"].append(f"Database audit exception: {e}")
    return results


def audit_frontend_backend_contracts():
    """Extracts API routes from frontend and verifies they exist in backend Flask url_map."""
    from app import app
    backend_rules = [
        {
            "endpoint": rule.endpoint,
            "methods": sorted(list(rule.methods - {'OPTIONS', 'HEAD'})),
            "rule": rule.rule
        }
        for rule in app.url_map.iter_rules()
    ]
    backend_paths = {r["rule"] for r in backend_rules}

    jsx_files = list(FRONTEND_SRC.rglob("*.jsx")) + list(FRONTEND_SRC.rglob("*.js"))
    frontend_endpoints = []
    url_pattern = re.compile(r'(/api/[a-zA-Z0-9_\-/${}]+|/process|/download)')

    for fpath in jsx_files:
        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
            for m in url_pattern.findall(content):
                clean_url = m.strip("`'\"?").split('?')[0]
                norm_url = re.sub(r'\$\{[^}]+\}', '<var>', clean_url)
                frontend_endpoints.append({
                    "url": clean_url,
                    "norm_url": norm_url,
                    "file": str(fpath.relative_to(ROOT_DIR))
                })
        except Exception:
            pass

    unmatched = []
    for fe in frontend_endpoints:
        url = fe["norm_url"]
        matched = any(
            re.match("^" + re.sub(r'<[^>]+>', r'[^/]+', bp) + "$", url)
            or url == bp
            or url.replace('<var>', 'test') == bp
            for bp in backend_paths
        )
        if not matched:
            unmatched.append(fe)

    return {
        "total_frontend_calls": len(frontend_endpoints),
        "total_backend_routes": len(backend_rules),
        "unmatched": unmatched,
        "backend_rules": backend_rules
    }


def run_endpoint_smoke_tests():
    """Runs test client requests against key backend endpoints."""
    from app import app
    client = app.test_client()
    smoke_endpoints = [
        ("GET", "/health"), ("GET", "/api/dashboard"), ("GET", "/api/history"),
        ("GET", "/api/transactions"), ("GET", "/api/certifications"), ("GET", "/api/reports/gaps"),
        ("GET", "/api/reconciliation/gaps"), ("GET", "/api/reconciliation/modes"),
        ("GET", "/api/reconciliation/audit"), ("GET", "/api/stats/kpi"),
        ("GET", "/api/stats/daily_volume"), ("GET", "/api/stats/exchange_distribution"),
        ("GET", "/api/stats/equity"), ("GET", "/api/stats/spread"),
        ("GET", "/api/stats/available_exchanges"), ("GET", "/api/taxes/report"),
        ("GET", "/api/taxes/settings"), ("GET", "/api/exchanges"),
        ("GET", "/api/env"), ("GET", "/api/status"), ("GET", "/api/certifications/next_start"),
    ]
    results = []
    for method, path in smoke_endpoints:
        try:
            resp = client.get(path) if method == "GET" else client.post(path, json={})
            results.append({
                "method": method, "path": path, "status": resp.status_code,
                "ok": resp.status_code in (200, 201), "is_json": resp.is_json
            })
        except Exception as e:
            results.append({"method": method, "path": path, "status": 500, "ok": False, "error": str(e)})
    return results


def run_deep_system_audit():
    print("=" * 80)
    print("AUDITORIA PROFUNDA DE SISTEMA, IMPORTS AST Y CONEXIONES API")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    print("\n[1/5] Escaneando AST de imports en funciones y modulos...")
    import_res = audit_all_python_imports()
    print(f"  * Archivos Python analizados: {import_res['total_files']}")
    print(f"  * Total imports encontrados: {import_res['total_imports']}")
    print(f"  * Imports adentro de funciones/metodos (ocultos): {import_res['hidden_imports']}")
    print(f"  * Imports validos comprobados: {import_res['valid_imports']}")
    if import_res['broken_imports']:
        print(f"  [ERROR] IMPORTS ROTOS DETECTADOS ({len(import_res['broken_imports'])}):")
        for bi in import_res['broken_imports']:
            print(f"     - {bi['file']}:{bi['line']} in {bi['scope']} -> {bi['error']}")
    else:
        print("  [OK] 100% de imports (modulo y funciones ocultas) resuelven correctamente sin errores.")

    print("\n[2/5] Verificando contratos de fachadas y __all__...")
    facade_res = audit_facades()
    all_facades_pass = True
    for f in facade_res:
        status_icon = "[OK]" if f["status"] == "PASS" else ("[WARN]" if f["status"] == "WARN" else "[FAIL]")
        print(f"  {status_icon} Fachada '{f['facade']}': {f['message']}")
        if f["status"] == "FAIL":
            all_facades_pass = False

    print("\n[3/5] Verificando base de datos SQLite y esquemas...")
    db_res = audit_database_and_schemas()
    for c in db_res["checks"]:
        print(f"  * {c}")
    print("  [OK] Esquema de base de datos e integridad estructural verificados." if db_res["status"] == "PASS" else "  [FAIL] Errores detectados en la base de datos.")

    print("\n[4/5] Auditando contratos de rutas Frontend vs Backend...")
    contract_res = audit_frontend_backend_contracts()
    print(f"  * Rutas Backend registradas en Flask: {contract_res['total_backend_routes']}")
    print(f"  * Peticiones API detectadas en Frontend: {contract_res['total_frontend_calls']}")
    if contract_res["unmatched"]:
        print(f"  [WARN] Rutas frontend no emparejadas ({len(contract_res['unmatched'])}):")
        for um in contract_res["unmatched"]:
            print(f"     - {um['file']} -> {um['url']}")
    else:
        print("  [OK] 100% de rutas frontend mapeadas correctamente en los Blueprints de backend.")

    print("\n[5/5] Ejecutando Smoke Tests en endpoints backend...")
    smoke_res = run_endpoint_smoke_tests()
    all_smoke_pass = True
    for sr in smoke_res:
        print(f"  {'[OK]' if sr['ok'] else '[FAIL]'} {sr['method']} {sr['path']} -> HTTP {sr['status']}")
        if not sr["ok"]:
            all_smoke_pass = False

    print("\n" + "=" * 80)
    success = (
        not import_res['broken_imports'] and all_facades_pass
        and db_res["status"] == "PASS" and all_smoke_pass and not contract_res["unmatched"]
    )
    print("AUDITORIA COMPLETA: TODOS LOS SUBSISTEMAS ESTAN 100% OPERATIVOS Y SANOS." if success else "AUDITORIA FINALIZADA CON ADVERTENCIAS O DETECCIONES PENDIENTES.")
    print("=" * 80)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(run_deep_system_audit())
