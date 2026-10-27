"""
engine/execution/signal_dispatcher.py
Orquestador de Señales, Motor de Prioridad y Gestor de Mutex de Racha para Bot 1.
Coordina múltiples estrategias y múltiples pares para resolver el cuello de botella
de frecuencia sin colisiones ni sobreoperación.
"""

from dataclasses import dataclass, field
from enum import Enum
import threading
import time
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("NexusSignalDispatcher")


class MutexState(Enum):
    IDLE_WAITING = "IDLE_WAITING"          # Listo para capturar la próxima señal (Paso 0, 1, 2...)
    LOCKED_IN_TRADE = "LOCKED_IN_TRADE"      # Bala activa en Binance Futuros; bloqueado


@dataclass
class SignalCandidate:
    symbol: str
    strategy_id: str
    direction: str  # 'BUY' o 'SELL'
    candle_ts: int
    close_price: float
    atr: float
    sl_price: float
    tp_price: float
    raw_confidence: float = 1.0
    confluence_count: int = 1
    priority_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class StreakMutexManager:
    """
    Gestor atómico del Mutex de Racha de Bot 1.
    Garantiza que solo una bala esté activa en el mercado y coordina el avance de pasos.
    """
    def __init__(self):
        self._lock = threading.RLock()
        self.state: MutexState = MutexState.IDLE_WAITING
        self.active_symbol: Optional[str] = None
        self.active_strategy: Optional[str] = None
        self.active_direction: Optional[str] = None
        self.entry_price: float = 0.0
        self.entry_time: float = 0.0
        self.active_bullet_usd: float = 5.0

    def can_dispatch(self) -> bool:
        with self._lock:
            return self.state == MutexState.IDLE_WAITING

    def acquire_lock(self, candidate: SignalCandidate, bullet_usd: float) -> bool:
        with self._lock:
            if self.state != MutexState.IDLE_WAITING:
                return False
            self.state = MutexState.LOCKED_IN_TRADE
            self.active_symbol = candidate.symbol
            self.active_strategy = candidate.strategy_id
            self.active_direction = candidate.direction
            self.entry_price = candidate.close_price
            self.entry_time = time.time()
            self.active_bullet_usd = bullet_usd
            logger.info(
                f"[MUTEX LOCK ADQUIRIDO] Bot 1 entró en trade en {candidate.symbol} "
                f"vía {candidate.strategy_id} (${bullet_usd:.2f} USD)."
            )
            return True

    def release_lock(self, reason: str = "FLAT_COMPLETED"):
        with self._lock:
            old_symbol = self.active_symbol
            self.state = MutexState.IDLE_WAITING
            self.active_symbol = None
            self.active_strategy = None
            self.active_direction = None
            self.entry_price = 0.0
            self.entry_time = 0.0
            logger.info(
                f"[MUTEX LOCK LIBERADO] Bot 1 liberó {old_symbol}. Razón: {reason}. Listo para siguiente paso."
            )


class PriorityRankingEngine:
    """
    Motor cuantitativo que resuelve confluencias, conflictos y rankea señales.
    """
    # Estadísticas históricas de calibración (Wilson Lower Bound y Win Rates)
    STRATEGY_WEIGHTS = {
        "daily_confluence": {"wilson_low": 0.68, "p_ww": 0.72},
        "climax_reversal": {"wilson_low": 0.65, "p_ww": 0.69},
        "volatility_squeeze_ml": {"wilson_low": 0.62, "p_ww": 0.64},
        "rsi_extremes": {"wilson_low": 0.60, "p_ww": 0.61},
        "bollinger_bounce": {"wilson_low": 0.59, "p_ww": 0.60},
        "mean_reversion": {"wilson_low": 0.58, "p_ww": 0.59},
    }

    SYMBOL_WEIGHTS = {
        "BTC/USDT": 1.00,
        "BTCUSDT": 1.00,
        "ETH/USDT": 0.95,
        "ETHUSDT": 0.95,
        "SOL/USDT": 0.90,
        "SOLUSDT": 0.90,
        "BNB/USDT": 0.88,
        "BNBUSDT": 0.88,
        "AVAX/USDT": 0.82,
        "AVAXUSDT": 0.82,
    }

    @classmethod
    def rank_candidates(
        cls,
        candidates: List[SignalCandidate],
        blocked_symbols: Optional[List[str]] = None
    ) -> List[SignalCandidate]:
        """
        1. Filtra símbolos bloqueados (por Bot 2 o en cooldown).
        2. Resuelve colisiones en el mismo símbolo (Veto si BUY vs SELL; Confluencia si BUY + BUY).
        3. Calcula el Priority Score institucional.
        4. Ordena descendentemente.
        """
        blocked = set(s.upper().replace('/', '') for s in (blocked_symbols or []))

        # 1. Descartar símbolos bloqueados
        valid_candidates = [
            c for c in candidates
            if c.symbol.upper().replace('/', '') not in blocked
        ]
        if not valid_candidates:
            return []

        # 2. Agrupar por símbolo para resolver conflictos intra-par
        by_symbol: Dict[str, List[SignalCandidate]] = {}
        for c in valid_candidates:
            sym_clean = c.symbol.upper().replace('/', '')
            by_symbol.setdefault(sym_clean, []).append(c)

        consolidated: List[SignalCandidate] = []

        for sym_clean, sym_cands in by_symbol.items():
            directions = set(c.direction.upper() for c in sym_cands)
            if len(directions) > 1:
                # Conflicto direccional en el mismo par: VETO CRUZADO
                logger.warning(
                    f"[VETO CRUZADO] Conflicto en {sym_clean}: Señales contradictorias (BUY y SELL) "
                    f"detectadas en la misma vela. Símbolo descartado por seguridad."
                )
                continue

            # Misma dirección: Confluencia pura
            primary = sym_cands[0]
            confluence = len(sym_cands)
            strats = [c.strategy_id for c in sym_cands]

            # Calcular Score Compuesto
            strat_info = cls.STRATEGY_WEIGHTS.get(primary.strategy_id, {"wilson_low": 0.55, "p_ww": 0.55})
            sym_weight = cls.SYMBOL_WEIGHTS.get(primary.symbol, 0.75)

            # Bonus por confluencia multi-estrategia (+25% por cada estrategia adicional confirmando)
            confluence_mult = 1.0 + (0.25 * (confluence - 1))

            score = (
                0.50 * strat_info["wilson_low"] +
                0.30 * strat_info["p_ww"] +
                0.20 * sym_weight
            ) * confluence_mult

            primary.confluence_count = confluence
            primary.priority_score = round(score, 4)
            primary.metadata["contributing_strategies"] = strats
            consolidated.append(primary)

        # 3. Ordenar por score decreciente
        consolidated.sort(key=lambda x: x.priority_score, reverse=True)
        return consolidated
