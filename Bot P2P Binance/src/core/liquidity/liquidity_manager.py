"""
Gestor de Liquidez ARS y Cálculo de Saldos (LiquidityManager).
Calcula el balance nominal, comprometido en compras abiertas y efectivo disponible.
Referencia de diseño: docs/ARQUITECTURA.md
"""
import logging
import time
from datetime import datetime
from typing import Optional

from config.settings import LIQUIDITY_BUFFER
from core.liquidity.order_tracker import OrderTracker
from core.network.binance_api import BinanceApi, BinanceClient
from data.database import Database
from data.models import BotConfig, DetectedOrder, DetectedSwap

logger = logging.getLogger(__name__)


class LiquidityManager:
    """
    Rastrea y gestiona la liquidez disponible en ARS para operaciones de compra.
    """

    def __init__(self, client: BinanceClient, db: Database, spot_client: Optional[object] = None) -> None:
        self.client = client
        self.db = db
        self.spot_client = spot_client
        self.tracker = OrderTracker()
        self._balance: float = 0.0

    @property
    def _known_order_nos(self) -> set[str]:
        return self.tracker.known_order_nos

    @property
    def _known_swap_ids(self) -> set[str]:
        return self.tracker.known_swap_ids

    @property
    def _notified_open_orders(self) -> set[str]:
        return self.tracker.notified_open_orders

    @property
    def _notified_open_sell_orders(self) -> dict[str, str]:
        return self.tracker.notified_open_sell_orders

    @property
    def _new_incoming_orders(self) -> list[DetectedOrder]:
        return self.tracker.new_incoming_orders

    @property
    def _surplus_decremented_orders(self) -> set[str]:
        return self.tracker.surplus_decremented_orders

    @property
    def _startup_open_order_nos(self) -> set[str]:
        return self.tracker.startup_open_order_nos

    @property
    def _committed_ars(self) -> float:
        return self.tracker.committed_ars

    @_committed_ars.setter
    def _committed_ars(self, val: float) -> None:
        self.tracker.committed_ars = val

    @property
    def _init_time(self) -> float:
        return self.tracker.init_time

    @_init_time.setter
    def _init_time(self, val: float) -> None:
        self.tracker.init_time = val

    async def initialize(self, config: BotConfig, spot_prices: Optional[dict[str, float]] = None) -> None:
        """Carga el balance inicial desde config y precarga órdenes pasadas conciliando offline."""
        self._balance = config.balance_ars
        self.tracker.init_time = time.time()
        logger.info("Balance inicial: $%.2f ARS", self._balance)

        db_orders: set[str] = set()
        try:
            db_orders = set(self.db.get_all_detected_order_nos())
            self.tracker.known_order_nos.update(db_orders)
            logger.info("Cargadas %d órdenes previas desde la base de datos", len(db_orders))
        except Exception as e:
            logger.warning("No se pudieron cargar órdenes previas desde BD: %s", e)

        latest_db_order_time = None
        try:
            latest_db_order_time = self.db.get_latest_detected_order_time()
        except Exception:
            pass

        try:
            for tt in ["BUY", "SELL"]:
                open_res = await self.client.list_orders(trade_type=tt, rows=50)
                for item in open_res.get("data", []):
                    order_no = str(item.get("orderNumber", item.get("orderNo", "")))
                    st_val = str(item.get("orderStatus", ""))
                    if order_no and st_val in ("1", "2", "3", "5", "TRADING", "BUYER_PAYED", "APPEALING", "CANCELLED_WITH_APPEAL"):
                        self.tracker.startup_open_order_nos.add(order_no)
                        if tt == "BUY":
                            self.tracker.committed_ars += float(item.get("totalPrice", item.get("fiatAmount", 0)))

                result = await self.client.list_orders(trade_type=tt, rows=50, order_status_list=[4])
                for item in result.get("data", []):
                    order_no = str(item.get("orderNumber", item.get("orderNo", "")))
                    if not order_no or str(item.get("orderStatus", "4")) not in ("4", "COMPLETED", ""):
                        continue

                    order_time_ms = int(item.get("createTime") or item.get("orderTime") or 0)
                    update_time_ms = int(item.get("updateTime", item.get("createTime", 0)) or order_time_ms)
                    is_recent = True
                    if update_time_ms > 0 and isinstance(latest_db_order_time, datetime):
                        if datetime.fromtimestamp(update_time_ms / 1000.0) <= latest_db_order_time:
                            is_recent = False

                    if db_orders and order_no not in db_orders and order_no not in self.tracker.known_order_nos and is_recent:
                        amount_ars = float(item.get("totalPrice", item.get("fiatAmount", 0)))
                        amount_crypto = float(item.get("amount", 0))
                        asset = item.get("asset", "")
                        raw_price = float(item.get("unitPrice", item.get("price", 0)) or 0.0)
                        price = raw_price if raw_price > 0 else (round(amount_ars / amount_crypto, 2) if amount_crypto > 0 else 0.0)

                        if tt == "BUY":
                            self._balance -= amount_ars
                            event_type = "buy"
                        else:
                            self._balance += amount_ars
                            event_type = "sell"

                        spot = 1.0
                        if spot_prices and asset in spot_prices:
                            spot = spot_prices[asset]
                        elif self.spot_client and hasattr(self.spot_client, "get_prices"):
                            try:
                                s_map = await self.spot_client.get_prices([asset])
                                spot = s_map.get(asset, 1.0)
                            except Exception:
                                spot = 1.0

                        tc = round(price / spot, 2) if spot > 0 else price
                        counterparty = (
                            item.get("sellerNickname" if tt == "BUY" else "buyerNickname")
                            or item.get("buyerNickname" if tt == "BUY" else "sellerNickname")
                            or item.get("counterPartNickName", "") or ""
                        )
                        order = DetectedOrder(
                            order_no=order_no, adv_no=item.get("advNo", ""), asset=asset, trade_type=tt,
                            amount_crypto=amount_crypto, amount_ars=amount_ars, price=price, tc_implicito=tc,
                            payment_method=item.get("payType", item.get("tradeMethodName", "")) or "",
                            counterparty=counterparty, status=str(item.get("orderStatus", "4")), timestamp=datetime.now(),
                        )
                        self.db.save_detected_order(order)
                        self.db.save_liquidity_event(
                            event_type=event_type, balance_after=self._balance, amount_ars=amount_ars,
                            order_no=order_no, asset=asset, amount_crypto=amount_crypto, notes="Conciliación offline al encender",
                        )
                        try:
                            self.db.set_config("balance_ars", str(self._balance))
                        except Exception:
                            pass
                        logger.info("💵 Conciliada orden offline %s (%s $%.2f ARS). Balance: $%.2f ARS", order_no, tt, amount_ars, self._balance)

                    self.tracker.known_order_nos.add(order_no)
            self.tracker.notified_open_orders.update(self.tracker.startup_open_order_nos)
        except Exception as e:
            logger.warning("No se pudieron precargar órdenes históricas de Binance: %s", e)

        try:
            db_swaps = self.db.get_all_detected_swap_ids()
            self.tracker.known_swap_ids.update(db_swaps)
        except Exception as e:
            logger.warning("No se pudieron cargar swaps previos desde BD: %s", e)

        try:
            now_ms = int(time.time() * 1000)
            convert_res = await self.client.get_convert_trades(now_ms - 24 * 3600 * 1000, now_ms, limit=20)
            for item in convert_res.get("list", []):
                order_id = str(item.get("orderId", ""))
                if order_id:
                    self.tracker.known_swap_ids.add(f"convert_{order_id}")
        except Exception as e:
            logger.debug("No se pudieron precargar swaps de Convert: %s", e)

    def set_balance(self, amount: float) -> None:
        """Setea el balance manualmente (desde Telegram)."""
        self._balance = amount
        self.db.save_liquidity_event(
            event_type="manual_adjust", balance_after=self._balance, amount_ars=amount, notes="Ajuste manual via Telegram",
        )
        try:
            self.db.set_config("balance_ars", str(amount))
        except Exception as e:
            logger.warning("No se pudo guardar balance_ars en bot_config: %s", e)
        logger.info("Balance seteado manualmente: $%.2f ARS", self._balance)

    @property
    def balance(self) -> float:
        """Balance nominal configurado en ARS."""
        return self._balance

    @property
    def committed_balance(self) -> float:
        """Monto en ARS comprometido en órdenes de compra abiertas (status 1, 2, 3, 5)."""
        return self.tracker.committed_ars

    @property
    def effective_balance(self) -> float:
        """Saldo real disponible restando órdenes de compra en curso."""
        return max(self._balance - self.committed_balance, 0.0)

    @property
    def available_balance(self) -> float:
        """Balance efectivo con buffer de seguridad aplicado."""
        return max(self.effective_balance * LIQUIDITY_BUFFER, 0.0)

    @property
    def has_liquidity(self) -> bool:
        return self.available_balance > 0

    def get_status_text(self) -> str:
        """Formatea el estado de liquidez para Telegram."""
        committed_txt = f"\n• *Comprometido en órdenes:* ${self.committed_balance:,.2f} ARS" if self.committed_balance > 0 else ""
        return (
            f"💰 *Estado de Balance y Liquidez*\n\n"
            f"• *Balance Nominal:* ${self.balance:,.2f} ARS{committed_txt}\n"
            f"• *Saldo Efectivo:* ${self.effective_balance:,.2f} ARS\n"
            f"• *Disponible (buffer {int(LIQUIDITY_BUFFER * 100)}%):* ${self.available_balance:,.2f} ARS\n"
            f"• *Estado:* {'✅ Con liquidez' if self.has_liquidity else '❌ Sin liquidez'}"
        )

    def consume_incoming_orders(self) -> list[DetectedOrder]:
        """Retorna y vacía la lista de nuevas órdenes entrantes detectadas en curso."""
        return self.tracker.consume_incoming_orders()

    def _on_order_completed(self, trade_type: str, amount_ars: float, asset: str, amount_crypto: float, adv_no: str) -> float:
        """Callback al completar una orden para actualizar balance nominal."""
        if trade_type == "BUY":
            self._balance -= amount_ars
        else:
            self._balance += amount_ars
        try:
            self.db.set_config("balance_ars", str(self._balance))
        except Exception:
            pass
        return self._balance

    async def sync_orders(self, spot_prices: dict[str, float]) -> list[DetectedOrder]:
        """Sincroniza órdenes en curso, apelaciones y completadas."""
        new_orders: list[DetectedOrder] = []
        open_items, open_ok = await self.tracker.sync_open_buy_orders(self.client, spot_prices, self.db)
        await self.tracker.sync_open_sell_orders(self.client, spot_prices, self.db)

        try:
            buy_res = await self.client.list_orders(trade_type="BUY", order_status_list=[4], rows=50)
            completed_buys = await self.tracker.process_completed_orders(
                self.client, "BUY", buy_res, spot_prices, self.db, self._on_order_completed,
            )
            new_orders.extend(completed_buys)
        except Exception as e:
            logger.error("Error leyendo órdenes de compra completadas: %s", e)

        if open_ok:
            prev_committed = self.tracker.committed_ars
            self.tracker.committed_ars = sum(
                float(item.get("totalPrice", item.get("fiatAmount", 0)))
                for item in open_items
                if str(item.get("orderNumber", item.get("orderNo", ""))) not in self.tracker.known_order_nos
            )
            if self.tracker.committed_ars != prev_committed:
                logger.info("🔒 Liquidez comprometida: $%.2f ARS (Saldo efectivo: $%.2f ARS)", self.tracker.committed_ars, self.effective_balance)

        try:
            sell_res = await self.client.list_orders(trade_type="SELL", order_status_list=[4], rows=50)
            completed_sells = await self.tracker.process_completed_orders(
                self.client, "SELL", sell_res, spot_prices, self.db, self._on_order_completed,
            )
            new_orders.extend(completed_sells)
        except Exception as e:
            logger.error("Error leyendo órdenes de venta completadas: %s", e)

        for o in new_orders:
            if o.trade_type == "SELL":
                self.tracker.notified_open_sell_orders.pop(o.order_no, None)

        return new_orders

    async def sync_swaps(self, assets: list[str]) -> list[DetectedSwap]:
        """Detecta conversiones en Convert y Spot."""
        return await self.tracker.sync_swaps(self.client, assets, self.db, self._balance)


# Alias canónico
LiquidityTracker = LiquidityManager
