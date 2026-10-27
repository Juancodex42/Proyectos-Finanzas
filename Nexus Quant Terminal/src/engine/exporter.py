"""
StrategyExporter Façade - Re-exports modular exporters from engine.exporters.
Maintains 100% backward compatibility with all existing imports.
"""
from engine.exporters.json_schema import export_to_json
from engine.exporters.pinescript import export_to_pinescript
from engine.exporters.python_standalone import export_to_python


class StrategyExporter:
    """
    Exportador Cuantitativo Multiformato de Estrategias.
    Soporta exportación a:
    1. JSON Schema (para REST API, Web UI, bots de producción)
    2. Python Standalone Script (ejecutable autónomo 100% independiente del framework)
    3. TradingView PineScript v5 (para visualización, alertas y backtesting en TradingView)
    """
    export_to_json = staticmethod(export_to_json)
    export_to_python = staticmethod(export_to_python)
    export_to_pinescript = staticmethod(export_to_pinescript)


__all__ = ['StrategyExporter', 'export_to_json', 'export_to_python', 'export_to_pinescript']
