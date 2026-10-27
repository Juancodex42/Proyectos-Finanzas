import json
from typing import Dict, Any, Optional

try:
    from strategies import STRATEGIES
except ImportError:
    STRATEGIES = {}


def export_to_json(strategy_key: str, params: dict, symbol: str = "BTCUSDT", expiry: int = 1) -> str:
    """Exporta la configuración y esquema de una estrategia a formato JSON."""
    strat_key = strategy_key.lower()
    strat_cls = STRATEGIES.get(strat_key)
    name = getattr(strat_cls, 'name', strategy_key.upper()) if strat_cls else strategy_key.upper()
    description = getattr(strat_cls, 'description', '') if strat_cls else ''
    
    schema = []
    if strat_cls and hasattr(strat_cls, 'get_params_schema'):
        try:
            schema = strat_cls().get_params_schema()
        except Exception:
            schema = []

    payload = {
        "strategy_key": strategy_key,
        "name": name,
        "description": description,
        "symbol": symbol,
        "expiry_candles": expiry,
        "parameters": params,
        "schema": schema,
        "version": "1.0.0",
        "metadata": {
            "created_by": "Antigravity Quant Engine",
            "target_winrate": ">80%",
            "engine_version": "2.5.0",
            "export_format": "JSON_REST_SCHEMA_V1"
        }
    }
    return json.dumps(payload, indent=2)
