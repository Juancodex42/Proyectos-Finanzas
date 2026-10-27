import os
import sys
import ast
import importlib
from pathlib import Path
import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

class DetailedImportVisitor(ast.NodeVisitor):
    def __init__(self, filepath):
        self.filepath = filepath
        self.scope_stack = ["<module>"]
        self.try_depth = 0
        self.imports = []

    def visit_FunctionDef(self, node):
        self.scope_stack.append(f"def {node.name}")
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_AsyncFunctionDef(self, node):
        self.scope_stack.append(f"async def {node.name}")
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_ClassDef(self, node):
        self.scope_stack.append(f"class {node.name}")
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_Try(self, node):
        self.try_depth += 1
        self.generic_visit(node)
        self.try_depth -= 1

    def visit_Import(self, node):
        scope_str = " -> ".join(self.scope_stack)
        is_inner = len(self.scope_stack) > 1
        is_guarded = self.try_depth > 0
        for alias in node.names:
            self.imports.append({
                "file": self.filepath,
                "line": node.lineno,
                "type": "import",
                "module": alias.name,
                "name": None,
                "asname": alias.asname,
                "scope": scope_str,
                "is_inner": is_inner,
                "is_guarded": is_guarded,
                "level": 0
            })

    def visit_ImportFrom(self, node):
        scope_str = " -> ".join(self.scope_stack)
        is_inner = len(self.scope_stack) > 1
        is_guarded = self.try_depth > 0
        for alias in node.names:
            self.imports.append({
                "file": self.filepath,
                "line": node.lineno,
                "type": "from",
                "module": node.module,
                "name": alias.name,
                "asname": alias.asname,
                "scope": scope_str,
                "is_inner": is_inner,
                "is_guarded": is_guarded,
                "level": node.level
            })

def resolve_full_module_name(current_file: Path, module_name: str, level: int):
    if level == 0:
        return module_name
    current_pkg_parts = list(current_file.relative_to(WORKSPACE_ROOT).parent.parts)
    go_up = level - 1
    if go_up > len(current_pkg_parts):
        return None
    if go_up > 0:
        base_parts = current_pkg_parts[:-go_up]
    else:
        base_parts = current_pkg_parts
    if module_name:
        return ".".join(base_parts + module_name.split("."))
    return ".".join(base_parts)

def get_production_py_files():
    """Finds all production python files in engine, routes, strategies, and root."""
    py_files = []
    # Root .py files
    for f in WORKSPACE_ROOT.glob("*.py"):
        py_files.append(f)
    # engine, routes, strategies
    for sub in ["engine", "routes", "strategies"]:
        sub_dir = WORKSPACE_ROOT / sub
        if sub_dir.exists():
            for root, dirs, files in os.walk(sub_dir):
                dirs[:] = [d for d in dirs if d not in [".git", "__pycache__", ".pytest_cache"]]
                for f in files:
                    if f.endswith(".py"):
                        py_files.append(Path(root) / f)
    return py_files


