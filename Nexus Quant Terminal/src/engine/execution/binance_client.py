"""Cliente institucional CCXT para ejecución en Binance USDⓈ-M Futures con margen aislado.
Implementa validación de precisión, rollback de emergencia y protección atómica de Stop-Loss.
Referencia de diseño: docs/ARQUITECTURA.md"""

from typing import Dict, Any, Optional, List
import math
import time
import logging
import ccxt

logger = logging.getLogger("NexusBinanceClient")


class BinanceFuturesClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        testnet: bool = True
    ):
        self.api_key = api_key or ""
        self.api_secret = api_secret or ""
        self.testnet = bool(testnet)
        self.client: Optional[ccxt.binance] = None
        self.connected: bool = False
        self._markets_loaded: bool = False
        self._initialize_exchange()

    def _initialize_exchange(self) -> None:
        """Inicializa la instancia de ccxt con configuración exclusiva de Futuros."""
        if not self.api_key or not self.api_secret:
            self.client = None
            self.connected = False
            return

        try:
            exchange_config = {
                'apiKey': self.api_key,
                'secret': self.api_secret,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future',
                    'adjustForTimeDifference': True,
                    'warnOnFetchOpenOrdersWithoutSymbol': False,
                },
                'timeout': 15000,
            }
            self.client = ccxt.binance(exchange_config)
            if self.testnet:
                self.client.set_sandbox_mode(True)
            self.client.load_markets()
            self._markets_loaded = True

            # Forzar modo unidireccional (One-Way Mode) de forma determinista
            try:
                self.client.set_position_mode(False)
            except Exception:
                pass  # Si ya está en One-Way mode, Binance devuelve código ignorado

            self.connected = True
        except Exception as e:
            logger.error(f"Error al inicializar ccxt Binance Futures: {e}")
            self.client = None
            self.connected = False

    def format_symbol(self, symbol: str) -> str:
        """Formatea cualquier representación a la convención estándar unificada de ccxt."""
        clean = symbol.upper().replace("/", "")
        if clean.endswith(":USDT"):
            return symbol
        if clean.endswith("USDC"):
            base = clean[:-4]
            return f"{base}/USDC:USDC" if ":" not in symbol else symbol
        if clean.endswith("USDT"):
            base = clean[:-4]
            return f"{base}/USDT:USDT" if ":" not in symbol else symbol
        return f"{clean}/USDT:USDT"

    def test_connection(self) -> Dict[str, Any]:
        """Prueba la conectividad con Binance y verifica que las claves sean válidas."""
        if not self.client:
            return {"success": False, "error": "Claves API no configuradas", "testnet": self.testnet}
        try:
            time_res = self.client.fetch_time()
            balance = self.get_futures_balance()
            return {
                "success": True,
                "server_time": time_res,
                "testnet": self.testnet,
                "usdt_balance": balance.get("free_usdt", 0.0),
                "total_balance": balance.get("total_usdt", 0.0),
                "p2p_isolated": True,
            }
        except Exception as e:
            return {"success": False, "error": str(e), "testnet": self.testnet}

    def ping(self) -> Dict[str, Any]:
        """Realiza un ping activo a Binance para medir latencia en tiempo real."""
        if not self.client:
            return {"connected": False, "latency_ms": 0.0, "status": "disconnected"}
        try:
            t0 = time.perf_counter()
            self.client.fetch_time()
            latency = (time.perf_counter() - t0) * 1000.0
            return {"connected": True, "latency_ms": round(latency, 1), "status": "healthy", "timestamp": time.time()}
        except Exception as e:
            return {"connected": False, "latency_ms": 0.0, "status": "error", "error": str(e)}

    def get_futures_balance(self) -> Dict[str, float]:
        """Obtiene el balance exclusivo de la billetera de Futuros USDⓈ-M."""
        if not self.client:
            return {"free_usdt": 0.0, "total_usdt": 0.0}
        try:
            bal = self.client.fetch_balance(params={'type': 'future'})
            free_usdt = float(bal.get('USDT', {}).get('free', 0.0))
            total_usdt = float(bal.get('USDT', {}).get('total', 0.0))
            return {"free_usdt": free_usdt, "total_usdt": total_usdt}
        except Exception as e:
            logger.error(f"Error al consultar balance de futuros: {e}")
            return {"free_usdt": 0.0, "total_usdt": 0.0, "error": str(e)}

    def configure_market_safe(self, symbol: str, leverage: int = 10) -> bool:
        """
        Configura apalancamiento y modo de margen AISLADO de forma estricta.
        SI FALLA EL MODO AISLADO, ABORTA para evitar arriesgar fondos en Margen Cruzado.
        """
        if not self.client:
            return False
        try:
            m_id = self.format_symbol(symbol)
            # 1. Forzar margen aislado
            try:
                self.client.set_margin_mode('ISOLATED', m_id)
            except Exception as margin_err:
                err_str = str(margin_err)
                if "No need to change margin type" not in err_str:
                    logger.critical(f"FATAL: Rechazo al fijar Margen Aislado en {m_id}: {margin_err}")
                    return False  # Abortar inmediatamente

            # 2. Configurar apalancamiento
            self.client.set_leverage(int(leverage), m_id)
            return True
        except Exception as e:
            logger.error(f"Error al configurar mercado seguro {symbol}: {e}")
            return False

    def get_ticker_price(self, symbol: str) -> float:
        """Devuelve el último precio de mercado de un símbolo de forma segura."""
        if not self.client or not self.connected:
            return 0.0
        try:
            m_id = self.format_symbol(symbol)
            ticker = self.client.fetch_ticker(m_id)
            return float((ticker or {}).get('last') or (ticker or {}).get('close') or 0.0)
        except Exception as e:
            logger.error(f"Error consultando ticker en {symbol}: {e}")
            return 0.0

    def place_bracket_order(
        self,
        symbol: str,
        direction: str,  # 'CALL'/'BUY'/'LONG' o 'PUT'/'SELL'/'SHORT'
        budget_usd: float,
        sl_price: float,
        tp_price: float,
        leverage: int = 10,
        post_only: bool = False
    ) -> Dict[str, Any]:
        """
        Ejecuta una orden de entrada con Stop Loss y Take Profit vinculados en Binance Futures.
        Incluye validación de precisión (LOT_SIZE / PRICE_FILTER) y Rollback automático.
        """
        if not self.client or not self.connected:
            return {"success": False, "error": "Cliente Binance no conectado"}

        m_id = self.format_symbol(symbol)

        # 1. Configurar margen aislado de forma estricta (abortar si falla)
        if not self.configure_market_safe(symbol, leverage):
            return {
                "success": False,
                "error": f"Fallo de seguridad al forzar Margen Aislado en {m_id}. Operación cancelada para proteger el capital."
            }

        # 2. Normalización semántica de dirección
        is_long = str(direction).upper() in ['BUY', 'CALL', 'LONG']
        ccxt_side = 'buy' if is_long else 'sell'
        close_side = 'sell' if is_long else 'buy'

        try:
            # 3. Obtener precio actual y calcular cantidad respetando LOT_SIZE
            ticker = self.client.fetch_ticker(m_id)
            curr_price = float((ticker or {}).get('last') or (ticker or {}).get('close') or 0.0)
            if curr_price <= 0:
                return {"success": False, "error": "No se pudo obtener precio actual del mercado"}

            notional = float(budget_usd) * float(leverage)
            raw_qty = notional / curr_price

            # Formateo estricto de cantidad y precios por las reglas de Binance
            qty_str = self.client.amount_to_precision(m_id, raw_qty)
            qty = float(qty_str)

            if not self._markets_loaded:
                self.client.load_markets()
                self._markets_loaded = True
            market = self.client.market(m_id)
            min_qty = float(market.get('limits', {}).get('amount', {}).get('min') or 0.001)
            min_cost = float(market.get('limits', {}).get('cost', {}).get('min') or 5.0)

            if qty < min_qty:
                return {
                    "success": False,
                    "error": f"Cantidad calculada ({qty}) menor al tamaño mínimo permitido en {m_id} ({min_qty}). Aumenta la bala o el apalancamiento."
                }
            if (qty * curr_price) < min_cost:
                return {
                    "success": False,
                    "error": f"Valor nocional (${qty * curr_price:.2f}) inferior al MIN_NOTIONAL de Binance (${min_cost:.2f})."
                }

            sl_str = self.client.price_to_precision(m_id, sl_price)
            tp_str = self.client.price_to_precision(m_id, tp_price)

            # 4. Enviar Orden de Entrada
            entry_order = self.client.create_order(
                symbol=m_id,
                type='market',
                side=ccxt_side,
                amount=qty,
                params={'reduceOnly': False}
            )

            filled_qty = float(entry_order.get('filled') or qty)
            if filled_qty <= 0:
                filled_qty = qty
            filled_qty_str = self.client.amount_to_precision(m_id, filled_qty)

            # 5. Enviar Stop Loss y Take Profit
            try:
                sl_order = self.client.create_order(
                    symbol=m_id,
                    type='STOP_MARKET',
                    side=close_side,
                    amount=float(filled_qty_str),
                    params={
                        'stopPrice': float(sl_str),
                        'reduceOnly': True
                    }
                )

                tp_order = self.client.create_order(
                    symbol=m_id,
                    type='TAKE_PROFIT_MARKET',
                    side=close_side,
                    amount=float(filled_qty_str),
                    params={
                        'stopPrice': float(tp_str),
                        'reduceOnly': True
                    }
                )

                return {
                    "success": True,
                    "entry_order": entry_order,
                    "sl_order": sl_order,
                    "tp_order": tp_order,
                    "symbol": m_id,
                    "side": ccxt_side,
                    "qty": filled_qty,
                    "sl_price": float(sl_str),
                    "tp_price": float(tp_str),
                    "sl_id": sl_order.get('id'),
                    "tp_id": tp_order.get('id')
                }

            except Exception as bracket_err:
                # ROLLBACK DE SEGURIDAD: Si la entrada se llenó pero el SL o TP falló,
                # cerrar inmediatamente la posición para evitar dejarla desprotegida
                logger.critical(f"ALERTA CRÍTICA: Entrada ejecutada pero fallo en SL/TP ({bracket_err}). Ejecutando cierre de emergencia inmediato...")
                try:
                    self.client.cancel_all_orders(m_id)
                    self.client.create_order(
                        symbol=m_id,
                        type='market',
                        side=close_side,
                        amount=float(filled_qty_str),
                        params={'reduceOnly': True}
                    )
                except Exception as rollback_err:
                    logger.critical(f"FALLO FATAL DE ROLLBACK: {rollback_err}")
                return {"success": False, "error": f"Fallo al colocar SL/TP. Posición cerrada por seguridad: {bracket_err}"}

        except Exception as e:
            logger.error(f"Error al ejecutar bracket order en {symbol}: {e}")
            return {"success": False, "error": str(e)}

    def purge_orphan_orders_if_flat(self, symbol: str) -> bool:
        """
        RECIPIENTE OCO Y LIMPIEZA DE ÓRDENES HUÉRFANAS:
        Si la posición neta en el símbolo es 0, cancela cualquier orden residual de SL o TP.
        """
        if not self.client or not self.connected:
            return False
        try:
            m_id = self.format_symbol(symbol)
            positions = self.client.fetch_positions([m_id], params={'type': 'future'})
            amt = 0.0
            for p in positions:
                if not p or not isinstance(p, dict):
                    continue
                if p.get('symbol') == m_id:
                    info = p.get('info') or {}
                    amt = float(info.get('positionAmt') or p.get('contracts') or 0.0)
                    break

            if abs(amt) < 1e-8:
                open_orders = self.client.fetch_open_orders(m_id)
                if len(open_orders) > 0:
                    logger.info(f"Posición plana en {m_id}. Purgando {len(open_orders)} órdenes condicionales huérfanas...")
                    self.client.cancel_all_orders(m_id)
                    return True
            return False
        except Exception as e:
            logger.warning(f"Aviso al purgar órdenes huérfanas en {symbol}: {e}")
            return False

    def cancel_all_orders_for_symbol(self, symbol: str) -> bool:
        """Cancela todas las órdenes abiertas pendientes de un par."""
        if not self.client:
            return False
        try:
            m_id = self.format_symbol(symbol)
            self.client.cancel_all_orders(m_id)
            return True
        except Exception as e:
            logger.error(f"Error al cancelar órdenes en {symbol}: {e}")
            return False

    def close_all_positions(self) -> Dict[str, Any]:
        """
        BOTÓN DE PÁNICO (KILL SWITCH) ROBUSTO:
        Cierra inmediatamente todas las posiciones abiertas a mercado usando positionAmt firmado.
        """
        if not self.client:
            return {"success": False, "error": "Cliente no conectado"}
        try:
            positions = self.client.fetch_positions(params={'type': 'future'})
            closed = []
            for pos in positions:
                if not pos or not isinstance(pos, dict):
                    continue
                info = pos.get('info') or {}
                amt = float(info.get('positionAmt') or 0.0)
                if abs(amt) > 1e-8:
                    symbol = pos.get('symbol')
                    m_id = self.format_symbol(symbol)
                    close_side = 'sell' if amt > 0 else 'buy'
                    abs_qty = abs(amt)
                    qty_str = self.client.amount_to_precision(m_id, abs_qty)

                    # 1. Cancelar órdenes pendientes para liberar margen
                    self.client.cancel_all_orders(m_id)
                    # 2. Cerrar posición a mercado
                    res = self.client.create_order(
                        symbol=m_id,
                        type='market',
                        side=close_side,
                        amount=float(qty_str),
                        params={'reduceOnly': True}
                    )
                    closed.append({"symbol": m_id, "amount": abs_qty, "order_id": res.get('id')})
            return {"success": True, "closed_positions": closed}
        except Exception as e:
            logger.error(f"Error en Kill Switch Seguro: {e}")
            return {"success": False, "error": str(e)}

    def get_position_amt(self, symbol: str) -> float:
        """Devuelve el tamaño neto abierto (positionAmt firmado) para un símbolo en Binance Futuros."""
        if not self.client or not self.connected:
            return 0.0
        try:
            m_id = self.format_symbol(symbol)
            positions = self.client.fetch_positions([m_id], params={'type': 'future'})
            for p in positions:
                if not p or not isinstance(p, dict):
                    continue
                if p.get('symbol') == m_id:
                    info = p.get('info') or {}
                    try:
                        raw_amt = info.get('positionAmt') or p.get('contracts') or 0.0
                        return float(raw_amt)
                    except (ValueError, TypeError):
                        return 0.0
            return 0.0
        except Exception as e:
            logger.error(f"Error consultando positionAmt en {symbol}: {e}")
            return 0.0

    def get_recent_closed_pnl(self, symbol: str) -> float:
        """Obtiene el PnL realizado acumulado del cierre de operación más reciente en Binance Futuros."""
        if not self.client or not self.connected:
            return 0.0
        try:
            m_id = self.format_symbol(symbol)
            trades = self.client.fetch_my_trades(m_id, limit=5)
            if not trades:
                return 0.0
            last_trade = trades[-1]
            if not last_trade or not isinstance(last_trade, dict):
                return 0.0
            info = last_trade.get('info') or {}
            try:
                pnl = float(info.get('realizedPnl') or 0.0)
                return pnl
            except (ValueError, TypeError):
                return 0.0
        except Exception as e:
            logger.error(f"Error consultando PnL realizado para {symbol}: {e}")
            return 0.0

    def move_stop_loss_to_breakeven(self, symbol: str, entry_price: float) -> Dict[str, Any]:
        """
        DESPLAZAMIENTO REAL DE BREAKEVEN EN BINANCE FUTUROS:
        Cancela la orden STOP_MARKET original y coloca una nueva al precio de entrada,
        blindando la posición a CERO RIESGO en los servidores de Binance.
        """
        if not self.client or not self.connected:
            return {"success": False, "error": "Cliente no conectado"}
        try:
            m_id = self.format_symbol(symbol)
            open_orders = self.client.fetch_open_orders(m_id)

            # Buscar orden de Stop Loss activa
            sl_orders = [
                o for o in open_orders
                if isinstance(o, dict) and (
                    o.get('type') in ['STOP_MARKET', 'STOP'] or
                    'STOP' in str((o.get('info') or {}).get('type', ''))
                )
            ]

            if not sl_orders:
                return {"success": False, "error": "No se encontró orden de Stop Loss activa para modificar"}

            old_sl = sl_orders[0]
            old_id = old_sl['id']
            side = old_sl['side']  # 'sell' si era Long, 'buy' si era Short
            amount = float(old_sl.get('amount') or old_sl.get('contracts') or 0.0)

            # Formatear precio de entrada por las reglas de Binance
            entry_str = self.client.price_to_precision(m_id, entry_price)
            qty_str = self.client.amount_to_precision(m_id, amount)

            # 1. Colocar primero el nuevo Stop Loss en Breakeven para nunca dejar la posición desprotegida
            new_sl = self.client.create_order(
                symbol=m_id,
                type='STOP_MARKET',
                side=side,
                amount=float(qty_str),
                params={
                    'stopPrice': float(entry_str),
                    'reduceOnly': True
                }
            )

            # 2. Cancelar el Stop Loss anterior únicamente tras confirmar la nueva orden
            try:
                self.client.cancel_order(old_id, m_id)
            except Exception as cancel_err:
                logger.warning(f"Nuevo SL creado ({new_sl.get('id')}), aviso al cancelar SL previo {old_id}: {cancel_err}")

            logger.info(f"✅ Breakeven activado con éxito en Binance para {m_id}: Stop Loss movido a ${entry_str}")
            return {
                "success": True,
                "old_order_id": old_id,
                "new_order_id": new_sl.get('id'),
                "breakeven_price": float(entry_str)
            }

        except Exception as e:
            logger.error(f"Error desplazando Stop Loss a Breakeven en {symbol}: {e}")
            return {"success": False, "error": str(e)}


