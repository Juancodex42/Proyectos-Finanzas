"""
routes/bot_routes.py
Alias de compatibilidad y punto de enlace para el subsistema de ejecución dual de bots.
Referencia de diseño: docs/ARQUITECTURA.md
"""
from .execution_routes import execution_bp as bot_bp, manager


def init_bot_system():
    """Inicializa el subsistema Dual-Bot en memoria o con configuración persistida."""
    return manager


__all__ = ["bot_bp", "init_bot_system", "manager"]
