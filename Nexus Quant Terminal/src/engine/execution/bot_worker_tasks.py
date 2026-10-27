"""Tareas de ejecución en segundo plano para el sistema Dual-Bot (Bot 1 Radar y Bot 2 Macro).
Contiene el escaneo multi-activo, reconciliación de posiciones en Binance y Breakeven dinámico.
Referencia de diseño: docs/ARQUITECTURA.md"""

import logging
from typing import List
import numpy as np
import pandas as pd

from engine.execution.signal_dispatcher import (
    MutexState,
    PriorityRankingEngine,
    SignalCandidate,
)
from strategies import STRATEGIES

logger = logging.getLogger("NexusDualBotManager")


def scan_bot1_radar_and_dispatch(manager) -> None:
    """Escanea la matriz (estrategias x pares) en Bot 1 respetando el Mutex de Racha."""
    if not manager.streak_mutex.can_dispatch():
        reconcile_active_bot1_trade(manager)
        return

    if not manager.client or not manager.client.client:
        return

    strategies = manager.bot1.get("strategies", [manager.bot1.get("strategy", "daily_confluence")])
    symbols = manager.bot1.get("symbols", [manager.bot1.get("symbol", "BTC/USDT")])
    raw_candidates: List[SignalCandidate] = []

    bot2_sym = manager.bot2.get("symbol", "")
    blocked_symbols = (
        [bot2_sym] if manager.bot2["state"] == "RUNNING" and manager.bot2.get("open_positions") else []
    )

    for sym in symbols:
        try:
            m_id = manager.client.format_symbol(sym)
            ohlcv = manager.client.client.fetch_ohlcv(m_id, timeframe="1h", limit=120)
            if not ohlcv or len(ohlcv) < 50:
                continue

            closed_candle = ohlcv[-2]
            closed_candle_ts = int(closed_candle[0])

            df = pd.DataFrame(
                ohlcv[:-1], columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")

            highs, lows, closes = df["high"].values, df["low"].values, df["close"].values
            tr = np.maximum(
                highs[1:] - lows[1:],
                np.maximum(abs(highs[1:] - closes[:-1]), abs(lows[1:] - closes[:-1])),
            )
            atr = float(np.mean(tr[-14:])) if len(tr) >= 14 else float(highs[-1] - lows[-1])
            close_price = float(closes[-1])

            for strat_key in strategies:
                cache_key = f"bot1_{strat_key}_{sym}"
                if manager.last_processed_candle_ts.get(cache_key) == closed_candle_ts:
                    continue

                strat_cls = STRATEGIES.get(strat_key)
                if not strat_cls:
                    continue

                strat_inst = strat_cls()
                signals = strat_inst.generate_signals(df)
                if signals is None or len(signals) == 0:
                    continue

                last_sig = signals.iloc[-1]
                manager.last_processed_candle_ts[cache_key] = closed_candle_ts

                if last_sig in ["CALL", "PUT", "BUY", "SELL", 1, -1]:
                    is_long = last_sig in ["CALL", "BUY", 1]
                    dir_str = "BUY" if is_long else "SELL"
                    sl = close_price - (atr * 1.2) if is_long else close_price + (atr * 1.2)
                    tp = close_price + (atr * 2.5) if is_long else close_price - (atr * 2.5)

                    raw_candidates.append(
                        SignalCandidate(
                            symbol=sym,
                            strategy_id=strat_key,
                            direction=dir_str,
                            candle_ts=closed_candle_ts,
                            close_price=close_price,
                            atr=atr,
                            sl_price=sl,
                            tp_price=tp,
                        )
                    )
        except Exception as e:
            logger.error(f"Error escaneando {sym} en radar de Bot 1: {e}")

    if not raw_candidates:
        return

    ranked = PriorityRankingEngine.rank_candidates(raw_candidates, blocked_symbols)
    if not ranked:
        return

    best = ranked[0]
    current_bullet = manager.bot1["current_bullet_usd"]
    step = manager.bot1["current_step"]

    if not manager.streak_mutex.acquire_lock(best, current_bullet):
        return

    clean_sym = best.symbol.upper().replace("/", "")
    if "BTC" in clean_sym:
        lev = 16
    elif "ETH" in clean_sym:
        lev = 6
    else:
        lev = 5

    manager._add_event(
        "BOT_1_RADAR",
        f"🎯 [Paso {step+1}/{manager.bot1['streak_target']}] Seleccionado: {best.symbol} ({best.direction}) "
        f"vía {best.strategy_id} (Score: {best.priority_score}, Confluencias: {best.confluence_count}). "
        f"Disparando bala de ${current_bullet:.2f} USD a {lev}x...",
    )

    res = manager.client.place_bracket_order(
        symbol=best.symbol,
        direction=best.direction,
        budget_usd=current_bullet,
        sl_price=best.sl_price,
        tp_price=best.tp_price,
        leverage=lev,
    )

    with manager._lock:
        if res.get("success"):
            manager.bot1["active_trade"] = {
                "symbol": best.symbol,
                "direction": best.direction,
                "strategy": best.strategy_id,
                "bullet_usd": current_bullet,
                "step": step,
                "entry_price": best.close_price,
                "atr": best.atr,
                "breakeven_triggered": False,
                "order_details": res,
            }
            manager.bot1["mutex_state"] = "LOCKED_IN_TRADE"
            manager._add_event(
                "BOT_1",
                f"✅ Orden en vivo colocada en Binance ({best.symbol}). SL: ${best.sl_price:.2f} | TP: ${best.tp_price:.2f}",
            )
        else:
            manager.streak_mutex.release_lock("ORDER_FAILED")
            manager.bot1["mutex_state"] = "IDLE_WAITING"
            manager._add_event("ERROR", f"Fallo al ejecutar orden en Binance: {res.get('error')}")


def reconcile_active_bot1_trade(manager) -> None:
    """Verifica el estado de la posición activa de Bot 1 y gestiona el desplazamiento a Breakeven."""
    active = manager.bot1.get("active_trade")
    if not active or not manager.client:
        return

    sym = active["symbol"]
    pos_amt = manager.client.get_position_amt(sym)

    if abs(pos_amt) < 1e-8:
        manager.client.purge_orphan_orders_if_flat(sym)
        pnl_realized = manager.client.get_recent_closed_pnl(sym)
        is_win = pnl_realized > 0

        manager._add_event(
            "BOT_1", f"Trade finalizado en {sym}. PnL Realizado: ${pnl_realized:+.2f} USD."
        )
        manager.record_simulated_trade(
            bot_id="bot_1", is_win=is_win, pnl_usd=pnl_realized, symbol=sym
        )
        with manager._lock:
            manager.bot1["active_trade"] = None
            manager.streak_mutex.release_lock("TRADE_SETTLED")
            manager.bot1["mutex_state"] = "IDLE_WAITING"
    else:
        if not active.get("breakeven_triggered") and manager.client and manager.client.client:
            try:
                m_id = manager.client.format_symbol(sym)
                ticker = manager.client.client.fetch_ticker(m_id)
                curr_p = float(ticker.get("last") or ticker.get("close") or 0.0)
                entry_p = float(active.get("entry_price") or 0.0)
                atr = float(active.get("atr") or 0.0)
                is_long = active.get("direction") == "BUY"

                if curr_p > 0 and entry_p > 0 and atr > 0:
                    should_be = (curr_p >= entry_p + atr) if is_long else (curr_p <= entry_p - atr)
                    if should_be:
                        be_res = manager.client.move_stop_loss_to_breakeven(sym, entry_p)
                        if be_res.get("success"):
                            with manager._lock:
                                active["breakeven_triggered"] = True
                            manager._add_event(
                                "BOT_1_BREAKEVEN",
                                f"🛡️ BREAKEVEN ACTIVADO EN BINANCE REAL ({sym}): Precio tocó +1.0x ATR (${curr_p:.2f}). "
                                f"Stop Loss desplazado a ${entry_p:.2f} en el exchange. ¡Operación a 0.00% de riesgo!",
                            )
            except Exception as be_err:
                logger.warning(f"Aviso al evaluar Breakeven dinámico para {sym}: {be_err}")


def process_live_bot2_signals(manager) -> None:
    """Descarga velas cerradas y evalúa la estrategia macro de Bot 2 con protección de Drawdown."""
    target_bot = manager.bot2
    symbol = target_bot.get("symbol", "BTC/USDT")
    strat_key = target_bot.get("strategy", "volatility_squeeze_ml")

    if not manager.client or not manager.client.client:
        return

    try:
        m_id = manager.client.format_symbol(symbol)
        ohlcv = manager.client.client.fetch_ohlcv(m_id, timeframe="1h", limit=120)
        if not ohlcv or len(ohlcv) < 50:
            return

        closed_candle = ohlcv[-2]
        closed_candle_ts = int(closed_candle[0])

        key = f"bot_2_{symbol}"
        if manager.last_processed_candle_ts.get(key) == closed_candle_ts:
            return

        df = pd.DataFrame(
            ohlcv[:-1], columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")

        strat_class = STRATEGIES.get(strat_key)
        if not strat_class:
            return

        strat_instance = strat_class()
        signals = strat_instance.generate_signals(df)
        if signals is None or len(signals) == 0:
            return

        last_sig = signals.iloc[-1]
        manager.last_processed_candle_ts[key] = closed_candle_ts

        if last_sig in ["CALL", "PUT", "BUY", "SELL", 1, -1]:
            highs, lows, closes = df["high"].values, df["low"].values, df["close"].values
            tr = np.maximum(
                highs[1:] - lows[1:],
                np.maximum(abs(highs[1:] - closes[:-1]), abs(lows[1:] - closes[:-1])),
            )
            atr = float(np.mean(tr[-14:])) if len(tr) >= 14 else float(highs[-1] - lows[-1])
            close_price = float(closes[-1])

            is_long = last_sig in ["CALL", "BUY", 1]
            direction = "BUY" if is_long else "SELL"
            sl_price = close_price - (atr * 1.2) if is_long else close_price + (atr * 1.2)
            tp_price = close_price + (atr * 2.5) if is_long else close_price - (atr * 2.5)

            bullet = target_bot["allocated_capital_usd"] * (target_bot["risk_per_trade_pct"] / 100.0)
            lev = 5

            manager._add_event(
                "BOT_2",
                f"🎯 Señal Macro {direction} detectada por {strat_key} en {symbol}. Ejecutando orden bracket (${bullet:.2f} USD)...",
            )
            res = manager.client.place_bracket_order(
                symbol=symbol,
                direction=direction,
                budget_usd=bullet,
                sl_price=sl_price,
                tp_price=tp_price,
                leverage=lev,
            )

            if res.get("success"):
                manager._add_event(
                    "BOT_2",
                    f"✅ Orden Macro ejecutada en Binance. SL: ${sl_price:.2f} | TP: ${tp_price:.2f}",
                )
            else:
                manager._add_event(
                    "ERROR", f"Fallo al ejecutar orden Macro en Binance: {res.get('error')}"
                )
    except Exception as e:
        logger.error(f"Error procesando señales de Bot 2: {e}")


def reconcile_startup_positions(manager) -> None:
    """Reconcilia posiciones abiertas en Binance tras un reinicio para evitar órdenes duplicadas."""
    if not manager.client or not manager.client.client:
        return
    try:
        positions = manager.client.client.fetch_positions(params={"type": "future"})
        for p in positions:
            amt = float(p.get("info", {}).get("positionAmt") or p.get("contracts") or 0.0)
            if abs(amt) > 1e-8:
                sym = p.get("symbol", "").replace(":USDT", "")
                entry_p = float(
                    p.get("entryPrice") or p.get("info", {}).get("entryPrice") or 0.0
                )
                is_long = amt > 0
                direction = "BUY" if is_long else "SELL"

                with manager._lock:
                    manager.bot1["active_trade"] = {
                        "symbol": sym,
                        "direction": direction,
                        "strategy": "reconciled_position",
                        "bullet_usd": manager.bot1["current_bullet_usd"],
                        "step": manager.bot1["current_step"],
                        "entry_price": entry_p,
                        "atr": entry_p * 0.01,
                        "breakeven_triggered": False,
                    }
                    manager.streak_mutex.state = MutexState.LOCKED_IN_TRADE
                    manager.bot1["mutex_state"] = "LOCKED_IN_TRADE"
                manager._add_event(
                    "SISTEMA_RECOVERY",
                    f"⚠️ POSICIÓN PREVIA RECUPERADA EN BINANCE: {direction} en {sym} ({abs(amt):.4f} contratos a ${entry_p:.2f}). "
                    f"Mutex bloqueado automáticamente para evitar abrir órdenes duplicadas.",
                )
                break
    except Exception as e:
        logger.warning(f"Aviso al reconciliar posiciones de inicio: {e}")
