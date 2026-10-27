import os
import re

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README_PATH = os.path.join(ROOT_DIR, "README.md")
BACKEND_DIR = os.path.join(ROOT_DIR, "webapp", "backend")
FRONTEND_DIR = os.path.join(ROOT_DIR, "webapp", "frontend")

BACKEND_PACKAGES = (
    "db",
    "models",
    "parsers",
    "routes",
    "services",
    "api_clients",
    "compat",
    "utils",
    "workers",
)

PACKAGE_DESCRIPTIONS = {
    "db": "Conexión SQLite, inicialización de esquema, migraciones y consultas base.",
    "models": "Modelos de dominio, normalización de exchanges y hash canónico MD5.",
    "parsers": "Parsers modulares por exchange (CSV/XLSX) y registro unificado de ingesta.",
    "routes": "Blueprints de Flask y endpoints HTTP REST desacoplados por dominio.",
    "services": "Lógica de negocio contable (FIFO, huecos, custodia mensual, conciliación, caché, impuestos).",
    "api_clients": "Conectores y clientes para sincronización con APIs de exchanges.",
    "compat": "Fachadas de compatibilidad retroactiva para módulos históricos.",
    "utils": "Utilidades transversales (normalización de fechas, símbolos y helpers).",
    "workers": "Workers de sincronización automática en segundo plano.",
}


