"""
Repositorio Mixin de órdenes detectadas, arbitraje Fiwind, eventos de liquidez y métricas diarias.
Referencia de diseño: docs/ARQUITECTURA.md
"""
import json
import logging
import sqlite3
import statistics
from datetime import datetime
from typing import Optional, Any, List, Dict, Set
from data.models import DetectedOrder
from data.schema import _parse_db_datetime

logger = logging.getLogger("data.orders")


class OrderRepoMixin:
    """Operaciones de persistencia para órdenes detectadas, fiwind, liquidez y métricas diarias."""
    def save_detected_order(self, order: DetectedOrder, fiwind_bid: Optional[float] = None):
        with self._lock:
            conn = self.connect()
            try:
                bid_val = fiwind_bid if fiwind_bid is not None else getattr(order, "fiwind_bid", None)
                conn.execute(
                    "INSERT OR IGNORE INTO detected_orders "
                    "(order_no, adv_no, timestamp, asset, trade_type, amount_crypto, "
                    "amount_ars, price, tc_implicito, payment_method, counterparty, status, fiwind_bid) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        order.order_no, order.adv_no, order.timestamp, order.asset,
                        order.trade_type, order.amount_crypto, order.amount_ars,
                        order.price, order.tc_implicito, order.payment_method,
                        order.counterparty, order.status, bid_val,
                    ),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                try:
                    conn.rollback()
                except Exception:
                    pass
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                raise

    def update_order_fiwind_bid(self, order_no: str, fiwind_bid: float):
        """Actualiza la cotización de Fiwind bid asociada a una orden de compra."""
        if not order_no or fiwind_bid <= 0:
            return
        with self._lock:
            conn = self.connect()
            try:
                conn.execute(
                    "UPDATE detected_orders SET fiwind_bid = ? WHERE order_no = ?",
                    (float(fiwind_bid), str(order_no)),
                )
                conn.commit()
            except Exception as e:
                logger.debug("Error actualizando fiwind_bid para orden %s: %s", order_no, e)

    def save_fiwind_quote(self, bid: float, ask: float):
        """Guarda un registro continuo de la cotización de Fiwind (bid y ask)."""
        if bid <= 0 or ask <= 0:
            return
        self._execute_write(
            "INSERT INTO fiwind_quotes (bid, ask) VALUES (?, ?)",
            (float(bid), float(ask)),
        )

    def get_fiwind_buy_spread_stats(self, lookback_days: int = 30) -> dict:
        """
        Calcula la mediana y estadísticas de la brecha entre compras (trade_type='BUY')
        y el bid de Fiwind correspondiente (fiwind_bid - tc_implicito).
        """
        with self._lock:
            conn = self.connect()
            # 1. Compras dentro de la ventana de lookback
            rows = conn.execute(
                "SELECT order_no, timestamp, detected_at, tc_implicito, fiwind_bid "
                "FROM detected_orders "
                "WHERE trade_type = 'BUY' AND tc_implicito > 0 "
                "AND (DATE(detected_at) >= DATE('now', ?) OR DATE(timestamp) >= DATE('now', ?)) "
                "ORDER BY detected_at DESC",
                (f"-{lookback_days} days", f"-{lookback_days} days"),
            ).fetchall()

            # Fallback a todas las compras si la ventana no arroja registros
            if not rows:
                rows = conn.execute(
                    "SELECT order_no, timestamp, detected_at, tc_implicito, fiwind_bid "
                    "FROM detected_orders "
                    "WHERE trade_type = 'BUY' AND tc_implicito > 0 "
                    "ORDER BY detected_at DESC",
                ).fetchall()

            spreads = []
            for r in rows:
                tc = float(r["tc_implicito"] or 0.0)
                if tc <= 0:
                    continue

                fw_bid = r["fiwind_bid"]
                if fw_bid is not None and float(fw_bid) > 0:
                    spreads.append(float(fw_bid) - tc)
                else:
                    ts = r["detected_at"] or r["timestamp"]
                    if ts:
                        # Buscar la cotización de fiwind_quotes más cercana en el tiempo
                        match = conn.execute(
                            "SELECT bid, timestamp FROM fiwind_quotes "
                            "ORDER BY ABS(strftime('%s', timestamp) - strftime('%s', ?)) ASC LIMIT 1",
                            (str(ts),),
                        ).fetchone()
                        if match and match["bid"] and float(match["bid"]) > 0:
                            td_row = conn.execute(
                                "SELECT ABS(strftime('%s', ?) - strftime('%s', ?))",
                                (str(ts), str(match["timestamp"])),
                            ).fetchone()
                            time_diff = td_row[0] if td_row else None
                            # Aceptar match si ocurrió dentro de 1 hora (3600s)
                            if time_diff is not None and time_diff <= 3600:
                                spreads.append(float(match["bid"]) - tc)

            if spreads:
                med = statistics.median(spreads)
                mean = statistics.mean(spreads)
                return {
                    "median": round(med, 2),
                    "mean": round(mean, 2),
                    "count": len(spreads),
                    "min": round(min(spreads), 2),
                    "max": round(max(spreads), 2),
                }

            return {"median": None, "mean": None, "count": 0}

    def get_all_detected_order_nos(self) -> set[str]:
        """Retorna todos los order_nos registrados en detected_orders."""
        with self._lock:
            conn = self.connect()
            rows = conn.execute("SELECT order_no FROM detected_orders").fetchall()
            return {r["order_no"] for r in rows if r["order_no"]}

    def get_all_detected_swap_ids(self) -> set[str]:
        """Retorna todos los IDs de swaps registrados en la tabla liquidity."""
        with self._lock:
            conn = self.connect()
            rows = conn.execute(
                "SELECT order_no FROM liquidity WHERE event_type = 'swap' AND order_no IS NOT NULL AND order_no != ''"
            ).fetchall()
            return {r["order_no"] for r in rows if r["order_no"]}

    def get_new_order_nos(self, known_nos: set[str]) -> list[str]:
        """Retorna order_nos que están en DB pero no en known_nos."""
        all_nos = self.get_all_detected_order_nos()
        return list(all_nos - known_nos)

    def get_latest_detected_order_time(self) -> Optional[datetime]:
        """Retorna la fecha y hora de la última orden registrada en detected_orders."""
        with self._lock:
            conn = self.connect()
            row = conn.execute("SELECT MAX(timestamp) as max_ts FROM detected_orders").fetchone()
            if row and row["max_ts"]:
                return _parse_db_datetime(row["max_ts"])
            return None

    # ── Liquidity ─────────────────────────────────────────────────────

    def save_liquidity_event(
        self, event_type: str, balance_after: float,
        amount_ars: float = 0, order_no: str = "",
        asset: str = "", amount_crypto: float = 0, notes: str = "",
    ):
        self._execute_write(
            "INSERT INTO liquidity "
            "(event_type, order_no, asset, amount_ars, amount_crypto, balance_after, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (event_type, order_no, asset, amount_ars, amount_crypto, balance_after, notes),
        )

    def get_current_balance(self) -> float:
        with self._lock:
            conn = self.connect()
            row = conn.execute(
                "SELECT balance_after FROM liquidity ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return float(row["balance_after"]) if (row and row["balance_after"] is not None) else 0.0

    # ── Spot Prices ───────────────────────────────────────────────────

    def save_spot_prices(self, prices: dict[str, float]):
        self._execute_write(
            "INSERT INTO spot_prices (asset, price_usdt) VALUES (?, ?)",
            executemany=True,
            many_params=[(asset, price) for asset, price in prices.items()],
        )


    def get_daily_stats(self, date_str: Optional[str] = None, profit_ars: Optional[float] = None) -> dict:
        with self._lock:
            conn = self.connect()
            today = date_str or datetime.now().strftime("%Y-%m-%d")

            repositions = conn.execute(
                "SELECT COUNT(*) as cnt FROM price_changes WHERE DATE(timestamp, 'localtime') = ?",
                (today,),
            ).fetchone()

            orders_buy = conn.execute(
                "SELECT COUNT(*) as cnt, COALESCE(SUM(amount_ars), 0) as total "
                "FROM detected_orders WHERE trade_type = 'BUY' "
                "AND (DATE(detected_at, 'localtime') = ? OR DATE(detected_at) = ?) "
                "AND order_no NOT IN ("
                "SELECT order_no FROM liquidity "
                "WHERE event_type = 'historical_sync' AND order_no IS NOT NULL AND order_no != ''"
                ")",
                (today, today),
            ).fetchone()

            orders_sell = conn.execute(
                "SELECT COUNT(*) as cnt, COALESCE(SUM(amount_ars), 0) as total "
                "FROM detected_orders WHERE trade_type = 'SELL' "
                "AND (DATE(detected_at, 'localtime') = ? OR DATE(detected_at) = ?) "
                "AND order_no NOT IN ("
                "SELECT order_no FROM liquidity "
                "WHERE event_type = 'historical_sync' AND order_no IS NOT NULL AND order_no != ''"
                ")",
                (today, today),
            ).fetchone()

            # Calcular o asignar ganancia del día
            calculated_profit = profit_ars
            if calculated_profit is None:
                # Estimación sincrónica rápida en base a datos de BD
                try:
                    buy_rows = conn.execute(
                        "SELECT asset, amount_crypto, amount_ars, tc_implicito FROM detected_orders "
                        "WHERE trade_type = 'BUY' "
                        "AND (DATE(detected_at, 'localtime') = ? OR DATE(detected_at) = ?) "
                        "AND order_no NOT IN ("
                        "SELECT order_no FROM liquidity "
                        "WHERE event_type = 'historical_sync' AND order_no IS NOT NULL AND order_no != ''"
                        ")",
                        (today, today),
                    ).fetchall()
                    sell_rows = conn.execute(
                        "SELECT asset, amount_crypto, amount_ars FROM detected_orders "
                        "WHERE trade_type = 'SELL' "
                        "AND (DATE(detected_at, 'localtime') = ? OR DATE(detected_at) = ?) "
                        "AND order_no NOT IN ("
                        "SELECT order_no FROM liquidity "
                        "WHERE event_type = 'historical_sync' AND order_no IS NOT NULL AND order_no != ''"
                        ")",
                        (today, today),
                    ).fetchall()

                    t_buy_ars = sum(float(r["amount_ars"] or 0) for r in buy_rows)
                    t_buy_usdt = sum(
                        float(r["amount_crypto"] or 0) if str(r["asset"]).upper() == "USDT"
                        else ((float(r["amount_ars"] or 0) / float(r["tc_implicito"])) if float(r["tc_implicito"] or 0) > 0 else float(r["amount_crypto"] or 0))
                        for r in buy_rows
                    )
                    t_sell_ars = sum(float(r["amount_ars"] or 0) for r in sell_rows)
                    t_sell_usdt = sum(float(r["amount_crypto"] or 0) for r in sell_rows)

                    avg_b_tc = (t_buy_ars / t_buy_usdt) if t_buy_usdt > 0 else 0.0
                    avg_s_tc = (t_sell_ars / t_sell_usdt) if t_sell_usdt > 0 else 0.0

                    # Obtener benchmark de venta reciente
                    bm_row = conn.execute(
                        "SELECT avg_top10_price FROM usdt_sell_benchmark ORDER BY timestamp DESC LIMIT 1"
                    ).fetchone()
                    bm_p = float(bm_row["avg_top10_price"]) if bm_row and bm_row["avg_top10_price"] else (avg_b_tc + 10.0)

                    realized = (avg_s_tc - avg_b_tc) * t_sell_usdt if (avg_b_tc > 0 and t_sell_usdt > 0) else 0.0
                    rem_stock = max(t_buy_usdt - t_sell_usdt, 0.0)
                    projected = (bm_p - avg_b_tc) * rem_stock if (rem_stock > 0 and avg_b_tc > 0 and bm_p > avg_b_tc) else 0.0
                    calculated_profit = max(realized + projected, 0.0)
                except Exception:
                    calculated_profit = 0.0

            return {
                "date": today,
                "repositions": repositions["cnt"],
                "buy_orders": orders_buy["cnt"],
                "buy_volume_ars": orders_buy["total"],
                "sell_orders": orders_sell["cnt"],
                "sell_volume_ars": orders_sell["total"],
                "balance_ars": self.get_current_balance(),
                "daily_profit_ars": round(calculated_profit, 2),
            }


