"""
Estrategia de Arbitraje Estadístico (Pairs Trading) entre USDT/ARS y USDC/ARS.
Detecta desvíos de paridad mediante Z-score, Ornstein-Uhlenbeck y test ADF.
Referencia de diseño: docs/ARQUITECTURA.md
"""

import logging
from collections import deque
from datetime import datetime
from typing import Dict, Optional, Tuple
import numpy as np

from domain.models import ArbitrageSignal
from domain.quant_math import (
    calculate_z_score,
    calculate_spread_bps,
    half_life,
    test_cointegration,
)

logger = logging.getLogger(__name__)


class StatisticalArbitrageStrategy:
    """
    Pairs Trading cuantitativo entre USDT/ARS y USDC/ARS basado en reversión
    a la media, cointegración / estacionariedad ADF y ruteo óptimo.
    """

    def __init__(
        self,
        ripio_api,
        config: Dict,
        portfolio_manager,
        state_manager,
        router=None,
    ):
        self.ripio = ripio_api
        self.config = config or {}
        self.portfolio = portfolio_manager
        self.state = state_manager
        self.router = router

        strat_config = self.config.get("strategies", {}).get("statistical_arbitrage", {})
        self.enabled = strat_config.get("enabled", False)
        self.allocation_pct = float(strat_config.get("allocation_pct", 0.40))
        self.z_score_entry = float(
            strat_config.get("z_score_entry", strat_config.get("z_entry_threshold", 2.0))
        )
        self.z_score_exit = float(
            strat_config.get("z_score_exit", strat_config.get("z_exit_threshold", 0.5))
        )
        # Alias de compatibilidad para handlers de Telegram
        self.z_entry_threshold = self.z_score_entry
        self.z_exit_threshold = self.z_score_exit

        raw_lookback = strat_config.get(
            "lookback_period", strat_config.get("lookback_days", 100)
        )
        self.lookback_period = max(10, int(raw_lookback))
        self.min_spread_bps = float(strat_config.get("min_spread_bps", 10.0))
        self.cointegration_pvalue_max = float(
            strat_config.get("cointegration_pvalue_max", 0.05)
        )

        fees_cfg = self.config.get("fees", {})
        self.maker_fee = float(fees_cfg.get("maker", 0.0013))
        self.taker_fee = float(fees_cfg.get("taker", 0.0030))

        self.price_history_usdt = deque(maxlen=self.lookback_period)
        self.price_history_usdc = deque(maxlen=self.lookback_period)
        self.ratio_history = deque(maxlen=self.lookback_period)

        self.current_position: Optional[str] = None
        self.position_entry_price: Optional[float] = None
        self.position_entry_time: Optional[datetime] = None
        self.position_size_usd: float = 0.0

        logger.info(f"[STAT ARB] Strategy initialized (enabled: {self.enabled})")
        logger.info(
            f"[STAT ARB] Z-entry: {self.z_score_entry}, Z-exit: {self.z_score_exit}, "
            f"Lookback: {self.lookback_period}"
        )

    async def update_prices(self) -> bool:
        """Actualiza las series de precios mid de USDT/ARS y USDC/ARS desde Ripio API."""
        try:
            ticker_usdt = await self.ripio.get_ticker("USDT_ARS")
            ticker_usdc = await self.ripio.get_ticker("USDC_ARS")

            if not ticker_usdt or not ticker_usdc:
                logger.warning("[STAT ARB] No se pudieron obtener precios")
                return False

            price_usdt = (ticker_usdt["bid"] + ticker_usdt["ask"]) / 2.0
            price_usdc = (ticker_usdc["bid"] + ticker_usdc["ask"]) / 2.0
            if price_usdc <= 0:
                return False

            self.price_history_usdt.append(price_usdt)
            self.price_history_usdc.append(price_usdc)
            self.ratio_history.append(price_usdt / price_usdc)
            return True

        except Exception as e:
            logger.error(f"[STAT ARB] Error updating prices: {e}")
            return False

    def calculate_z_score(self) -> Optional[float]:
        """Calcula el Z-score actual del ratio USDT/USDC."""
        min_obs = min(20, self.lookback_period)
        if len(self.ratio_history) < min_obs:
            return None
        return calculate_z_score(list(self.ratio_history))

    def calculate_spread_bps(self) -> Optional[float]:
        """Calcula el desvío actual respecto a la paridad 1:1 en basis points."""
        if len(self.ratio_history) < 2:
            return None
        return calculate_spread_bps(self.ratio_history[-1], parity=1.0)

    def calculate_half_life(self) -> float:
        """Calcula el half-life de reversión a la media (Ornstein-Uhlenbeck)."""
        if len(self.ratio_history) < 10:
            return float("inf")
        return half_life(list(self.ratio_history))

    def test_cointegration(
        self,
        usdt_prices=None,
        usdc_prices=None,
    ) -> Tuple[bool, float]:
        """
        Verifica estacionariedad del spread USDT - USDC (phi_1 < 1 / lambda < 0).
        Puede invocarse de forma síncrona pasando series o usando el historial interno.
        """
        x = list(usdt_prices) if usdt_prices is not None else list(self.price_history_usdt)
        y = list(usdc_prices) if usdc_prices is not None else list(self.price_history_usdc)
        return test_cointegration(x, y, pvalue_threshold=self.cointegration_pvalue_max)

    async def check_cointegration(self) -> Tuple[bool, float]:
        """Wrapper asíncrono para validación de cointegración / estacionariedad."""
        return self.test_cointegration()

    def calculate_position_size(self, signal_strength: float) -> float:
        """Calcula el tamaño de posición en USD según capital, alocación y límite de riesgo."""
        total_capital = 1000.0
        if self.state and hasattr(self.state, "state"):
            total_capital = float(self.state.state.get("capital", 1000.0) or 1000.0)

        strategy_capital = total_capital * self.allocation_pct
        signal_factor = min(abs(signal_strength) / 3.0, 1.0)

        risk_cfg = self.config.get("risk", {})
        max_position_pct = float(
            risk_cfg.get(
                "max_posicion_individual_pct",
                risk_cfg.get("max_posicion_individual", 0.20),
            )
        )
        return float(strategy_capital * signal_factor * max_position_pct)

    async def generate_signal(self) -> Optional[Dict]:
        """Genera señal de apertura o cierre validando Z-score, spread y cointegración."""
        min_obs = min(20, self.lookback_period)
        if len(self.ratio_history) < min_obs:
            return None

        z_score = self.calculate_z_score()
        spread_bps = self.calculate_spread_bps()
        if z_score is None or spread_bps is None:
            return None

        if self.current_position is None:
            if spread_bps < self.min_spread_bps:
                return None

            is_cointegrated, p_value = await self.check_cointegration()
            if not is_cointegrated:
                return None

            hl = self.calculate_half_life()
            if z_score > self.z_score_entry:
                pos_size = self.calculate_position_size(abs(z_score))
                return ArbitrageSignal(
                    action="open_long_usdc",
                    z_score=z_score,
                    spread_bps=spread_bps,
                    confidence=min(abs(z_score) / 3.0, 1.0),
                    position_size_usd=pos_size,
                    reason=f"Z-score alto ({z_score:.2f}) - USDT sobrevaluado",
                    half_life=hl,
                    p_value=p_value,
                ).to_dict()

            if z_score < -self.z_score_entry:
                pos_size = self.calculate_position_size(abs(z_score))
                return ArbitrageSignal(
                    action="open_long_usdt",
                    z_score=z_score,
                    spread_bps=spread_bps,
                    confidence=min(abs(z_score) / 3.0, 1.0),
                    position_size_usd=pos_size,
                    reason=f"Z-score bajo ({z_score:.2f}) - USDT subvaluado",
                    half_life=hl,
                    p_value=p_value,
                ).to_dict()

        else:
            if abs(z_score) < self.z_score_exit:
                return ArbitrageSignal(
                    action="close",
                    z_score=z_score,
                    spread_bps=spread_bps,
                    confidence=1.0,
                    position_size_usd=self.position_size_usd,
                    reason=f"Z-score normalizado ({z_score:.2f}) - Cerrar posición",
                ).to_dict()

        return None

    async def execute_signal(self, signal: Dict) -> bool:
        """Ejecuta la señal de trading (vía router si está activo) y persiste trades cerrados."""
        action = signal.get("action")
        size_usd = float(signal.get("position_size_usd", 100.0))

        try:
            if action in ("open_long_usdt", "open_long_usdc"):
                from_token = "USDC" if action == "open_long_usdt" else "USDT"
                to_token = "USDT" if action == "open_long_usdt" else "USDC"

                if self.router:
                    result = await self.router.execute_optimal_route(
                        from_token=from_token,
                        to_token=to_token,
                        amount_usd=size_usd,
                    )
                    if not result.get("success", False):
                        return False

                self.current_position = "long_usdt" if action == "open_long_usdt" else "long_usdc"
                self.position_entry_price = self.ratio_history[-1] if self.ratio_history else 1.0
                self.position_entry_time = datetime.now()
                self.position_size_usd = size_usd
                return True

            if action == "close" and self.current_position:
                pnl_pct = 0.0
                pnl_usd = 0.0
                current_ratio = self.ratio_history[-1] if self.ratio_history else 1.0

                if self.position_entry_price and self.position_entry_price > 0:
                    if self.current_position == "long_usdt":
                        pnl_pct = (current_ratio / self.position_entry_price - 1.0) * 100.0
                    else:
                        pnl_pct = (self.position_entry_price / current_ratio - 1.0) * 100.0
                    pnl_usd = (pnl_pct / 100.0) * (self.position_size_usd or 100.0)

                trade_data = {
                    "pair": "USDT_USDC",
                    "side": self.current_position,
                    "amount_usd": self.position_size_usd or 100.0,
                    "entry_price": self.position_entry_price,
                    "exit_price": current_ratio,
                    "pnl": pnl_usd,
                    "pnl_pct": pnl_pct,
                    "strategy": "statistical_arbitrage",
                }
                if self.state and hasattr(self.state, "add_trade"):
                    self.state.add_trade("statistical_arbitrage", trade_data)
                if self.portfolio and hasattr(self.portfolio, "registrar_trade"):
                    self.portfolio.registrar_trade("statistical_arbitrage", trade_data)

                self.current_position = None
                self.position_entry_price = None
                self.position_entry_time = None
                self.position_size_usd = 0.0
                return True

            return False

        except Exception as e:
            logger.error(f"[STAT ARB] Error executing signal: {e}")
            return False

    def on_data(self, row) -> Optional[Dict]:
        """Adaptador síncrono para evaluación en BacktesterEngine barra por barra."""
        usdt = row.get("USDT_ARS_mid", row.get("close", row.get("price")))
        usdc = row.get("USDC_ARS_mid")
        if usdt is None:
            return None

        usdt_val = float(usdt)
        usdc_val = float(usdc) if usdc is not None else 1500.0
        if usdc_val <= 0:
            return None

        self.price_history_usdt.append(usdt_val)
        self.price_history_usdc.append(usdc_val)
        self.ratio_history.append(usdt_val / usdc_val)

        z_score = self.calculate_z_score()
        if z_score is None:
            return None

        if self.current_position is None:
            if z_score < -self.z_score_entry:
                self.current_position = "long"
                return {
                    "action": "open_long",
                    "position_size_usd": self.calculate_position_size(abs(z_score)),
                    "reason": f"StatArb Long entry Z={z_score:.2f}",
                }
            if z_score > self.z_score_entry:
                self.current_position = "short"
                return {
                    "action": "open_short",
                    "position_size_usd": self.calculate_position_size(abs(z_score)),
                    "reason": f"StatArb Short entry Z={z_score:.2f}",
                }
        else:
            if abs(z_score) < self.z_score_exit:
                close_act = "close_long" if self.current_position == "long" else "close_short"
                self.current_position = None
                return {
                    "action": close_act,
                    "position_size_usd": 0.0,
                    "reason": f"StatArb exit Z={z_score:.2f}",
                }
        return None

    async def run_iteration(self) -> Optional[Dict]:
        """Ejecuta un ciclo de actualización de precios, señal y orden."""
        if not self.enabled:
            return None
        if not await self.update_prices():
            return None

        signal = await self.generate_signal()
        if signal:
            executed = await self.execute_signal(signal)
            return {
                "strategy": "statistical_arbitrage",
                "signal": signal,
                "executed": executed,
                "timestamp": datetime.now().isoformat(),
            }
        return None

    def get_status(self) -> Dict:
        """Retorna el estado operativo actual de la estrategia."""
        return {
            "enabled": self.enabled,
            "current_position": self.current_position,
            "z_score": self.calculate_z_score(),
            "spread_bps": self.calculate_spread_bps(),
            "half_life": self.calculate_half_life() if len(self.ratio_history) >= 10 else None,
            "data_points": len(self.ratio_history),
            "position_duration": (
                str(datetime.now() - self.position_entry_time)
                if self.position_entry_time
                else None
            ),
        }