def _node_id(module_name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", module_name)


def get_backend_modules():
    modules = []
    if not os.path.exists(BACKEND_DIR):
        return modules

    # Entrypoints en la raíz de webapp/backend (p. ej. app.py)
    for f in sorted(os.listdir(BACKEND_DIR)):
        full_path = os.path.join(BACKEND_DIR, f)
        if (
            os.path.isfile(full_path)
            and f.endswith(".py")
            and not f.startswith("test_")
            and not f.startswith("verify_")
            and not f.startswith("__")
        ):
            modules.append(f[:-3])

    # Paquetes modulares reales de webapp/backend/
    for pkg in BACKEND_PACKAGES:
        pkg_dir = os.path.join(BACKEND_DIR, pkg)
        if not os.path.isdir(pkg_dir):
            continue
        for f in sorted(os.listdir(pkg_dir)):
            if (
                f.endswith(".py")
                and not f.startswith("__")
                and not f.startswith("test_")
                and not f.startswith("verify_")
            ):
                mod_rel = f"{pkg}/{f[:-3]}"
                if mod_rel not in modules:
                    modules.append(mod_rel)

    return modules


def analyze_imports(modules):
    dependencies = []
    alias_map = {}
    for m in modules:
        alias_map[m] = m
        alias_map[m.replace("/", ".")] = m
        short_name = m.split("/")[-1]
        if short_name not in alias_map or m.startswith("compat/"):
            alias_map[short_name] = m

    for module in modules:
        filepath = os.path.join(BACKEND_DIR, *f"{module}.py".split("/"))
        if not os.path.exists(filepath):
            continue

        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("import "):
                parts = line[7:].split(",")
                for p in parts:
                    raw_target = p.strip().split(" ")[0]
                    target = alias_map.get(raw_target) or alias_map.get(raw_target.split(".")[0])
                    if target and target in modules and target != module:
                        dependencies.append((module, target))
            elif line.startswith("from ") and " import " in line:
                from_part, import_part = line[5:].split(" import ", 1)
                raw_source = from_part.strip()
                target = alias_map.get(raw_source)
                if target and target in modules and target != module:
                    dependencies.append((module, target))
                    continue

                for imp in import_part.split(","):
                    imp_name = imp.strip().split(" ")[0]
                    candidate = f"{raw_source}.{imp_name}"
                    sub_target = (
                        alias_map.get(candidate)
                        or alias_map.get(raw_source.split(".")[0])
                        or alias_map.get(imp_name)
                    )
                    if sub_target and sub_target in modules and sub_target != module:
                        dependencies.append((module, sub_target))

    return sorted(list(set(dependencies)))


def build_mermaid_diagram(dependencies, modules):
    lines = [
        "```mermaid",
        "graph TD",
        "    %% Entidades Externas y Frontend",
        "    User((Usuario))",
        "    Browser[Navegador Web<br/>Frontend React/Vite]",
        "",
        '    subgraph "Backend Modular (Flask)"',
    ]

    for m in modules:
        nid = _node_id(m)
        label = f"{m}.py"
        if m == "app":
            label = "app.py<br/>(API Principal)"
        lines.append(f'        {nid}["{label}"]')

    lines.append("        DB[(transactions.db<br/>SQLite)]")
    lines.append("    end")
    lines.append("")

    lines.append('    User -- "Interacciona" --> Browser')
    if "app" in modules:
        lines.append('    Browser -- "Llamadas HTTP API" --> app')

    if "db/connection" in modules:
        lines.append(f'    {_node_id("db/connection")} --> DB')
    elif "compat/db_manager" in modules:
        lines.append(f'    {_node_id("compat/db_manager")} --> DB')

    lines.append("    %% Relaciones Dinámicas de Código")
    for src, dst in dependencies:
        lines.append(f"    {_node_id(src)} -.-> {_node_id(dst)}")

    lines.append("```")
    return "\n".join(lines)


def update_readme():
    if not os.path.exists(README_PATH):
        print("README.md no encontrado.")
        return

    with open(README_PATH, "r", encoding="utf-8") as f:
        readme_content = f.read()

    anchor = "## 🏗️ Arquitectura y Flujo del Sistema"
    if anchor not in readme_content:
        readme_content += f"\n\n{anchor}\n"

    parts = readme_content.split(anchor)
    static_part = parts[0]

    modules = get_backend_modules()
    dependencies = analyze_imports(modules)
    mermaid_diagram = build_mermaid_diagram(dependencies, modules)

    webapp_structure = ""
    if os.path.exists(FRONTEND_DIR):
        webapp_structure += "- `webapp/frontend/`: React application (Vite + TypeScript)\n"
    if os.path.exists(BACKEND_DIR):
        webapp_structure += "- `webapp/backend/`: Python API modular (Flask)\n"

    dynamic_content = f"""{anchor}

El sistema está diseñado bajo una arquitectura cliente-servidor modular (Frontend-Backend). Esta sección se genera **dinámicamente** escaneando los paquetes modulares reales de `webapp/backend/` (`db/`, `models/`, `parsers/`, `routes/`, `services/`, `api_clients/`, `compat/`, `utils/`, `workers/`) y analizando las dependencias de importación del código fuente.

### 📊 Diagrama de Dependencias y Flujo de Control

{mermaid_diagram}

> [!NOTE]
> Las líneas punteadas `-.->` indican dependencias directas de importación (`import`) detectadas estáticamente en el código backend.

### 📁 Estructura Detectada del Proyecto

#### Aplicación Web (`webapp/`)
{webapp_structure}
#### Inventario Técnico Modular de Backend (`webapp/backend/`)
"""
    root_modules = [m for m in modules if "/" not in m]
    for rm in root_modules:
        desc = " - Servidor Flask principal y registro de blueprints." if rm == "app" else ""
        dynamic_content += f"- `{rm}.py`{desc}\n"

    for pkg in BACKEND_PACKAGES:
        pkg_modules = [m for m in modules if m.startswith(f"{pkg}/")]
        if not pkg_modules:
            continue
        pkg_desc = PACKAGE_DESCRIPTIONS.get(pkg, "")
        dynamic_content += f"- **`{pkg}/`** — {pkg_desc}\n"
        for pm in pkg_modules:
            dynamic_content += f"  - `{pm}.py`\n"

    new_readme = static_part + dynamic_content
    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(new_readme)
    print("README.md actualizado dinámicamente con éxito.")


if __name__ == "__main__":
    update_readme()
