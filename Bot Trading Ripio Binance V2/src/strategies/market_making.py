"""
Estrategia de Market Making cuantitativo basada en el modelo Avellaneda-Stoikov.
Calcula precio de reserva, spread óptimo y sesgo de inventario (Inventory Skewing).
Referencia de diseño: docs/ARQUITECTURA.md
"""

import logging
from collections import deque
from datetime import datetime
from typing import Dict, Optional, Tuple
import numpy as np

from domain.models import QuotePair
from domain.quant_math import (
    inventory_skew,
    reservation_price,
    optimal_spread,
)

logger = logging.getLogger(__name__)


class MarketMakingStrategy:
    """
    Market Making algorítmico en USDT/ARS mediante el modelo de Avellaneda-Stoikov (2008).
    Ajusta cotizaciones Bid/Ask dinámicamente según aversión al riesgo y posición neta.
    """

    def __init__(
        self,
        ripio_api,
        config: Dict,
        portfolio_manager,
        state_manager,
    ):
        self.ripio = ripio_api
        self.config = config or {}
        self.portfolio = portfolio_manager
        self.state = state_manager

        strat_config = self.config.get("strategies", {}).get("market_making", {})
        self.enabled = strat_config.get("enabled", False)
        self.allocation_pct = float(strat_config.get("allocation_pct", 0.30))

        # Soportar tanto target_spread_bps (inglés) como spread_objetivo_pct (YAML español)
        if "target_spread_bps" in strat_config:
            self.target_spread_bps = float(strat_config["target_spread_bps"])
        elif "spread_objetivo_pct" in strat_config:
            self.target_spread_bps = float(strat_config["spread_objetivo_pct"]) * 10000.0
        else:
            self.target_spread_bps = 50.0

        self.order_size_usd = float(strat_config.get("order_size_usd", 100.0))

        # Soportar tanto max_inventory_usd como max_inventario_desbalance_pct
        total_cap = 1000.0
        if self.state and hasattr(self.state, "state") and isinstance(self.state.state, dict):
            total_cap = float(self.state.state.get("capital", 1000.0) or 1000.0)

        if "max_inventory_usd" in strat_config:
            self.max_inventory_usd = float(strat_config["max_inventory_usd"])
        elif "max_inventario_desbalance_pct" in strat_config:
            self.max_inventory_usd = float(strat_config["max_inventario_desbalance_pct"]) * total_cap
        else:
            self.max_inventory_usd = 500.0

        # Soportar tanto gamma como risk_aversion
        self.gamma = float(
            strat_config.get("gamma", strat_config.get("risk_aversion", 0.1))
        )
        self.k = float(strat_config.get("k", 1.5))

        fees_cfg = self.config.get("fees", {})
        self.maker_fee = float(fees_cfg.get("maker", 0.0013))
        self.taker_fee = float(fees_cfg.get("taker", 0.0030))

        self.price_history = deque(maxlen=100)
        self.mid_prices = deque(maxlen=100)
        self.active_orders = {"bid": None, "ask": None}

        self.inventory_usdt = 0.0
        self.inventory_value_usd = 0.0
        self.total_trades = 0
        self.total_pnl = 0.0
        self.trades_today = []

        logger.info(f"[MARKET MAKING] Strategy initialized (enabled: {self.enabled})")
        logger.info(
            f"[MARKET MAKING] Target spread: {self.target_spread_bps:.1f} bps, "
            f"gamma: {self.gamma}, Max inventory: ${self.max_inventory_usd:.2f}"
        )

    async def update_market_data(self) -> bool:
        """Actualiza el precio medio y el spread del libro de órdenes en USDT/ARS."""
        try:
            ticker = await self.ripio.get_ticker("USDT_ARS")
            if not ticker:
                logger.warning("[MARKET MAKING] No se pudo obtener ticker")
                return False

            mid_price = (ticker["bid"] + ticker["ask"]) / 2.0
            self.mid_prices.append(mid_price)

            current_spread = ticker["ask"] - ticker["bid"]
            current_spread_bps = (current_spread / mid_price) * 10000.0 if mid_price > 0 else 0.0

            self.price_history.append({
                "timestamp": datetime.now(),
                "mid": mid_price,
                "bid": ticker["bid"],
                "ask": ticker["ask"],
                "spread_bps": current_spread_bps,
            })
            return True

        except Exception as e:
            logger.error(f"[MARKET MAKING] Error updating market data: {e}")
            return False

    def calculate_volatility(self, window: int = 50) -> float:
        """Calcula la volatilidad anualizada de los retornos logarítmicos del precio mid."""
        if len(self.mid_prices) < 2:
            return 0.01

        prices = list(self.mid_prices)[-window:]
        if len(prices) < 2:
            return 0.01

        returns = np.diff(np.log(prices))
        volatility = float(np.std(returns))
        volatility_annual = volatility * float(np.sqrt(288.0 * 365.0))
        return max(volatility_annual, 0.001)

    def calculate_inventory_penalty(self, sigma: float) -> float:
        """Calcula el desplazamiento del precio de reserva por inventario en ARS."""
        mid_price = self.mid_prices[-1] if self.mid_prices else 1500.0
        return inventory_skew(
            mid_price=mid_price,
            inventory_usd=self.inventory_value_usd,
            max_inventory_usd=self.max_inventory_usd,
            gamma=self.gamma,
            sigma=sigma,
        )

    def calculate_optimal_spread(self, sigma: float) -> float:
        """Calcula el spread óptimo en ARS en función de la volatilidad y comisiones."""
        mid_price = self.mid_prices[-1] if self.mid_prices else 1500.0
        return optimal_spread(
            mid_price=mid_price,
            target_spread_bps=self.target_spread_bps,
            sigma=sigma,
            maker_fee=self.maker_fee,
            gamma=self.gamma,
            k=self.k,
        )

    def calculate_quote_details(self) -> Optional[QuotePair]:
        """Genera la entidad tipada QuotePair con precios de reserva y cotizaciones."""
        if len(self.mid_prices) < 2:
            return None

        mid_price = float(self.mid_prices[-1])
        sigma = self.calculate_volatility()
        spread = self.calculate_optimal_spread(sigma)
        penalty = self.calculate_inventory_penalty(sigma)
        r_price = reservation_price(
            mid_price=mid_price,
            inventory_usd=self.inventory_value_usd,
            max_inventory_usd=self.max_inventory_usd,
            gamma=self.gamma,
            sigma=sigma,
        )
        bid_price = r_price - spread / 2.0
        ask_price = r_price + spread / 2.0

        return QuotePair(
            pair="USDT_ARS",
            mid_price=mid_price,
            reservation_price=r_price,
            bid_price=bid_price,
            ask_price=ask_price,
            spread_ars=spread,
            spread_bps=(spread / mid_price) * 10000.0 if mid_price > 0 else 0.0,
            inventory_penalty=penalty,
            volatility=sigma,
        )

    def calculate_quote_prices(self) -> Optional[Tuple[float, float]]:
        """Calcula la tupla (bid_price, ask_price) óptima según Avellaneda-Stoikov."""
        quote = self.calculate_quote_details()
        if quote is None:
            return None
        return quote.bid_price, quote.ask_price

    async def update_inventory(self) -> bool:
        """Sincroniza el inventario disponible de USDT desde el PortfolioManager."""
        try:
            await self.portfolio.actualizar_inventario()
            inventario = self.portfolio.inventario
            self.inventory_usdt = float(inventario.get("USDT", 0.0))
            self.inventory_value_usd = self.inventory_usdt
            return True
        except Exception as e:
            logger.error(f"[MARKET MAKING] Error updating inventory: {e}")
            return False

    def should_place_orders(self) -> Tuple[bool, str]:
        """Evalúa si las condiciones de inventario, historia y spread permiten cotizar."""
        if abs(self.inventory_value_usd) > self.max_inventory_usd:
            return (
                False,
                f"Inventory limit exceeded: ${self.inventory_value_usd:.2f} > ${self.max_inventory_usd:.2f}",
            )
        if len(self.mid_prices) < 10:
            return False, "Not enough market data"

        if self.price_history:
            current_spread_bps = self.price_history[-1]["spread_bps"]
            min_profitable_spread = self.maker_fee * 2.0 * 10000.0
            if current_spread_bps < min_profitable_spread:
                return (
                    False,
                    f"Market spread too tight: {current_spread_bps:.1f} < {min_profitable_spread:.1f} bps",
                )
        return True, "OK"

    async def place_orders(self, bid_price: float, ask_price: float) -> bool:
        """Coloca órdenes limit de compra y venta (simuladas en modo paper/demo)."""
        try:
            usdt_size = self.order_size_usd
            self.active_orders["bid"] = {
                "price": bid_price,
                "size": usdt_size,
                "timestamp": datetime.now(),
            }
            self.active_orders["ask"] = {
                "price": ask_price,
                "size": usdt_size,
                "timestamp": datetime.now(),
            }
            return True
        except Exception as e:
            logger.error(f"[MARKET MAKING] Error placing orders: {e}")
            return False

    async def cancel_orders(self) -> bool:
        """Cancela las cotizaciones activas en el libro."""
        self.active_orders = {"bid": None, "ask": None}
        return True

    async def run_iteration(self) -> Optional[Dict]:
        """Ejecuta un ciclo completo de actualización y cotización de Market Making."""
        if not self.enabled:
            return None

        if not await self.update_market_data():
            return None

        await self.update_inventory()
        should_place, _ = self.should_place_orders()
        if not should_place:
            await self.cancel_orders()
            return None

        quote = self.calculate_quote_details()
        if not quote:
            return None

        await self.cancel_orders()
        placed = await self.place_orders(quote.bid_price, quote.ask_price)

        return {
            "strategy": "market_making",
            "bid_price": quote.bid_price,
            "ask_price": quote.ask_price,
            "reservation_price": quote.reservation_price,
            "spread_ars": quote.spread_ars,
            "spread_bps": quote.spread_bps,
            "inventory_usd": self.inventory_value_usd,
            "placed": placed,
            "timestamp": datetime.now().isoformat(),
        }

    def get_status(self) -> Dict:
        """Retorna el estado operativo de la estrategia de Market Making."""
        sigma = self.calculate_volatility() if len(self.mid_prices) >= 2 else 0.0
        return {
            "enabled": self.enabled,
            "inventory_usdt": self.inventory_usdt,
            "inventory_value_usd": self.inventory_value_usd,
            "volatility": sigma,
            "target_spread_bps": self.target_spread_bps,
            "gamma": self.gamma,
            "max_inventory_usd": self.max_inventory_usd,
            "active_orders": {
                "bid": self.active_orders["bid"] is not None,
                "ask": self.active_orders["ask"] is not None,
            },
            "total_trades": self.total_trades,
            "total_pnl": self.total_pnl,
            "data_points": len(self.mid_prices),
        }
