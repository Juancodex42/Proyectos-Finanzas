"""
Módulo de Seguimiento de Órdenes y Swaps (OrderTracker).
Rastrea órdenes en curso (incluyendo apelaciones), órdenes completadas y conversiones internas.
Referencia de diseño: docs/ARQUITECTURA.md
"""
import logging
import time
from datetime import datetime
from typing import Callable, Optional

from core.network.binance_api import BinanceApi
from data.database import Database
from data.models import DetectedOrder, DetectedSwap

logger = logging.getLogger(__name__)


class OrderTracker:
    """
    Rastreador de órdenes P2P, disputas/apelaciones y compromiso de capital ARS.
    """

    def __init__(self) -> None:
        self.known_order_nos: set[str] = set()
        self.known_swap_ids: set[str] = set()
        self.notified_open_orders: set[str] = set()
        self.notified_open_sell_orders: dict[str, str] = {}
        self.new_incoming_orders: list[DetectedOrder] = []
        self.surplus_decremented_orders: set[str] = set()
        self.startup_open_order_nos: set[str] = set()
        self.committed_ars: float = 0.0
        self.init_time: float = 0.0

    def consume_incoming_orders(self) -> list[DetectedOrder]:
        """Retorna y vacía la lista de nuevas órdenes entrantes detectadas en curso."""
        orders = list(self.new_incoming_orders)
        self.new_incoming_orders.clear()
        return orders

    async def sync_open_buy_orders(
        self, client: BinanceApi, spot_prices: dict[str, float], db: Database
    ) -> tuple[list[dict], bool]:
        """
        Monitorea órdenes de compra en curso (status 1, 2, 3, 5 incluyendo apelaciones).
        Evita fugar liquidez comprometida en órdenes disputadas y detecta órdenes entrantes.
        """
        open_items: list[dict] = []
        open_fetch_ok = True
        try:
            open_res = await client.list_orders(
                trade_type="BUY",
                order_status_list=[1, 2, 3, 5],
                rows=50,
            )
            open_items = open_res.get("data", [])
            for item in open_items:
                order_no = str(item.get("orderNumber", item.get("orderNo", "")))
                st = str(item.get("orderStatus", "1"))
                if not order_no or order_no in self.notified_open_orders or order_no in self.known_order_nos:
                    continue

                self.notified_open_orders.add(order_no)
                asset = item.get("asset", "")
                amount_crypto = float(item.get("amount", 0))
                amount_ars = float(item.get("totalPrice", item.get("fiatAmount", 0)))
                raw_price = float(item.get("unitPrice", item.get("price", 0)) or 0.0)
                price = raw_price if raw_price > 0 else (round(amount_ars / amount_crypto, 2) if amount_crypto > 0 else 0.0)
                spot = spot_prices.get(asset, 1.0)
                tc = round(price / spot, 2) if spot > 0 else 0.0

                counterparty = (
                    item.get("sellerNickname") or item.get("buyerNickname")
                    or item.get("counterPartNickName", "") or ""
                )
                payment_method = item.get("payType", item.get("tradeMethodName", "")) or ""

                inc_order = DetectedOrder(
                    order_no=order_no, adv_no=item.get("advNo", ""), asset=asset, trade_type="BUY",
                    amount_crypto=amount_crypto, amount_ars=amount_ars, price=price, tc_implicito=tc,
                    payment_method=payment_method, counterparty=counterparty, status=st, timestamp=datetime.now(),
                )
                self.new_incoming_orders.append(inc_order)

                if order_no not in self.surplus_decremented_orders and inc_order.adv_no and amount_crypto > 0:
                    try:
                        rem = db.decrement_ad_surplus(inc_order.adv_no, amount_crypto)
                        self.surplus_decremented_orders.add(order_no)
                        if rem is not None:
                            logger.info("📉 Surplus anuncio %s decrementado: %.6f %s (restante: %.6f)", inc_order.adv_no, amount_crypto, asset, rem)
                    except Exception as e_dec:
                        logger.debug("Error descontando surplus anuncio %s: %s", inc_order.adv_no, e_dec)
                logger.info("📥 Compra entrante detectada: %s (%.4f %s por $%.2f ARS, status=%s)", order_no, amount_crypto, asset, amount_ars, st)
        except Exception as e:
            open_fetch_ok = False
            logger.error("Error leyendo órdenes abiertas de compra: %s", e)
        return open_items, open_fetch_ok

    async def sync_open_sell_orders(
        self, client: BinanceApi, spot_prices: dict[str, float], db: Database
    ) -> None:
        """Monitorea órdenes de venta en curso (status 1, 2, 3, 5)."""
        try:
            open_res = await client.list_orders(
                trade_type="SELL",
                order_status_list=[1, 2, 3, 5],
                rows=50,
            )
            for item in open_res.get("data", []):
                if str(item.get("tradeType", "SELL")).upper() != "SELL":
                    continue
                order_no = str(item.get("orderNumber", item.get("orderNo", "")))
                st = str(item.get("orderStatus", "1"))
                if not order_no or order_no in self.known_order_nos:
                    continue

                prev_st = self.notified_open_sell_orders.get(order_no)
                should_notify = (prev_st is None) or (prev_st == "1" and st == "2") or (prev_st != st and st in ("3", "5"))
                if not should_notify:
                    continue

                self.notified_open_sell_orders[order_no] = st
                asset = item.get("asset", "")
                amount_crypto = float(item.get("amount", 0))
                amount_ars = float(item.get("totalPrice", item.get("fiatAmount", 0)))
                raw_price = float(item.get("unitPrice", item.get("price", 0)) or 0.0)
                price = raw_price if raw_price > 0 else (round(amount_ars / amount_crypto, 2) if amount_crypto > 0 else 0.0)
                spot = spot_prices.get(asset, 1.0)
                tc = round(price / spot, 2) if spot > 0 else 0.0

                counterparty = (
                    item.get("buyerNickname") or item.get("buyerRealName")
                    or item.get("counterPartNickName", "") or ""
                )
                payment_method = item.get("payType", item.get("tradeMethodName", "")) or ""

                inc_order = DetectedOrder(
                    order_no=order_no, adv_no=item.get("advNo", ""), asset=asset, trade_type="SELL",
                    amount_crypto=amount_crypto, amount_ars=amount_ars, price=price, tc_implicito=tc,
                    payment_method=payment_method, counterparty=counterparty, status=st, timestamp=datetime.now(),
                )
                self.new_incoming_orders.append(inc_order)

                if order_no not in self.surplus_decremented_orders and inc_order.adv_no and amount_crypto > 0:
                    try:
                        rem = db.decrement_ad_surplus(inc_order.adv_no, amount_crypto)
                        self.surplus_decremented_orders.add(order_no)
                        if rem is not None:
                            logger.info("📉 Surplus venta %s decrementado: %.6f %s (restante: %.6f)", inc_order.adv_no, amount_crypto, asset, rem)
                    except Exception as e_dec:
                        logger.debug("Error descontando surplus venta %s: %s", inc_order.adv_no, e_dec)
                logger.info("📤 Venta en curso detectada: %s (%.4f %s por $%.2f ARS, status=%s)", order_no, amount_crypto, asset, amount_ars, st)
        except Exception as e:
            logger.error("Error leyendo órdenes abiertas de venta: %s", e)

    async def process_completed_orders(
        self,
        client: BinanceApi,
        trade_type: str,
        result: dict,
        spot_prices: dict[str, float],
        db: Database,
        on_order_completed: Callable[[str, float, str, float, str], None],
    ) -> list[DetectedOrder]:
        """Procesa órdenes completadas ([4]), actualiza saldos y persiste en base de datos."""
        new_orders: list[DetectedOrder] = []
        data = result.get("data", [])
        if not data:
            return new_orders

        _raw_offset = getattr(client, "_time_offset", 0)
        time_offset_ms = float(_raw_offset) if isinstance(_raw_offset, (int, float)) else 0.0
        effective_init_ms = int((self.init_time + time_offset_ms / 1000.0 - 5.0) * 1000)

        for item in data:
            order_no = str(item.get("orderNumber", item.get("orderNo", "")))
            if not order_no or order_no in self.known_order_nos:
                continue

            self.known_order_nos.add(order_no)
            asset = item.get("asset", "")
            amount_crypto = float(item.get("amount", 0))
            amount_ars = float(item.get("totalPrice", item.get("fiatAmount", 0)))
            raw_price = float(item.get("unitPrice", item.get("price", 0)) or 0.0)
            price = raw_price if raw_price > 0 else (round(amount_ars / amount_crypto, 2) if amount_crypto > 0 else 0.0)
            spot = spot_prices.get(asset, 1.0)
            tc = round(price / spot, 2) if spot > 0 else 0.0

            counterparty = (
                item.get("sellerNickname" if trade_type == "BUY" else "buyerNickname")
                or item.get("buyerNickname" if trade_type == "BUY" else "sellerNickname")
                or item.get("counterPartNickName", "") or ""
            )
            payment_method = item.get("payType", item.get("tradeMethodName", "")) or ""

            create_time = int(item.get("createTime", 0) or 0)
            is_prior = (create_time > 0 and self.init_time > 0 and create_time < effective_init_ms and order_no not in self.startup_open_order_nos)

            if not is_prior and (not payment_method or not counterparty):
                try:
                    detail_res = await client.get_order_detail(order_no)
                    d_data = detail_res.get("data", {})
                    if isinstance(d_data, dict):
                        if not payment_method:
                            payment_method = d_data.get("payType", "") or ""
                        if not counterparty:
                            counterparty = (
                                d_data.get("sellerNickname" if trade_type == "BUY" else "buyerNickname")
                                or d_data.get("buyerNickname" if trade_type == "BUY" else "sellerNickname")
                                or d_data.get("counterPartNickName", "") or ""
                            )
                except Exception as e_det:
                    logger.debug("No se pudo obtener detalle para %s: %s", order_no, e_det)

            order = DetectedOrder(
                order_no=order_no, adv_no=item.get("advNo", ""), asset=asset, trade_type=trade_type,
                amount_crypto=amount_crypto, amount_ars=amount_ars, price=price, tc_implicito=tc,
                payment_method=payment_method, counterparty=counterparty, status=item.get("orderStatus", ""),
                timestamp=datetime.now(),
            )

            if not is_prior:
                balance_after = on_order_completed(trade_type, amount_ars, asset, amount_crypto, order.adv_no)
                event_type = "buy" if trade_type == "BUY" else "sell"
                if order.adv_no and amount_crypto > 0 and order_no not in self.surplus_decremented_orders:
                    try:
                        rem = db.decrement_ad_surplus(order.adv_no, amount_crypto)
                        self.surplus_decremented_orders.add(order_no)
                        if rem is not None:
                            logger.info("📉 Surplus anuncio %s decrementado: %.6f %s (restante: %.6f)", order.adv_no, amount_crypto, asset, rem)
                    except Exception as e_dec:
                        logger.debug("Error descontando surplus anuncio %s: %s", order.adv_no, e_dec)
                if isinstance(balance_after, (int, float)):
                    db.save_liquidity_event(
                        event_type=event_type, balance_after=float(balance_after), amount_ars=amount_ars,
                        order_no=order_no, asset=asset, amount_crypto=amount_crypto, notes="",
                    )
            else:
                event_type = "historical_sync"

            db.save_detected_order(order)
            if is_prior:
                db.save_liquidity_event(
                    event_type=event_type, balance_after=0.0, amount_ars=amount_ars,
                    order_no=order_no, asset=asset, amount_crypto=amount_crypto,
                    notes="Histórica precargada",
                )
            if not is_prior:
                new_orders.append(order)

        return new_orders

    async def sync_swaps(
        self, client: BinanceApi, assets: list[str], db: Database, current_balance: float
    ) -> list[DetectedSwap]:
        """Detecta conversiones en Binance Convert y trades en Spot."""
        new_swaps: list[DetectedSwap] = []
        _raw_offset = getattr(client, "_time_offset", 0)
        time_offset_ms = float(_raw_offset) if isinstance(_raw_offset, (int, float)) else 0.0
        init_time_ms = int((self.init_time + time_offset_ms / 1000.0 - 5.0) * 1000) if self.init_time > 0 else 0

        try:
            now_ms = int(time.time() * 1000)
            start_ms = max(init_time_ms - 60000, now_ms - 6 * 3600 * 1000) if init_time_ms > 0 else (now_ms - 6 * 3600 * 1000)
            res = await client.get_convert_trades(start_ms, now_ms, limit=15)
            for item in res.get("list", []):
                uid = f"convert_{item.get('orderId', '')}"
                c_time = int(item.get("createTime", 0))
                if c_time and init_time_ms and c_time < init_time_ms:
                    self.known_swap_ids.add(uid)
                    continue
                if uid and uid not in self.known_swap_ids:
                    self.known_swap_ids.add(uid)
                    fa, ta = item.get("fromAsset", ""), item.get("toAsset", "")
                    fam, tam, ratio = float(item.get("fromAmount", 0)), float(item.get("toAmount", 0)), float(item.get("ratio", 0))
                    swap = DetectedSwap(trade_id=uid, symbol=f"{fa}->{ta}", side="CONVERT", base_asset=fa, quote_asset=ta, base_amount=fam, quote_amount=tam, price=ratio, timestamp=datetime.now())
                    new_swaps.append(swap)
                    db.save_liquidity_event(event_type="swap", balance_after=current_balance, amount_ars=0.0, order_no=uid, asset=f"{fa}->{ta}", amount_crypto=tam, notes=f"Convert: {fam} {fa} -> {tam} {ta} @ {ratio}")
                    logger.info("🔄 Swap Convert detectado: %s %s -> %s %s", fam, fa, tam, ta)
        except Exception as e:
            logger.debug("Error revisando Convert: %s", e)

        for asset in assets:
            if asset in ["USDT", "ARS", "U"]:
                continue
            symbol = f"{asset}USDT"
            try:
                trades = await client.get_my_spot_trades(symbol=symbol, limit=5)
                for t in trades:
                    uid = f"spot_{symbol}_{t.get('id', '')}"
                    t_time = int(t.get("time", 0))
                    if t_time and init_time_ms and t_time < init_time_ms:
                        self.known_swap_ids.add(uid)
                        continue
                    if uid and uid not in self.known_swap_ids:
                        self.known_swap_ids.add(uid)
                        qty, p = float(t.get("qty", 0)), float(t.get("price", 0))
                        qqty = float(t.get("quoteQty", qty * p))
                        side = "BUY" if t.get("isBuyer", False) else "SELL"
                        swap = DetectedSwap(trade_id=uid, symbol=symbol, side=f"SPOT_{side}", base_asset=asset, quote_asset="USDT", base_amount=qty, quote_amount=qqty, price=p, timestamp=datetime.now())
                        new_swaps.append(swap)
                        db.save_liquidity_event(event_type="swap", balance_after=current_balance, amount_ars=0.0, order_no=uid, asset=symbol, amount_crypto=qty, notes=f"Spot {side}: {qty} {asset} @ ${p:,.2f} USDT")
                        logger.info("🔄 Spot trade detectado: %s %s %s @ $%.2f", side, qty, symbol, p)
            except Exception as e:
                logger.debug("Error revisando spot %s: %s", symbol, e)
        return new_swaps