class TestCodebaseImportIntegrity:

    def test_ast_parsing_all_production_files(self):
        """Verifica que todos los archivos de producción puedan ser parseados por AST sin SyntaxError."""
        files = get_production_py_files()
        assert len(files) > 0, "No production python files found"
        for f in files:
            with open(f, "r", encoding="utf-8") as fh:
                content = fh.read()
            tree = ast.parse(content, filename=str(f))
            assert tree is not None

    def test_all_production_imports_and_symbols_resolve(self):
        """
        Verifica exhaustivamente que cada sentencia import/from import (incluyendo
        imports internos dentro de funciones, métodos y clases) resuelva el módulo
        y los símbolos requeridos.
        """
        files = get_production_py_files()
        all_imports = []
        for f in files:
            with open(f, "r", encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), filename=str(f))
            visitor = DetailedImportVisitor(f)
            visitor.visit(tree)
            all_imports.extend(visitor.imports)

        failures = []
        for imp in all_imports:
            # Skip guarded imports with fallback handlers (e.g. optional dependencies in try/except)
            if imp["is_guarded"]:
                continue

            file_p = imp["file"]
            mod_name = imp["module"]
            sym_name = imp["name"]
            level = imp["level"]
            scope = imp["scope"]
            line = imp["line"]

            full_mod = resolve_full_module_name(file_p, mod_name, level)
            if not full_mod:
                failures.append(f"{file_p.name}:{line} in ({scope}) -> Invalid relative level: {level}")
                continue

            try:
                m = importlib.import_module(full_mod)
                if sym_name and sym_name != "*":
                    if not hasattr(m, sym_name):
                        # Could be a submodule
                        try:
                            importlib.import_module(f"{full_mod}.{sym_name}")
                        except Exception:
                            failures.append(f"{file_p.name}:{line} in ({scope}) -> from {full_mod} import {sym_name} (symbol not found)")
            except Exception as e:
                failures.append(f"{file_p.name}:{line} in ({scope}) -> import {full_mod}: {e}")

        assert len(failures) == 0, f"Import failures detected ({len(failures)}):\n" + "\n".join(failures)

    def test_no_circular_dependencies_in_top_level_imports(self):
        """Verifica que el grafo de dependencias de importaciones top-level sea acíclico (DAG)."""
        files = get_production_py_files()
        dep_graph = {}
        module_to_file = {}

        for f in files:
            rel = f.relative_to(WORKSPACE_ROOT)
            parts = list(rel.parts)
            if parts[-1].endswith(".py"):
                parts[-1] = parts[-1][:-3]
            if parts[-1] == "__init__":
                parts.pop()
            mod_name = ".".join(parts)
            module_to_file[mod_name] = f
            dep_graph[mod_name] = set()

        for f in files:
            rel = f.relative_to(WORKSPACE_ROOT)
            parts = list(rel.parts)
            if parts[-1].endswith(".py"):
                parts[-1] = parts[-1][:-3]
            if parts[-1] == "__init__":
                parts.pop()
            src_mod = ".".join(parts)

            with open(f, "r", encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), filename=str(f))
            visitor = DetailedImportVisitor(f)
            visitor.visit(tree)

            for imp in visitor.imports:
                if imp["is_inner"]:
                    continue
                full_mod = resolve_full_module_name(f, imp["module"], imp["level"])
                if full_mod and full_mod in module_to_file and full_mod != src_mod:
                    dep_graph[src_mod].add(full_mod)

        visited = {}
        cycles = []

        def dfs(node, path):
            visited[node] = 1
            path.append(node)
            for neighbor in dep_graph.get(node, []):
                if visited.get(neighbor) == 1:
                    idx = path.index(neighbor)
                    cycles.append(path[idx:] + [neighbor])
                elif visited.get(neighbor) is None:
                    dfs(neighbor, path)
            path.pop()
            visited[node] = 2

        for mod in dep_graph:
            if visited.get(mod) is None:
                dfs(mod, [])

        assert len(cycles) == 0, f"Circular dependencies found in production modules: {cycles}"

    def test_facades_and_reexports_integrity(self):
        """Verifica que las fachadas re-exporten todos los componentes necesarios para retrocompatibilidad."""
        import engine.simulator as sim
        import engine.optimizer as opt
        import engine.exporter as exp
        import routes.utils as ru
        import app as app_mod

        # Simulator
        assert hasattr(sim, "TripleBarrierSimulator")
        assert hasattr(sim, "VectorizedBinarySimulator")
        assert hasattr(sim, "BinarySimulator")
        assert hasattr(sim, "compute_atr")
        assert hasattr(sim, "compute_sharpe_sortino")

        # Optimizer
        assert hasattr(opt, "CapitalOptimizer")
        assert hasattr(opt, "ParallelOptimizer")
        assert hasattr(opt, "ClassicOptimizer")
        assert hasattr(opt, "calculate_wilson_lower_bound")
        assert hasattr(opt, "monte_carlo_vectorized_2d")

        # Exporter
        assert hasattr(exp, "StrategyExporter")
        assert hasattr(exp, "export_to_json")
        assert hasattr(exp, "export_to_pinescript")
        assert hasattr(exp, "export_to_python")

        # Routes utils
        assert hasattr(ru, "simulator")
        assert hasattr(ru, "stats_engine")
        assert hasattr(ru, "optimizer")
        assert hasattr(ru, "extract_markov_params")
        assert hasattr(ru, "clean_json_data")
        assert hasattr(ru, "preserve_peaks_subsample")
        assert hasattr(ru, "sse_response")

        # App re-exports
        assert hasattr(app_mod, "app")
        assert hasattr(app_mod, "simulator")
        assert hasattr(app_mod, "clean_json_data")
