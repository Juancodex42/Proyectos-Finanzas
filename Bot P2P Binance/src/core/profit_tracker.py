"""
Módulo de cálculo y proyección de ganancias P2P (ProfitTracker).
Calcula ganancia realizada sobre ventas cerradas y ganancia proyectada sobre stock en cartera.
Referencia de diseño: docs/ARQUITECTURA.md
"""
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Any

from data.database import Database
from data.models import ProfitReport
from core.sell_advisor import SellAdvisor
from config.settings import DEFAULT_BINANCE_SELL_TC_FALLBACK

logger = logging.getLogger(__name__)


class ProfitTracker:
    """
    Rastrea y calcula la rentabilidad real y proyectada de la operatoria P2P.
    """

    def __init__(self, db: Database, binance_client: Optional[Any] = None):
        self.db = db
        self.client = binance_client
        self._cached_sell_price: float = 0.0
        self._cached_sell_source: str = ""
        self._cached_sell_ts: float = 0.0
        self._cache_ttl_seconds: float = 60.0

    async def get_published_sell_price(self) -> tuple[float, str]:
        """
        Obtiene el precio de venta publicado más representativo:
        1. Anuncios propios SELL activos en Binance (precio mínimo para salida rápida).
        2. Fallback: Precio sugerido por SellAdvisor (Cluster 1).
        3. Fallback: Benchmark de MercadoPagoNew en SQLite.
        """
        now = time.time()
        if self._cached_sell_price > 0 and (now - self._cached_sell_ts) < self._cache_ttl_seconds:
            return self._cached_sell_price, self._cached_sell_source

        # 1. Intentar consultar anuncios propios de venta activos en Binance SAPI
        if self.client and hasattr(self.client, "list_my_ads"):
            try:
                res = await self.client.list_my_ads(trade_type="SELL", page=1, rows=20)
                if isinstance(res, dict) and "data" in res:
                    active_ads = [
                        item for item in res["data"]
                        if item.get("advStatus") == 1 and float(item.get("price", 0) or 0) > 0
                    ]
                    if active_ads:
                        # Ordenar por precio ascendente para tomar la salida más rápida y conservadora
                        active_ads.sort(key=lambda x: float(x.get("price", 0)))
                        best_ad = active_ads[0]
                        price = float(best_ad.get("price", 0))
                        adv_no = str(best_ad.get("advNo", ""))
                        short_no = adv_no[-4:] if len(adv_no) >= 4 else adv_no
                        source = f"Anuncio publicado #{short_no} (${price:,.2f})"

                        self._cached_sell_price = price
                        self._cached_sell_source = source
                        self._cached_sell_ts = now
                        return price, source
            except Exception as e:
                logger.debug("No se pudieron obtener anuncios SELL de Binance para proyección: %s", e)

        # 2. Fallback: SellAdvisor (Cluster 1 - Billeteras Masivas)
        try:
            advisor = SellAdvisor(self.db)
            advice_list = advisor.get_sell_advice()
            if advice_list and advice_list[0].suggested_price > 0 and advice_list[0].is_valid_data:
                price = advice_list[0].suggested_price
                source = f"SellAdvisor Cluster 1 (${price:,.2f})"
                self._cached_sell_price = price
                self._cached_sell_source = source
                self._cached_sell_ts = now
                return price, source
        except Exception as e:
            logger.debug("Error obteniendo sugerencia de SellAdvisor: %s", e)

        # 3. Fallback: Benchmark en base de datos
        try:
            bms = self.db.get_latest_benchmarks() if self.db else {}
            mp_bm = bms.get("MercadoPagoNew")
            if mp_bm and mp_bm.avg_top_n_price > 0:
                price = round(mp_bm.avg_top_n_price, 2)
                source = f"Benchmark Mercado Pago (${price:,.2f})"
                self._cached_sell_price = price
                self._cached_sell_source = source
                self._cached_sell_ts = now
                return price, source
        except Exception as e:
            logger.debug("Error obteniendo benchmark de DB: %s", e)

        return 0.0, "Sin precio de venta disponible"

    def _get_lookback_buy_tc(self, ref_date: str) -> float:
        """
        Calcula el costo ponderado de compras previas recientes (lookback 48hs)
        para cuando el día actual registra ventas de stock previo sin compras aún.
        """
        try:
            with self.db._lock:
                conn = self.db.connect()
                rows = conn.execute(
                    "SELECT amount_ars, amount_crypto, tc_implicito, asset FROM detected_orders "
                    "WHERE trade_type = 'BUY' "
                    "AND (DATE(detected_at, 'localtime') < ? OR DATE(detected_at) < ?) "
                    "ORDER BY detected_at DESC LIMIT 30",
                    (ref_date, ref_date),
                ).fetchall()

                if not rows:
                    return 0.0

                total_ars = 0.0
                total_usdt = 0.0
                for r in rows:
                    ars = float(r["amount_ars"] or 0.0)
                    crypto = float(r["amount_crypto"] or 0.0)
                    tc = float(r["tc_implicito"] or 0.0)
                    asset = str(r["asset"] or "USDT").upper()

                    if asset == "USDT":
                        u_equiv = crypto
                    elif tc > 0:
                        u_equiv = ars / tc
                    else:
                        u_equiv = (ars / DEFAULT_BINANCE_SELL_TC_FALLBACK) if DEFAULT_BINANCE_SELL_TC_FALLBACK > 0 else crypto

                    total_ars += ars
                    total_usdt += u_equiv

                return (total_ars / total_usdt) if total_usdt > 0 else 0.0
        except Exception as e:
            logger.warning("Error calculando lookback de costo de compra: %s", e)
            return 0.0

    def get_effective_wac_cost(self, date_str: Optional[str] = None) -> float:
        """
        Retorna el Costo Promedio Ponderado de Compra (WAC) de las compras del día
        o con lookback de 48hs si hoy no hubo compras aún.
        """
        today = date_str or datetime.now().strftime("%Y-%m-%d")
        with self.db._lock:
            conn = self.db.connect()
            buys = conn.execute(
                "SELECT amount_ars, amount_crypto, tc_implicito, asset FROM detected_orders "
                "WHERE trade_type = 'BUY' "
                "AND (DATE(detected_at, 'localtime') = ? OR DATE(detected_at) = ?) "
                "AND order_no NOT IN ("
                "  SELECT order_no FROM liquidity "
                "  WHERE event_type = 'historical_sync' AND order_no IS NOT NULL AND order_no != ''"
                ")",
                (today, today),
            ).fetchall()

        total_buy_ars = 0.0
        total_buy_usdt = 0.0
        for b in buys:
            ars = float(b["amount_ars"] or 0.0)
            crypto = float(b["amount_crypto"] or 0.0)
            tc = float(b["tc_implicito"] or 0.0)
            asset = str(b["asset"] or "USDT").upper()
            if asset == "USDT":
                u_equiv = crypto
            elif tc > 0:
                u_equiv = ars / tc
            else:
                u_equiv = (ars / DEFAULT_BINANCE_SELL_TC_FALLBACK) if DEFAULT_BINANCE_SELL_TC_FALLBACK > 0 else crypto
            total_buy_ars += ars
            total_buy_usdt += u_equiv

        if total_buy_usdt > 0:
            return round(total_buy_ars / total_buy_usdt, 2)

        lookback_cost = self._get_lookback_buy_tc(today)
        return round(lookback_cost, 2) if lookback_cost > 0 else 0.0

    async def calculate_profit(self, date_str: Optional[str] = None) -> ProfitReport:

        """
        Calcula la ganancia del día combinando el spread realizado de ventas cerradas
        y la proyección de ganancia sobre el inventario aún en cartera (medio pesos, medio USDT).
        """
        today = date_str or datetime.now().strftime("%Y-%m-%d")

        with self.db._lock:
            conn = self.db.connect()

            # 1. Compras del día
            buys = conn.execute(
                "SELECT order_no, asset, amount_crypto, amount_ars, price, tc_implicito, detected_at "
                "FROM detected_orders "
                "WHERE trade_type = 'BUY' "
                "AND (DATE(detected_at, 'localtime') = ? OR DATE(detected_at) = ?) "
                "AND order_no NOT IN ("
                "  SELECT order_no FROM liquidity "
                "  WHERE event_type = 'historical_sync' AND order_no IS NOT NULL AND order_no != ''"
                ")",
                (today, today),
            ).fetchall()

            # 2. Ventas del día
            sells = conn.execute(
                "SELECT order_no, asset, amount_crypto, amount_ars, price, tc_implicito, detected_at "
                "FROM detected_orders "
                "WHERE trade_type = 'SELL' "
                "AND (DATE(detected_at, 'localtime') = ? OR DATE(detected_at) = ?) "
                "AND order_no NOT IN ("
                "  SELECT order_no FROM liquidity "
                "  WHERE event_type = 'historical_sync' AND order_no IS NOT NULL AND order_no != ''"
                ")",
                (today, today),
            ).fetchall()

        total_buy_ars = 0.0
        total_buy_usdt = 0.0
        for b in buys:
            ars = float(b["amount_ars"] or 0.0)
            crypto = float(b["amount_crypto"] or 0.0)
            tc = float(b["tc_implicito"] or 0.0)
            asset = str(b["asset"] or "USDT").upper()

            if asset == "USDT":
                u_equiv = crypto
            elif tc > 0:
                u_equiv = ars / tc
            else:
                u_equiv = (ars / DEFAULT_BINANCE_SELL_TC_FALLBACK) if DEFAULT_BINANCE_SELL_TC_FALLBACK > 0 else (crypto if crypto > 0 else 0.0)

            total_buy_ars += ars
            total_buy_usdt += u_equiv

        total_sell_ars = 0.0
        total_sell_usdt = 0.0
        for s in sells:
            ars = float(s["amount_ars"] or 0.0)
            crypto = float(s["amount_crypto"] or 0.0)
            tc = float(s["tc_implicito"] or 0.0)
            asset = str(s["asset"] or "USDT").upper()

            if asset == "USDT":
                u_equiv = crypto
            elif tc > 0:
                u_equiv = ars / tc
            else:
                u_equiv = (ars / DEFAULT_BINANCE_SELL_TC_FALLBACK) if DEFAULT_BINANCE_SELL_TC_FALLBACK > 0 else (crypto if crypto > 0 else 0.0)

            total_sell_ars += ars
            total_sell_usdt += u_equiv

        avg_buy_tc = (total_buy_ars / total_buy_usdt) if total_buy_usdt > 0 else 0.0
        avg_sell_tc = (total_sell_ars / total_sell_usdt) if total_sell_usdt > 0 else 0.0

        # Si hoy no hubo compras pero sí ventas (se vendió remanente de días anteriores),
        # estimar el costo de compra mediante lookback histórico.
        effective_buy_tc = avg_buy_tc
        if effective_buy_tc <= 0 and total_sell_usdt > 0:
            effective_buy_tc = self._get_lookback_buy_tc(today)

        # Precio de venta publicado y fuente
        projected_sell_price, proj_source = await self.get_published_sell_price()

        # Si aún no tenemos effective_buy_tc y tampoco hay historial, usar breakeven conservador (no inventar ganancia)
        if effective_buy_tc <= 0 and projected_sell_price > 0:
            effective_buy_tc = projected_sell_price

        # 3. Ganancia Realizada (sobre lo ya vendido y cobrado)
        realized_profit_ars = 0.0
        if total_sell_usdt > 0 and effective_buy_tc > 0:
            # Si el costo medio fue inferior a la venta, el spread es positivo
            spread_realized = avg_sell_tc - effective_buy_tc
            realized_profit_ars = spread_realized * total_sell_usdt

        # 4. Stock Remanente y Ganancia Proyectada
        remaining_stock_usdt = max(total_buy_usdt - total_sell_usdt, 0.0)
        projected_profit_ars = 0.0

        if remaining_stock_usdt > 0.01 and projected_sell_price > 0 and effective_buy_tc > 0:
            spread_projected = projected_sell_price - effective_buy_tc
            if spread_projected > 0:
                projected_profit_ars = spread_projected * remaining_stock_usdt

        # Ganancia total acumulada
        total_profit_ars = max(realized_profit_ars + projected_profit_ars, 0.0)

        is_mixed = bool(remaining_stock_usdt >= 1.0 and total_sell_usdt >= 1.0)

        return ProfitReport(
            date=today,
            total_profit_ars=round(total_profit_ars, 2),
            realized_profit_ars=round(realized_profit_ars, 2),
            projected_profit_ars=round(projected_profit_ars, 2),
            total_buy_ars=round(total_buy_ars, 2),
            total_buy_usdt=round(total_buy_usdt, 4),
            avg_buy_tc=round(avg_buy_tc or effective_buy_tc, 2),
            total_sell_ars=round(total_sell_ars, 2),
            total_sell_usdt=round(total_sell_usdt, 4),
            avg_sell_tc=round(avg_sell_tc, 2),
            remaining_stock_usdt=round(remaining_stock_usdt, 4),
            projected_sell_price=round(projected_sell_price, 2),
            projection_source=proj_source,
            buy_orders_count=len(buys),
            sell_orders_count=len(sells),
            is_mixed_state=is_mixed,
        )
