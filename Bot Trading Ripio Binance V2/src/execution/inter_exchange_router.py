"""
Enrutador inteligente de liquidez inter-exchange entre Ripio Trade y Binance.
Evalúa costos de spread local vs comisiones on-chain (TRC20/BEP20/ERC20).
Referencia de diseño: docs/INTER_EXCHANGE_ROUTING.md
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class RouteType(Enum):
    """Tipos de rutas de ejecución soportadas."""
    RIPIO_DIRECT = "ripio_direct"
    BINANCE_ROUTE = "binance_route"
    NO_ROUTE = "no_route"


class NetworkType(Enum):
    """Redes blockchain soportadas para transferencia de stablecoins."""
    ERC20 = "erc20"
    TRC20 = "trc20"
    BEP20 = "bep20"


class InterExchangeRouter:
    """
    Router cuantitativo para ejecución óptima de swaps entre stablecoins.
    Compara el costo del spread directo en Ripio contra el puente vía Binance.
    """

    def __init__(self, ripio_api, binance_api, config: Dict):
        self.ripio = ripio_api
        self.binance = binance_api
        self.config = config or {}

        self.network_fees = {
            "USDT": {
                NetworkType.ERC20: 12.0,
                NetworkType.TRC20: 1.5,
                NetworkType.BEP20: 1.0,
            },
            "USDC": {
                NetworkType.ERC20: 10.0,
                NetworkType.TRC20: 1.5,
                NetworkType.BEP20: 1.0,
            },
        }

        routing_cfg = self.config.get("routing", {})
        custom_fees = routing_cfg.get("network_fees", {})
        for token_key, net_dict in custom_fees.items():
            t_upper = token_key.upper()
            if t_upper in self.network_fees and isinstance(net_dict, dict):
                for net_k, val in net_dict.items():
                    try:
                        self.network_fees[t_upper][NetworkType(net_k.lower())] = float(val)
                    except ValueError:
                        pass

        self.ripio_taker_fee = float(self.config.get("fees", {}).get("taker", 0.0030))
        self.binance_swap_fee = 0.0010
        self.min_profit_margin = float(routing_cfg.get("min_profit_margin", 1.5))

        pref_net = str(routing_cfg.get("preferred_network", "trc20")).lower()
        try:
            self.preferred_network = NetworkType(pref_net)
        except ValueError:
            self.preferred_network = NetworkType.TRC20

        self.spread_cache = {}
        self.cache_ttl = 60

        logger.info("[ROUTER] Inter-Exchange Router initialized")
        logger.info(f"[ROUTER] Preferred network: {self.preferred_network.value}")

    async def get_ripio_swap_spread(
        self,
        from_token: str,
        to_token: str,
    ) -> Optional[Dict]:
        """
        Obtiene el spread efectivo del par en Ripio.
        Si consulta el par inverso, invierte correctamente 1/ask como bid y 1/bid como ask.
        """
        try:
            pair = f"{from_token}_{to_token}"
            ticker = await self.ripio.get_ticker(pair)

            if ticker and ticker.get("bid", 0) > 0 and ticker.get("ask", 0) > 0:
                bid = float(ticker["bid"])
                ask = float(ticker["ask"])
            else:
                pair_inverse = f"{to_token}_{from_token}"
                inv_ticker = await self.ripio.get_ticker(pair_inverse)

                if inv_ticker and inv_ticker.get("bid", 0) > 0 and inv_ticker.get("ask", 0) > 0:
                    inv_bid = float(inv_ticker["bid"])
                    inv_ask = float(inv_ticker["ask"])
                    bid = 1.0 / inv_ask
                    ask = 1.0 / inv_bid
                    pair = pair_inverse
                else:
                    # Fallback sintético vía par contra ARS si existen ambos tickers
                    from_ars = await self.ripio.get_ticker(f"{from_token}_ARS")
                    to_ars = await self.ripio.get_ticker(f"{to_token}_ARS")
                    if (
                        from_ars
                        and to_ars
                        and to_ars.get("ask", 0) > 0
                        and to_ars.get("bid", 0) > 0
                    ):
                        bid = float(from_ars["bid"]) / float(to_ars["ask"])
                        ask = float(from_ars["ask"]) / float(to_ars["bid"])
                    else:
                        logger.warning(f"[ROUTER] No ticker found for {from_token}/{to_token}")
                        return None

            mid = (bid + ask) / 2.0
            spread_abs = ask - bid
            spread_pct = (spread_abs / mid) * 100.0 if mid > 0 else 0.0
            dislocation_pct = abs(mid - 1.0) * 100.0

            return {
                "pair": pair,
                "bid": bid,
                "ask": ask,
                "mid": mid,
                "spread_abs": spread_abs,
                "spread_pct": spread_pct,
                "dislocation_pct": dislocation_pct,
                "timestamp": datetime.now(),
            }

        except Exception as e:
            logger.error(f"[ROUTER] Error getting Ripio spread: {e}")
            return None

    def calculate_ripio_direct_cost(self, amount_usd: float, spread_pct: float) -> Dict:
        """Calcula el costo total de ejecutar el swap directamente dentro de Ripio."""
        spread_cost = amount_usd * (spread_pct / 100.0)
        trading_fee = amount_usd * self.ripio_taker_fee
        total_cost = spread_cost + trading_fee

        return {
            "route": RouteType.RIPIO_DIRECT,
            "spread_cost_usd": float(spread_cost),
            "trading_fee_usd": float(trading_fee),
            "network_fee_usd": 0.0,
            "total_cost_usd": float(total_cost),
            "execution_time_min": 1,
        }

    def calculate_binance_route_cost(
        self,
        amount_usd: float,
        token: str,
        network: Optional[NetworkType] = None,
    ) -> Dict:
        """Calcula el costo total de transferir a Binance, convertir 1:1 y retornar a Ripio."""
        if network is None:
            network = self.preferred_network

        fee_one_way = self.network_fees.get(token.upper(), {}).get(network, 1.5)
        network_fee_total = fee_one_way * 2.0
        binance_fee = amount_usd * self.binance_swap_fee
        total_cost = network_fee_total + binance_fee

        return {
            "route": RouteType.BINANCE_ROUTE,
            "spread_cost_usd": 0.0,
            "trading_fee_usd": float(binance_fee),
            "network_fee_usd": float(network_fee_total),
            "network": network.value,
            "total_cost_usd": float(total_cost),
            "execution_time_min": 45,
        }

    async def calculate_optimal_route(
        self,
        from_token: str,
        to_token: str,
        amount_usd: float,
        expected_arb_spread_pct: Optional[float] = None,
    ) -> Dict:
        """
        Determina la ruta de menor costo y evalúa el diferencial de arbitraje
        entre exchanges contra el costo total de la ruta multiplicado por el margen de seguridad.
        """
        spread_info = await self.get_ripio_swap_spread(from_token, to_token)
        if not spread_info:
            return {
                "route_type": RouteType.NO_ROUTE,
                "reason": "Cannot get Ripio spread",
                "total_cost_usd": float("inf"),
                "is_profitable": False,
            }

        spread_pct = float(spread_info["spread_pct"])
        dislocation_pct = float(spread_info.get("dislocation_pct", abs(spread_info["mid"] - 1.0) * 100.0))

        ripio_cost = self.calculate_ripio_direct_cost(amount_usd, spread_pct)
        binance_cost = self.calculate_binance_route_cost(amount_usd, from_token)

        if ripio_cost["total_cost_usd"] <= binance_cost["total_cost_usd"]:
            optimal = dict(ripio_cost)
            optimal["route_type"] = RouteType.RIPIO_DIRECT
            optimal["reason"] = (
                f"Ripio cheaper: ${ripio_cost['total_cost_usd']:.2f} <= "
                f"${binance_cost['total_cost_usd']:.2f}"
            )
        else:
            optimal = dict(binance_cost)
            optimal["route_type"] = RouteType.BINANCE_ROUTE
            optimal["reason"] = (
                f"Binance cheaper: ${binance_cost['total_cost_usd']:.2f} < "
                f"${ripio_cost['total_cost_usd']:.2f}"
            )

        # Evaluar el diferencial de arbitraje entre exchanges contra el costo total de la ruta
        arb_differential_pct = (
            float(expected_arb_spread_pct)
            if expected_arb_spread_pct is not None
            else max(dislocation_pct, spread_pct)
        )
        expected_gain = amount_usd * (arb_differential_pct / 100.0)
        min_required_gain = optimal["total_cost_usd"] * self.min_profit_margin

        optimal["spread_info"] = spread_info
        optimal["amount_usd"] = amount_usd
        optimal["arb_differential_pct"] = arb_differential_pct
        optimal["expected_gain_usd"] = float(expected_gain)
        optimal["min_required_gain_usd"] = float(min_required_gain)
        optimal["is_profitable"] = bool(expected_gain > min_required_gain)
        optimal["ripio_direct_cost_usd"] = ripio_cost["total_cost_usd"]
        optimal["binance_route_cost_usd"] = binance_cost["total_cost_usd"]

        return optimal

    async def execute_ripio_direct(self, from_token: str, to_token: str, amount: float) -> bool:
        """Ejecuta swap directo en Ripio (simulado en modo paper/demo)."""
        logger.info(f"[ROUTER] Executing RIPIO DIRECT: {amount} {from_token} -> {to_token}")
        return True

    async def execute_binance_route(
        self,
        from_token: str,
        to_token: str,
        amount: float,
        network: Optional[NetworkType] = None,
    ) -> bool:
        """Ejecuta ruta puente vía Binance sobre la red seleccionada."""
        net = network or self.preferred_network
        logger.info(
            f"[ROUTER] Executing BINANCE ROUTE: {amount} {from_token} -> {to_token} ({net.value})"
        )
        return True

    async def execute_optimal_route(
        self,
        from_token: str,
        to_token: str,
        amount_usd: float,
        expected_arb_spread_pct: Optional[float] = None,
    ) -> Dict:
        """Calcula la ruta óptima y la ejecuta únicamente si supera el umbral de rentabilidad."""
        route = await self.calculate_optimal_route(
            from_token, to_token, amount_usd, expected_arb_spread_pct=expected_arb_spread_pct
        )
        if not route.get("is_profitable", False):
            return {"success": False, "reason": "Not profitable", "route": route}

        route_type = route["route_type"]
        if route_type == RouteType.RIPIO_DIRECT:
            success = await self.execute_ripio_direct(from_token, to_token, amount_usd)
        elif route_type == RouteType.BINANCE_ROUTE:
            net = NetworkType(route.get("network", self.preferred_network.value))
            success = await self.execute_binance_route(from_token, to_token, amount_usd, net)
        else:
            success = False

        return {
            "success": success,
            "route": route,
            "timestamp": datetime.now().isoformat(),
        }

    def get_status(self) -> Dict:
        """Retorna la configuración activa del enrutador inter-exchange."""
        return {
            "preferred_network": self.preferred_network.value,
            "min_profit_margin": self.min_profit_margin,
            "ripio_taker_fee": self.ripio_taker_fee,
            "binance_swap_fee": self.binance_swap_fee,
            "network_fees": {
                token: {net.value: fee for net, fee in fees.items()}
                for token, fees in self.network_fees.items()
            },
        }
