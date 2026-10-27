"""
Gestor de persistencia atómica en disco para el estado operativo del bot.
Almacena capital, inventario, órdenes activas e historial de operaciones en JSON.
Referencia de diseño: docs/ARQUITECTURA.md
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class StateManager:
    """
    Gestiona la persistencia del estado del bot mediante escrituras atómicas (.tmp -> .json).
    Mantiene sincronizadas las claves `trades_dia` y `trades_history`.
    """

    def __init__(self, state_dir: Optional[Union[str, Path]] = None):
        self.state_dir = Path(state_dir) if state_dir else PROJECT_ROOT / "data" / "state"
        self.state_file = self.state_dir / "bot_state.json"
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.state: Dict[str, Any] = {
            "capital": 0.0,
            "inventario": {
                "USDT": 0.0,
                "USDC": 0.0,
                "ARS": 0.0,
                "BTC": 0.0,
                "ETH": 0.0,
            },
            "ordenes_activas": {},
            "trades_dia": [],
            "trades_history": [],
            "spread_history": [],
            "pnl_por_estrategia": {
                "statistical_arbitrage": {"trades": [], "pnl_total": 0.0},
                "market_making": {"trades": [], "pnl_total": 0.0},
                "triangular_arbitrage": {"trades": [], "pnl_total": 0.0},
            },
            "ultima_actualizacion": None,
        }

    def load_state(self) -> Dict[str, Any]:
        """Carga el estado desde `bot_state.json` o retorna el estado inicial."""
        if not self.state_file.exists():
            return self.state

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                loaded_state = json.load(f)
            self.state.update(loaded_state)
            if "trades_history" not in self.state:
                self.state["trades_history"] = list(self.state.get("trades_dia", []))
            return self.state
        except Exception as e:
            logger.error(f"❌ Error cargando estado: {e}")
            return self.state

    def save_state(self, state: Optional[Dict[str, Any]] = None) -> bool:
        """Persiste el estado en disco de forma atómica a través de un archivo temporal."""
        if state:
            self.state.update(state)

        self.state["ultima_actualizacion"] = datetime.now().isoformat()
        try:
            temp_file = self.state_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
            temp_file.replace(self.state_file)
            return True
        except Exception as e:
            logger.error(f"❌ Error guardando estado: {e}")
            return False

    def update_capital(self, capital: float):
        """Actualiza y persiste el capital actual."""
        self.state["capital"] = float(capital)
        self.save_state()

    def update_inventario(self, inventario: Dict[str, float]):
        """Actualiza y persiste los saldos de inventario por moneda."""
        self.state["inventario"].update(inventario)
        self.save_state()

    def add_orden_activa(self, orden_id: str, orden_data: Dict):
        """Registra una orden abierta en el estado persistente."""
        self.state["ordenes_activas"][orden_id] = orden_data
        self.save_state()

    def remove_orden_activa(self, orden_id: str):
        """Elimina una orden cerrada o cancelada del registro de órdenes activas."""
        if orden_id in self.state["ordenes_activas"]:
            del self.state["ordenes_activas"][orden_id]
            self.save_state()

    def add_trade(self, estrategia: str, trade_data: Dict):
        """Añade un trade completado tanto a `trades_dia` como a `trades_history`."""
        now_iso = trade_data.get("timestamp") or datetime.now().isoformat()
        record = {
            **trade_data,
            "timestamp": now_iso,
            "estrategia": estrategia,
            "strategy": estrategia,
        }
        self.state.setdefault("trades_dia", []).append(record)
        self.state.setdefault("trades_history", []).append(record)

        if estrategia in self.state["pnl_por_estrategia"]:
            self.state["pnl_por_estrategia"][estrategia]["trades"].append(record)
            self.state["pnl_por_estrategia"][estrategia]["pnl_total"] += float(
                trade_data.get("pnl", 0.0)
            )

        self.save_state()

    def reset_dia(self):
        """Reinicia la lista de operaciones del día conservando `trades_history`."""
        self.state["trades_dia"] = []
        self.save_state()

    def get_estadisticas(self) -> Dict[str, Any]:
        """Retorna resumen estadístico del estado actual."""
        trades_dia = self.state.get("trades_dia", [])
        pnl_dia = sum(float(t.get("pnl", 0.0)) for t in trades_dia)
        return {
            "capital": self.state["capital"],
            "inventario": self.state["inventario"],
            "num_ordenes_activas": len(self.state["ordenes_activas"]),
            "trades_dia": len(trades_dia),
            "pnl_dia": pnl_dia,
            "pnl_por_estrategia": {
                k: {
                    "num_trades": len(v["trades"]),
                    "pnl_total": v["pnl_total"],
                }
                for k, v in self.state["pnl_por_estrategia"].items()
            },
            "ultima_actualizacion": self.state["ultima_actualizacion"],
        }

    def backup_state(self) -> bool:
        """Crea una copia de respaldo fechada del archivo de estado."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.state_dir / f"bot_state_backup_{timestamp}.json"
            with open(backup_file, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"❌ Error creando backup: {e}")
            return False
