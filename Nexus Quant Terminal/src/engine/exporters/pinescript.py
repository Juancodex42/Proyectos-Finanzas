"""
pinescript.py - Institutional-Grade Pine Script v6 Strategy & Bot Exporter
Covers all 13 Quantitative Trading Strategies with Zero-Discrepancy Parity.
Supports Dual-Mode Export:
- 'strategy': Executable Bot with TradingView Strategy Tester metrics (Win Rate, Profit Factor, Sharpe, Drawdown, Trades list).
- 'indicator': Visual signals with clean overlays and alertcondition Webhooks.
Includes Commented Capital & Risk Management section in Spanish for every archetype.
"""

from typing import Dict, Any, Optional


def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_int(val: Any, default: int = 0) -> int:
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def _build_risk_mgmt_header(
    strat_title: str,
    export_mode: str,
    initial_capital: float,
    pos_size_usd: float,
    max_open_trades: int,
    bars_to_hold: int,
    commission_pct: float
) -> str:
    """Genera la cabecera v6 y la sección de gestión de riesgo comentada en español."""
    is_strategy = (str(export_mode).lower() == "strategy")
    init_cap = _safe_float(initial_capital, 1000.0)
    pos_size = _safe_float(pos_size_usd, 50.0)
    max_trades = max(1, _safe_int(max_open_trades, 1))
    hold_bars = max(1, _safe_int(bars_to_hold, 1))
    comm_pct = _safe_float(commission_pct, 0.05)

    if is_strategy:
        header = f'''//@version=6
strategy("{strat_title} (Bot Ejecutable)", 
         overlay=true, 
         initial_capital={init_cap:.1f}, 
         default_qty_type=strategy.cash, 
         default_qty_value={pos_size:.1f}, 
         commission_type=strategy.commission.percent, 
         commission_value={comm_pct:.3f},
         pyramiding={max_trades})'''
    else:
        header = f'''//@version=6
indicator("{strat_title} (Indicador de Señales)", overlay=true)'''

    risk_section = f'''
// ============================================================================
// 1. CONFIGURACIÓN DE GESTIÓN DE CAPITAL Y RIESGO (MODIFICA AQUÍ TUS PARÁMETROS)
// ============================================================================
// [TAMAÑO DE LA POSICIÓN]
// Modifica este valor si deseas arriesgar más o menos dinero en cada operación
pos_size_usd    = input.float({pos_size:.1f}, "Tamaño de Posición por Trade ($ USD)", tooltip="Monto en dinero que arriesgas en cada entrada")

// [LÍMITE DE OPERACIONES SIMULTÁNEAS]
// 1 = Solo 1 operación abierta a la vez (espera a que cierre antes de abrir otra).
// > 1 = Permite abrir nuevas operaciones si aparecen señales en velas siguientes.
max_open_trades = input.int({max_trades}, "Máximo de Operaciones Simultáneas", minval=1)

// [EXPIRACIÓN DE LA OPERACIÓN EN VELAS]
// Define cuántas velas permanece abierta la posición antes de cerrarse automáticamente
bars_to_hold    = input.int({hold_bars}, "Expiración en Velas (Time Stop)", minval=1, tooltip="Cantidad de velas que se mantiene abierta la posición")

// [TRADING CLÁSICO ASIMÉTRICO - TRIPLE BARRERA (STOP LOSS Y TAKE PROFIT POR ATR)]
use_tp_sl       = input.bool(true, "Activar Stop Loss y Take Profit por ATR")
sl_atr_mult     = input.float(1.2, "Multiplicador Stop Loss (x ATR)", minval=0.1, step=0.1)
tp_atr_mult     = input.float(2.4, "Multiplicador Take Profit (x ATR)", minval=0.1, step=0.1)
use_breakeven   = input.bool(true, "Mover SL a Entrada (Breakeven al tocar 1R)")

// [SISTEMA DE RACHA CONVEXA (OPCIÓN A: 3 TRADES vs OPCIÓN B: 4 TRADES)]
use_compounding_streak = input.bool(true, "Activar Escalera de Racha Compuesta")
streak_target_steps    = input.int(3, "Objetivo de Racha: 3 (Opción A) o 4 (Opción B)", minval=2, maxval=6)

// [COMISIÓN ESTIMADA DEL BROKER]
broker_fee_pct  = input.float({comm_pct:.2f}, "Comisión Estimada por Trade %") / 100.0
'''
    return header + "\n" + risk_section


def _build_execution_footer(strat_key: str, export_mode: str) -> str:
    """Genera el motor de ejecución de órdenes de TradingView v6 y las alertas."""
    is_strategy = (str(export_mode).lower() == "strategy")

    code = f'''
// ============================================================================
// 4. ALERTAS NATIVAS Y WEBHOOKS DE AUTOMATIZACIÓN
// ============================================================================
alertcondition(call_signal, title="{strat_key.upper()} CALL Signal", message='{{"action": "BUY_CALL", "strategy": "{strat_key}", "ticker": "' + syminfo.ticker + '", "close": ' + str.tostring(close) + '}}')
alertcondition(put_signal, title="{strat_key.upper()} PUT Signal", message='{{"action": "SELL_PUT", "strategy": "{strat_key}", "ticker": "' + syminfo.ticker + '", "close": ' + str.tostring(close) + '}}')
'''

    if is_strategy:
        code += f'''
// ============================================================================
// 5. MOTOR DE EJECUCIÓN CLÁSICA ASIMÉTRICA CON ESCALERA DE RACHAS (OPCIÓN A / B)
// ============================================================================
atr_dist = ta.atr(14)
var float long_sl = na
var float long_tp = na
var float short_sl = na
var float short_tp = na
var int current_streak_step = 0
var float active_trade_size = pos_size_usd

// Actualización de la racha al cerrar operaciones
if strategy.closedtrades > 0 and ta.change(strategy.closedtrades)
    if strategy.closedtrades.profit(strategy.closedtrades - 1) > 0
        current_streak_step := current_streak_step + 1
        if use_compounding_streak
            if current_streak_step >= streak_target_steps
                current_streak_step := 0
                active_trade_size := pos_size_usd
            else
                active_trade_size := active_trade_size * (1.0 + tp_atr_mult / sl_atr_mult)
    else
        current_streak_step := 0
        active_trade_size := pos_size_usd

if call_signal and strategy.opentrades < max_open_trades
    long_sl := close - (atr_dist * sl_atr_mult)
    long_tp := close + (atr_dist * tp_atr_mult)
    strategy.entry("BUY_CALL", strategy.long, qty=active_trade_size / close,
                   alert_message='{{"action": "BUY_CALL", "strategy": "{strat_key}", "ticker": "' + syminfo.ticker + '", "amount": ' + str.tostring(active_trade_size) + '}}')

if put_signal and strategy.opentrades < max_open_trades
    short_sl := close + (atr_dist * sl_atr_mult)
    short_tp := close - (atr_dist * tp_atr_mult)
    strategy.entry("SELL_PUT", strategy.short, qty=active_trade_size / close,
                   alert_message='{{"action": "SELL_PUT", "strategy": "{strat_key}", "ticker": "' + syminfo.ticker + '", "amount": ' + str.tostring(active_trade_size) + '}}')

// Gestión dinámica de salidas con Triple Barrera
if strategy.position_size > 0
    if use_breakeven and close >= (strategy.position_avg_price + atr_dist)
        long_sl := math.max(long_sl, strategy.position_avg_price)
    if use_tp_sl
        strategy.exit("Exit LONG", from_entry="BUY_CALL", stop=long_sl, limit=long_tp)

if strategy.position_size < 0
    if use_breakeven and close <= (strategy.position_avg_price - atr_dist)
        short_sl := math.min(short_sl, strategy.position_avg_price)
    if use_tp_sl
        strategy.exit("Exit SHORT", from_entry="SELL_PUT", stop=short_sl, limit=short_tp)

// Cierre por Time Stop (Expiración en velas) si no ha tocado SL ni TP
if strategy.opentrades > 0 and ta.barssince(strategy.opentrades.entry_time(0)) >= bars_to_hold
    strategy.close_all(comment="Time Stop")
'''
    return code




def export_to_pinescript(
    strategy_key: str,
    params: Dict[str, Any] = None,
    metadata: Dict[str, Any] = None,
    export_mode: str = "strategy",
    initial_capital: float = 1000.0,
    pos_size_usd: float = 50.0,
    max_open_trades: int = 1,
    bars_to_hold: int = 1,
    commission_pct: float = 0.05
) -> str:
    """
    Genera código Pine Script v6 completo, ejecutable e independiente para TradingView.
    Abarca con fidelidad matemática exacta las 13 estrategias del sistema.
    """
    params = params or {}
    metadata = metadata or {}
    strat_key = strategy_key.lower().replace("-", "_").replace(" ", "_")

    # Extraer parámetros de gestión si vienen en metadata o params
    if "initial_capital" in params:
        initial_capital = _safe_float(params["initial_capital"], initial_capital)
    if "pos_size_usd" in params:
        pos_size_usd = _safe_float(params["pos_size_usd"], pos_size_usd)
    if "max_open_trades" in params:
        max_open_trades = _safe_int(params["max_open_trades"], max_open_trades)
    if "bars_to_hold" in params:
        bars_to_hold = _safe_int(params["bars_to_hold"], bars_to_hold)
    elif "expiry_candles" in params:
        bars_to_hold = _safe_int(params["expiry_candles"], bars_to_hold)
    if "commission_pct" in params:
        commission_pct = _safe_float(params["commission_pct"], commission_pct)
    if "export_mode" in params:
        export_mode = str(params["export_mode"])

    # 1. MEAN REVERSION (SMA + ATR PERCENTILE FILTER)
    if strat_key in ["mean_reversion", "mean_reversion_atr_percentil"]:
        sma_p = _safe_int(params.get("sma_period", 20), 20)
        threshold = _safe_float(params.get("threshold", 0.015), 0.015)
        atr_p = _safe_int(params.get("atr_period", 14), 14)
        atr_pct = _safe_float(params.get("atr_threshold_percentile", 50.0), 50.0)

        header = _build_risk_mgmt_header(
            "Nexus Quant - Mean Reversion ATR", export_mode, initial_capital, pos_size_usd, max_open_trades, bars_to_hold, commission_pct
        )
        body = f'''
// ============================================================================
// 2. PARÁMETROS TÉCNICOS DE LA ESTRATEGIA (OPTIMIZADOS EN BACKTEST)
// ============================================================================
sma_period    = input.int({sma_p}, "Periodo Media Móvil (SMA)", minval=2, maxval=200)
threshold_pct = input.float({threshold * 100:.3f}, "Umbral de Desviación %", step=0.1) / 100.0
atr_period    = input.int({atr_p}, "Periodo ATR Volatilidad", minval=2, maxval=100)
atr_pct_max   = input.float({atr_pct:.1f}, "Percentil Máximo ATR (%)", minval=10.0, maxval=100.0)

// ============================================================================
// 3. CÁLCULO DE INDICADORES Y CONDICIONES DE ENTRADA
// ============================================================================
sma_val = ta.sma(close, sma_period)
atr_val = ta.atr(atr_period)

upper_thresh = sma_val * (1.0 + threshold_pct)
lower_thresh = sma_val * (1.0 - threshold_pct)

atr_rank = ta.percentrank(atr_val, 100)
atr_filter = atr_rank <= atr_pct_max

bool raw_call = (close <= lower_thresh) and atr_filter
bool raw_put  = (close >= upper_thresh) and atr_filter

bool call_signal = raw_call and not raw_call[1]
bool put_signal  = raw_put  and not raw_put[1]

plot(sma_val, title="SMA Base", color=color.new(#38bdf8, 0), linewidth=2)
p_up = plot(upper_thresh, title="Banda Superior PUT", color=color.new(#f43f5e, 20), linewidth=1)
p_lo = plot(lower_thresh, title="Banda Inferior CALL", color=color.new(#10b981, 20), linewidth=1)
fill(p_up, p_lo, color=color.new(#38bdf8, 92), title="Canal Reversión")

plotshape(call_signal, title="Señal CALL", style=shape.triangleup, location=location.belowbar, color=#10b981, size=size.small, text="CALL")
plotshape(put_signal, title="Señal PUT", style=shape.triangledown, location=location.abovebar, color=#f43f5e, size=size.small, text="PUT")
'''
        footer = _build_execution_footer("mean_reversion", export_mode)
        return header + body + footer

    # 2. RSI EXTREMES (RSI OVERBOUGHT/OVERSOLD + WICK ABSORPTION + VOLUME CLIMAX)
    if strat_key in ["rsi_extremes", "rsi_extremos_volumen"]:
        rsi_p = _safe_int(params.get("rsi_period", 14), 14)
        oversold = _safe_float(params.get("oversold", 25.0), 25.0)
        overbought = _safe_float(params.get("overbought", 75.0), 75.0)
        wick_r = _safe_float(params.get("wick_ratio", 0.35), 0.35)
        vol_m = _safe_float(params.get("vol_mult", 1.3), 1.3)

        header = _build_risk_mgmt_header(
            "Nexus Quant - RSI Extremes + Mecha", export_mode, initial_capital, pos_size_usd, max_open_trades, bars_to_hold, commission_pct
        )
        body = f'''
// ============================================================================
// 2. PARÁMETROS TÉCNICOS DE LA ESTRATEGIA (OPTIMIZADOS EN BACKTEST)
// ============================================================================
rsi_period     = input.int({rsi_p}, "Periodo RSI", minval=2, maxval=50)
rsi_oversold   = input.float({oversold:.1f}, "Nivel Sobreventa (CALL)", minval=5.0, maxval=45.0)
rsi_overbought = input.float({overbought:.1f}, "Nivel Sobrecompra (PUT)", minval=55.0, maxval=95.0)
wick_ratio     = input.float({wick_r:.2f}, "Ratio Mínimo Mecha Rechazo", minval=0.0, maxval=0.8, step=0.05)
vol_mult       = input.float({vol_m:.2f}, "Multiplicador de Volumen Clímax", minval=0.0, maxval=5.0, step=0.1)

// ============================================================================
// 3. CÁLCULO DE INDICADORES Y CONDICIONES DE ENTRADA
// ============================================================================
rsi_val = ta.rsi(close, rsi_period)
vol_sma = ta.sma(volume, 20)
vol_filter = vol_mult <= 0.0 or na(volume) or vol_sma == 0 or (volume >= vol_sma * vol_mult)

candle_range = high - low
lower_wick = math.min(open, close) - low
upper_wick = high - math.max(open, close)

lower_wick_ratio = candle_range > 0 ? (lower_wick / candle_range) : 0.0
upper_wick_ratio = candle_range > 0 ? (upper_wick / candle_range) : 0.0

wick_call = wick_ratio <= 0.0 or (lower_wick_ratio >= wick_ratio)
wick_put  = wick_ratio <= 0.0 or (upper_wick_ratio >= wick_ratio)

bool raw_call = (rsi_val < rsi_oversold) and wick_call and vol_filter
bool raw_put  = (rsi_val > rsi_overbought) and wick_put and vol_filter

bool call_signal = raw_call and not raw_call[1]
bool put_signal  = raw_put  and not raw_put[1]

plotshape(call_signal, title="RSI Extremes CALL", style=shape.triangleup, location=location.belowbar, color=#10b981, size=size.small, text="CALL")
plotshape(put_signal, title="RSI Extremes PUT", style=shape.triangledown, location=location.abovebar, color=#f43f5e, size=size.small, text="PUT")
'''
        footer = _build_execution_footer("rsi_extremes", export_mode)
        return header + body + footer

    # 3. BOLLINGER BOUNCE (PIERCING AND RE-ENTRY TO BANDS)
    if strat_key in ["bollinger_bounce", "bollinger_rebote"]:
        bb_p = _safe_int(params.get("bb_period", 20), 20)
        bb_std = _safe_float(params.get("bb_std", 2.2), 2.2)
        wick_r = _safe_float(params.get("wick_ratio", 0.35), 0.35)
        vol_m = _safe_float(params.get("vol_mult", 1.3), 1.3)

        header = _build_risk_mgmt_header(
            "Nexus Quant - Bollinger Bounce Re-Entry", export_mode, initial_capital, pos_size_usd, max_open_trades, bars_to_hold, commission_pct
        )
        body = f'''
// ============================================================================
// 2. PARÁMETROS TÉCNICOS DE LA ESTRATEGIA (OPTIMIZADOS EN BACKTEST)
// ============================================================================
bb_period   = input.int({bb_p}, "Periodo Bandas Bollinger", minval=5, maxval=100)
bb_std      = input.float({bb_std:.2f}, "Desviación Estándar BB", minval=1.0, maxval=4.0, step=0.1)
wick_ratio  = input.float({wick_r:.2f}, "Ratio Mínimo Mecha Rechazo", minval=0.0, maxval=0.8, step=0.05)
vol_mult    = input.float({vol_m:.2f}, "Multiplicador Volumen", minval=0.0, maxval=5.0, step=0.1)

// ============================================================================
// 3. CÁLCULO DE INDICADORES Y CONDICIONES DE ENTRADA
// ============================================================================
[bb_mid, bb_upper, bb_lower] = ta.bb(close, bb_period, bb_std)
vol_sma = ta.sma(volume, 20)
vol_filter = vol_mult <= 0.0 or na(volume) or vol_sma == 0 or (volume >= vol_sma * vol_mult)

candle_range = high - low
lower_wick = math.min(open, close) - low
upper_wick = high - math.max(open, close)

lower_wick_ratio = candle_range > 0 ? (lower_wick / candle_range) : 0.0
upper_wick_ratio = candle_range > 0 ? (upper_wick / candle_range) : 0.0

wick_call = wick_ratio <= 0.0 or (lower_wick_ratio >= wick_ratio)
wick_put  = wick_ratio <= 0.0 or (upper_wick_ratio >= wick_ratio)

bool call_signal = (close[1] <= bb_lower[1]) and (close > bb_lower) and wick_call and vol_filter
bool put_signal  = (close[1] >= bb_upper[1]) and (close < bb_upper) and wick_put and vol_filter

plot(bb_upper, title="BB Superior", color=color.new(#f43f5e, 20))
plot(bb_mid, title="BB Media", color=color.new(#94a3b8, 40))
plot(bb_lower, title="BB Inferior", color=color.new(#10b981, 20))

plotshape(call_signal, title="BB Bounce CALL", style=shape.triangleup, location=location.belowbar, color=#10b981, size=size.small, text="CALL")
plotshape(put_signal, title="BB Bounce PUT", style=shape.triangledown, location=location.abovebar, color=#f43f5e, size=size.small, text="PUT")
'''
        footer = _build_execution_footer("bollinger_bounce", export_mode)
        return header + body + footer

    # 4. EMA CROSS (MOMENTUM CROSSOVER)
    if strat_key in ["ema_cross", "cruce_emas"]:
        fast_p = _safe_int(params.get("fast_period", 9), 9)
        slow_p = _safe_int(params.get("slow_period", 21), 21)

        header = _build_risk_mgmt_header(
            "Nexus Quant - EMA Cross Momentum", export_mode, initial_capital, pos_size_usd, max_open_trades, bars_to_hold, commission_pct
        )
        body = f'''
// ============================================================================
// 2. PARÁMETROS TÉCNICOS DE LA ESTRATEGIA (OPTIMIZADOS EN BACKTEST)
// ============================================================================
fast_period = input.int({fast_p}, "Periodo EMA Rápida", minval=2, maxval=50)
slow_period = input.int({slow_p}, "Periodo EMA Lenta", minval=5, maxval=200)

// ============================================================================
// 3. CÁLCULO DE INDICADORES Y CONDICIONES DE ENTRADA
// ============================================================================
ema_fast = ta.ema(close, fast_period)
ema_slow = ta.ema(close, slow_period)

bool call_signal = ta.crossover(ema_fast, ema_slow)
bool put_signal  = ta.crossunder(ema_fast, ema_slow)

plot(ema_fast, title="EMA Rápida", color=color.new(#10b981, 0), linewidth=2)
plot(ema_slow, title="EMA Lenta", color=color.new(#f43f5e, 0), linewidth=2)

plotshape(call_signal, title="EMA Cross CALL", style=shape.triangleup, location=location.belowbar, color=#10b981, size=size.small, text="CALL")
plotshape(put_signal, title="EMA Cross PUT", style=shape.triangledown, location=location.abovebar, color=#f43f5e, size=size.small, text="PUT")
'''
        footer = _build_execution_footer("ema_cross", export_mode)
        return header + body + footer

    # 5. VOLATILITY SQUEEZE (CARTER SQUEEZE: BOLLINGER INSIDE KELTNER)
    if strat_key in ["volatility_squeeze", "carter_squeeze"]:
        bb_p = _safe_int(params.get("bb_period", 20), 20)
        bb_mult = _safe_float(params.get("bb_mult", 1.5), 1.5)
        kc_p = _safe_int(params.get("kc_period", 20), 20)
        kc_mult = _safe_float(params.get("kc_mult", 2.0), 2.0)

        header = _build_risk_mgmt_header(
            "Nexus Quant - Volatility Squeeze Carter", export_mode, initial_capital, pos_size_usd, max_open_trades, bars_to_hold, commission_pct
        )
        body = f'''
// ============================================================================
// 2. PARÁMETROS TÉCNICOS DE LA ESTRATEGIA (OPTIMIZADOS EN BACKTEST)
// ============================================================================
bb_period = input.int({bb_p}, "Periodo Bollinger", minval=5, maxval=100)
bb_mult   = input.float({bb_mult:.2f}, "Multiplicador Bollinger", minval=0.5, maxval=3.0, step=0.1)
kc_period = input.int({kc_p}, "Periodo Keltner Channel", minval=5, maxval=100)
kc_mult   = input.float({kc_mult:.2f}, "Multiplicador Keltner ATR", minval=0.5, maxval=3.0, step=0.1)

// ============================================================================
// 3. CÁLCULO DE INDICADORES Y CONDICIONES DE ENTRADA
// ============================================================================
[bb_mid, bb_upper, bb_lower] = ta.bb(close, bb_period, bb_mult)
kc_mid = ta.ema(close, kc_period)
kc_atr = ta.atr(kc_period)
kc_upper = kc_mid + (kc_mult * kc_atr)
kc_lower = kc_mid - (kc_mult * kc_atr)
momentum = close - bb_mid

squeeze_on = (bb_lower > kc_lower) and (bb_upper < kc_upper)
squeeze_fired = squeeze_on[1] and not squeeze_on

bool call_signal = squeeze_fired and (momentum > 0)
bool put_signal  = squeeze_fired and (momentum < 0)

plotshape(call_signal, title="Squeeze CALL", style=shape.triangleup, location=location.belowbar, color=#10b981, size=size.small, text="CALL")
plotshape(put_signal, title="Squeeze PUT", style=shape.triangledown, location=location.abovebar, color=#f43f5e, size=size.small, text="PUT")
'''
        footer = _build_execution_footer("volatility_squeeze", export_mode)
        return header + body + footer

    # 6. SUPPORT & RESISTANCE (DYNAMIC ROLLING ZONES)
    if strat_key in ["support_resistance", "soporte_resistencia_dinamico"]:
        lookback = _safe_int(params.get("lookback", params.get("sr_lookback", 50)), 50)
        prox = _safe_float(params.get("proximity", 0.003), 0.003)
        wick_r = _safe_float(params.get("bounce_wick_ratio", params.get("wick_ratio", 0.0)), 0.0)

        header = _build_risk_mgmt_header(
            "Nexus Quant - Support & Resistance Zones", export_mode, initial_capital, pos_size_usd, max_open_trades, bars_to_hold, commission_pct
        )
        body = f'''
// ============================================================================
// 2. PARÁMETROS TÉCNICOS DE LA ESTRATEGIA (OPTIMIZADOS EN BACKTEST)
// ============================================================================
lookback   = input.int({lookback}, "Lookback Swings Soporte/Resistencia", minval=10, maxval=200)
proximity  = input.float({prox * 100:.2f}, "Zona de Proximidad %", step=0.05) / 100.0
wick_ratio = input.float({wick_r:.2f}, "Min Ratio Mecha Rechazo", minval=0.0, maxval=0.8, step=0.05)

// ============================================================================
// 3. CÁLCULO DE INDICADORES Y CONDICIONES DE ENTRADA
// ============================================================================
rolling_high = ta.highest(high[1], lookback)
rolling_low  = ta.lowest(low[1], lookback)

candle_range = high - low
lower_wick = math.min(open, close) - low
upper_wick = high - math.max(open, close)

lower_wick_ratio = candle_range > 0 ? (lower_wick / candle_range) : 0.0
upper_wick_ratio = candle_range > 0 ? (upper_wick / candle_range) : 0.0

wick_call = wick_ratio <= 0.0 or (lower_wick_ratio >= wick_ratio)
wick_put  = wick_ratio <= 0.0 or (upper_wick_ratio >= wick_ratio)

bool call_signal = (low <= rolling_low * (1.0 + proximity)) and (close > rolling_low) and (ta.change(close) > 0) and wick_call
bool put_signal  = (high >= rolling_high * (1.0 - proximity)) and (close < rolling_high) and (ta.change(close) < 0) and wick_put

plot(rolling_high, title="Resistencia Dinámica", color=color.new(#f43f5e, 0), linewidth=2, style=plot.style_stepline)
plot(rolling_low, title="Soporte Dinámico", color=color.new(#10b981, 0), linewidth=2, style=plot.style_stepline)

plotshape(call_signal, title="S/R CALL", style=shape.triangleup, location=location.belowbar, color=#10b981, size=size.small, text="CALL")
plotshape(put_signal, title="S/R PUT", style=shape.triangledown, location=location.abovebar, color=#f43f5e, size=size.small, text="PUT")
'''
        footer = _build_execution_footer("support_resistance", export_mode)
        return header + body + footer

    # 7. DAILY CONFLUENCE (ELDER TRIPLE SCREEN MULTI-TIMEFRAME)
    if strat_key in ["daily_confluence", "confluencia_diaria", "confluencia_diaria_multiactivo"]:
        pullback_tol = _safe_float(params.get("pullback_tolerance", 0.015), 0.015)
        rsi_min_call = _safe_float(params.get("rsi_min_call", 25.0), 25.0)
        rsi_max_call = _safe_float(params.get("rsi_max_call", 55.0), 55.0)
        rsi_min_put = _safe_float(params.get("rsi_min_put", 45.0), 45.0)
        rsi_max_put = _safe_float(params.get("rsi_max_put", 75.0), 75.0)
        wick_r = _safe_float(params.get("wick_rejection_ratio", params.get("pinbar_wick_ratio", 0.35)), 0.35)
        ema_w_p = _safe_int(params.get("ema_weekly_period", 50), 50)
        ema_d_p = _safe_int(params.get("ema_daily_period", 20), 20)

        header = _build_risk_mgmt_header(
            "Nexus Quant - Confluencia MTF Semanal/Diaria", export_mode, initial_capital, pos_size_usd, max_open_trades, bars_to_hold, commission_pct
        )
        body = f'''
// ============================================================================
// 2. PARÁMETROS TÉCNICOS DE LA ESTRATEGIA (OPTIMIZADOS EN BACKTEST)
// ============================================================================
ema_w_period  = input.int({ema_w_p}, "Periodo EMA Semanal Macro", minval=10, maxval=200)
ema_d_period  = input.int({ema_d_p}, "Periodo EMA Diaria", minval=5, maxval=100)
rsi_period    = input.int(14, "Periodo RSI", minval=2, maxval=50)
pullback_tol  = input.float({pullback_tol:.3f}, "Tolerancia Pullback EMA (0.015 = 1.5%)")
rsi_min_call  = input.float({rsi_min_call:.1f}, "RSI Mínimo CALL")
rsi_max_call  = input.float({rsi_max_call:.1f}, "RSI Máximo CALL")
rsi_min_put   = input.float({rsi_min_put:.1f}, "RSI Mínimo PUT")
rsi_max_put   = input.float({rsi_max_put:.1f}, "RSI Máximo PUT")
wick_ratio    = input.float({wick_r:.2f}, "Ratio Mínimo Rechazo Mecha (Pinbar)")
exclude_wknd  = input.bool(true, "Excluir Operaciones en Fin de Semana")

// ============================================================================
// 3. CÁLCULO MTF SIN LOOKAHEAD BIAS
// ============================================================================
ema_weekly      = request.security(syminfo.tickerid, "W", ta.ema(close, ema_w_period)[1], barmerge.gaps_off, barmerge.lookahead_off)
close_weekly    = request.security(syminfo.tickerid, "W", close[1], barmerge.gaps_off, barmerge.lookahead_off)
weekly_bull     = (close_weekly > ema_weekly) and (ta.change(ema_weekly) > 0)
weekly_bear     = (close_weekly < ema_weekly) and (ta.change(ema_weekly) < 0)

ema_daily       = ta.ema(close, ema_d_period)
rsi_daily       = ta.rsi(close, rsi_period)

candle_range    = high - low
lower_wick      = math.min(open, close) - low
upper_wick      = high - math.max(open, close)
wick_call       = candle_range > 0 and (lower_wick / candle_range) >= wick_ratio
wick_put        = candle_range > 0 and (upper_wick / candle_range) >= wick_ratio

pullback_call   = (low <= ema_daily * (1 + pullback_tol)) and (close >= ema_daily * (1 - pullback_tol))
pullback_put    = (high >= ema_daily * (1 - pullback_tol)) and (close <= ema_daily * (1 + pullback_tol))

rsi_ok_call     = rsi_daily >= rsi_min_call and rsi_daily <= rsi_max_call
rsi_ok_put      = rsi_daily >= rsi_min_put and rsi_daily <= rsi_max_put

valid_day       = not exclude_wknd or (dayofweek != dayofweek.saturday and dayofweek != dayofweek.sunday)

bool call_signal = weekly_bull and pullback_call and rsi_ok_call and wick_call and valid_day and not (weekly_bull[1] and pullback_call[1])
bool put_signal  = weekly_bear and pullback_put  and rsi_ok_put  and wick_put  and valid_day and not (weekly_bear[1] and pullback_put[1])

plot(ema_daily, title="EMA 20 Diaria", color=color.new(#f59e0b, 0), linewidth=2)
plot(ema_weekly, title="EMA 50 Semanal", color=color.new(#a855f7, 0), linewidth=3)

plotshape(call_signal, title="Señal CALL Confluencia", style=shape.triangleup, location=location.belowbar, color=#10b981, size=size.small, text="CALL")
plotshape(put_signal, title="Señal PUT Confluencia", style=shape.triangledown, location=location.abovebar, color=#f43f5e, size=size.small, text="PUT")
'''
        footer = _build_execution_footer("daily_confluence", export_mode)
        return header + body + footer

    # 8. MTF TCVE (TREND VOLUME EXHAUSTION)
    if strat_key in ["mtf_tcve", "tcve"]:
        bb_p = _safe_int(params.get("bb_period", 20), 20)
        bb_std = _safe_float(params.get("bb_std", 2.0), 2.0)
        wick_r = _safe_float(params.get("wick_ratio", 0.35), 0.35)
        vol_m = _safe_float(params.get("vol_mult", 1.3), 1.3)
        rsi_p = _safe_int(params.get("rsi_period", 7), 7)
        rsi_os = _safe_float(params.get("rsi_oversold", 25.0), 25.0)
        rsi_ob = _safe_float(params.get("rsi_overbought", 75.0), 75.0)

        header = _build_risk_mgmt_header(
            "Nexus Quant - MTF Trend Volume Exhaustion", export_mode, initial_capital, pos_size_usd, max_open_trades, bars_to_hold, commission_pct
        )
        body = f'''
// ============================================================================
// 2. PARÁMETROS TÉCNICOS DE LA ESTRATEGIA (OPTIMIZADOS EN BACKTEST)
// ============================================================================
bb_period      = input.int({bb_p}, "Periodo Bollinger", minval=5, maxval=100)
bb_std         = input.float({bb_std:.2f}, "Desviación Estándar BB", minval=1.0, maxval=4.0, step=0.1)
wick_ratio     = input.float({wick_r:.2f}, "Min Ratio Mecha", minval=0.0, maxval=0.8, step=0.05)
vol_mult       = input.float({vol_m:.2f}, "Multiplicador Volumen", minval=0.0, maxval=5.0, step=0.1)
rsi_period     = input.int({rsi_p}, "Periodo RSI", minval=2, maxval=50)
rsi_oversold   = input.float({rsi_os:.1f}, "RSI Sobreventa", minval=5.0, maxval=45.0)
rsi_overbought = input.float({rsi_ob:.1f}, "RSI Sobrecompra", minval=55.0, maxval=95.0)

// ============================================================================
// 3. CÁLCULO DE INDICADORES Y CONDICIONES DE ENTRADA
// ============================================================================
ema_20 = ta.ema(close, 20)
ema_50 = ta.ema(close, 50)
[bb_mid, bb_upper, bb_lower] = ta.bb(close, bb_period, bb_std)
rsi_val = ta.rsi(close, rsi_period)

vol_sma = ta.sma(volume, 20)
vol_climax = na(volume) or vol_sma == 0 or (volume >= vol_sma * vol_mult)

candle_range = high - low
lower_wick = math.min(open, close) - low
upper_wick = high - math.max(open, close)

lower_wick_ratio = candle_range > 0 ? (lower_wick / candle_range) : 0.0
upper_wick_ratio = candle_range > 0 ? (upper_wick / candle_range) : 0.0

ema_trend_call = (ema_20 >= ema_50) or (close >= ema_50)
ema_trend_put  = (ema_20 <= ema_50) or (close <= ema_50)

bool call_signal = ema_trend_call and (low <= bb_lower) and (rsi_val <= rsi_oversold) and (lower_wick_ratio >= wick_ratio) and vol_climax
bool put_signal  = ema_trend_put  and (high >= bb_upper) and (rsi_val >= rsi_overbought) and (upper_wick_ratio >= wick_ratio) and vol_climax

plot(ema_20, title="EMA 20", color=color.new(#f59e0b, 0))
plot(ema_50, title="EMA 50", color=color.new(#38bdf8, 0))
plot(bb_upper, title="BB Upper", color=color.new(#c084fc, 0))
plot(bb_lower, title="BB Lower", color=color.new(#c084fc, 0))

plotshape(call_signal, title="TCVE CALL", style=shape.triangleup, location=location.belowbar, color=#10b981, size=size.small, text="CALL")
plotshape(put_signal, title="TCVE PUT", style=shape.triangledown, location=location.abovebar, color=#f43f5e, size=size.small, text="PUT")
'''
        footer = _build_execution_footer("mtf_tcve", export_mode)
        return header + body + footer

    # 9. DEESR (DUAL EXTREME ENVELOPE STRETCH REVERSAL)
    if strat_key in ["deesr", "dual_extreme_envelope"]:
        bb_p = _safe_int(params.get("bb_period", 20), 20)
        bb_std = _safe_float(params.get("bb_std", 2.5), 2.5)
        kc_p = _safe_int(params.get("kc_period", 20), 20)
        kc_mult = _safe_float(params.get("kc_mult", 2.0), 2.0)
        rsi_f = _safe_int(params.get("rsi_fast_period", 3), 3)
        rsi_s = _safe_int(params.get("rsi_slow_period", 14), 14)
        max_body = _safe_float(params.get("max_body_ratio", 0.45), 0.45)
        min_wick = _safe_float(params.get("min_wick_ratio", 0.35), 0.35)

        header = _build_risk_mgmt_header(
            "Nexus Quant - DEESR Dual Stretch", export_mode, initial_capital, pos_size_usd, max_open_trades, bars_to_hold, commission_pct
        )
        body = f'''
// ============================================================================
// 2. PARÁMETROS TÉCNICOS DE LA ESTRATEGIA (OPTIMIZADOS EN BACKTEST)
// ============================================================================
bb_period   = input.int({bb_p}, "Periodo Bollinger", minval=5, maxval=100)
bb_std      = input.float({bb_std:.2f}, "Desviación Estándar BB", minval=1.0, maxval=4.0, step=0.1)
kc_period   = input.int({kc_p}, "Periodo Keltner Channel", minval=5, maxval=100)
kc_mult     = input.float({kc_mult:.2f}, "Multiplicador Keltner ATR", minval=1.0, maxval=4.0, step=0.1)
rsi_fast_p  = input.int({rsi_f}, "Periodo RSI Rápido", minval=2, maxval=10)
rsi_slow_p  = input.int({rsi_s}, "Periodo RSI Lento", minval=5, maxval=50)
max_body_r  = input.float({max_body:.2f}, "Máximo Ratio de Cuerpo", minval=0.1, maxval=0.8, step=0.05)
min_wick_r  = input.float({min_wick:.2f}, "Mínimo Ratio de Mecha", minval=0.1, maxval=0.8, step=0.05)

// ============================================================================
// 3. CÁLCULO DE INDICADORES Y CONDICIONES DE ENTRADA
// ============================================================================
[bb_mid, bb_upper, bb_lower] = ta.bb(close, bb_period, bb_std)
kc_ma = ta.ema(close, kc_period)
kc_atr = ta.atr(kc_period)
kc_upper = kc_ma + (kc_mult * kc_atr)
kc_lower = kc_ma - (kc_mult * kc_atr)

rsi_fast_val = ta.rsi(close, rsi_fast_p)
rsi_slow_val = ta.rsi(close, rsi_slow_p)

candle_range = high - low
candle_body  = math.abs(close - open)
lower_wick   = math.min(close, open) - low
upper_wick   = high - math.max(close, open)

body_ratio = candle_range > 0 ? (candle_body / candle_range) : 1.0
lower_wick_ratio = candle_range > 0 ? (lower_wick / candle_range) : 0.0
upper_wick_ratio = candle_range > 0 ? (upper_wick / candle_range) : 0.0

bool call_signal = (close <= bb_lower) and (low <= kc_lower) and (rsi_fast_val <= 15.0) and (rsi_slow_val <= 35.0) and (body_ratio <= max_body_r) and (lower_wick_ratio >= min_wick_r)
bool put_signal  = (close >= bb_upper) and (high >= kc_upper) and (rsi_fast_val >= 85.0) and (rsi_slow_val >= 65.0) and (body_ratio <= max_body_r) and (upper_wick_ratio >= min_wick_r)

plot(bb_upper, title="BB Upper", color=color.new(#38bdf8, 0))
plot(bb_lower, title="BB Lower", color=color.new(#38bdf8, 0))
plot(kc_upper, title="KC Upper", color=color.new(#c084fc, 0))
plot(kc_lower, title="KC Lower", color=color.new(#c084fc, 0))

plotshape(call_signal, title="DEESR CALL", style=shape.triangleup, location=location.belowbar, color=#10b981, size=size.small, text="CALL")
plotshape(put_signal, title="DEESR PUT", style=shape.triangledown, location=location.abovebar, color=#f43f5e, size=size.small, text="PUT")
'''
        footer = _build_execution_footer("deesr", export_mode)
        return header + body + footer

    # 10. ISLG RS (INSTITUTIONAL SWEEP LIQUIDITY GRAB)
    if strat_key in ["islg_rs", "islg", "liquidity_grab"]:
        lookback = _safe_int(params.get("lookback_period", 50), 50)
        sweep_r = _safe_float(params.get("min_sweep_atr_ratio", 0.15), 0.15)
        wick_r = _safe_float(params.get("wick_ratio", 0.35), 0.35)
        vol_m = _safe_float(params.get("vol_mult", 1.3), 1.3)
        rsi_p = _safe_int(params.get("rsi_period", 7), 7)

        header = _build_risk_mgmt_header(
            "Nexus Quant - ISLG Institutional Liquidity Grab", export_mode, initial_capital, pos_size_usd, max_open_trades, bars_to_hold, commission_pct
        )
        body = f'''
// ============================================================================
// 2. PARÁMETROS TÉCNICOS DE LA ESTRATEGIA (OPTIMIZADOS EN BACKTEST)
// ============================================================================
lookback_p  = input.int({lookback}, "Lookback Swings de Liquidez", minval=10, maxval=200)
sweep_ratio = input.float({sweep_r:.2f}, "Ratio Mínimo Barrido ATR", minval=0.05, maxval=1.0, step=0.05)
wick_r      = input.float({wick_r:.2f}, "Ratio Mínimo Mecha Rechazo", minval=0.1, maxval=0.8, step=0.05)
vol_mult    = input.float({vol_m:.2f}, "Multiplicador Volumen", minval=0.0, maxval=5.0, step=0.1)
rsi_p       = input.int({rsi_p}, "Periodo RSI", minval=2, maxval=50)

// ============================================================================
// 3. CÁLCULO DE INDICADORES Y CONDICIONES DE ENTRADA
// ============================================================================
atr_val = ta.atr(14)
swing_high = ta.highest(high[1], lookback_p)
swing_low  = ta.lowest(low[1], lookback_p)
rsi_val = ta.rsi(close, rsi_p)
vol_ma  = ta.sma(volume, 20)
vol_spike = na(volume) or vol_ma == 0 or (volume >= vol_ma * vol_mult)

candle_range = high - low
lower_wick   = math.min(close, open) - low
upper_wick   = high - math.max(close, open)
lower_wick_ratio = candle_range > 0 ? (lower_wick / candle_range) : 0.0
upper_wick_ratio = candle_range > 0 ? (upper_wick / candle_range) : 0.0

bool call_signal = (low < swing_low) and ((swing_low - low) >= (sweep_ratio * atr_val)) and (close >= (swing_low - 0.05 * atr_val)) and (lower_wick_ratio >= wick_r) and vol_spike and (rsi_val <= 30.0)
bool put_signal  = (high > swing_high) and ((high - swing_high) >= (sweep_ratio * atr_val)) and (close <= (swing_high + 0.05 * atr_val)) and (upper_wick_ratio >= wick_r) and vol_spike and (rsi_val >= 70.0)

plot(swing_high, title="Swing High Liquidity", color=color.new(#f43f5e, 0), style=plot.style_stepline, linewidth=2)
plot(swing_low, title="Swing Low Liquidity", color=color.new(#10b981, 0), style=plot.style_stepline, linewidth=2)

plotshape(call_signal, title="ISLG CALL", style=shape.triangleup, location=location.belowbar, color=#10b981, size=size.small, text="CALL")
plotshape(put_signal, title="ISLG PUT", style=shape.triangledown, location=location.abovebar, color=#f43f5e, size=size.small, text="PUT")
'''
        footer = _build_execution_footer("islg_rs", export_mode)
        return header + body + footer

    # 11. VOLATILITY SQUEEZE ML (MACHINE LEARNING META-FILTER)
    if strat_key in ["volatility_squeeze_ml", "squeeze_ml", "ml_squeeze"]:
        bb_pctl_th = _safe_float(params.get("bb_pctl_thresh", 0.35), 0.35)
        prob_th = _safe_float(params.get("prob_thresh", 0.53), 0.53)
        use_mtf = params.get("use_mtf", True)

        header = _build_risk_mgmt_header(
            "Nexus Quant - Volatility Squeeze ML Meta-Filter", export_mode, initial_capital, pos_size_usd, max_open_trades, bars_to_hold, commission_pct
        )
        body = f'''
// ============================================================================
// 2. PARÁMETROS TÉCNICOS DE LA ESTRATEGIA (OPTIMIZADOS EN BACKTEST)
// ============================================================================
bb_pctl_thresh = input.float({bb_pctl_th:.2f}, "Percentil Máximo Ancho BB (Compresión)", minval=0.10, maxval=0.80, step=0.05)
prob_thresh    = input.float({prob_th:.2f}, "Umbral Probabilidad P(WIN) ML", minval=0.50, maxval=0.90, step=0.01)
use_mtf        = input.bool({str(use_mtf).lower()}, "Activar Filtro Macro MTF EMA")

// ============================================================================
// 3. CÁLCULO DE FEATURES DE MICROESTRUCTURA Y SCORING DE DECISIÓN ML
// ============================================================================
candle_range = math.max(high - low, 1e-8)
lower_wick   = math.min(open, close) - low
upper_wick   = high - math.max(open, close)
wick_lower_r = lower_wick / candle_range
wick_upper_r = upper_wick / candle_range

[bb_mid, bb_upper, bb_lower] = ta.bb(close, 20, 2.0)
bb_w = bb_mid > 0 ? (4.0 * ta.stdev(close, 20) / bb_mid) : 0.0
bb_pctl = ta.percentrank(bb_w, 100) / 100.0

ema_20 = ta.ema(close, 20)
ema_50 = ta.ema(close, 50)
atr_14 = math.max(ta.atr(14), 1e-8)
dist_ema20 = math.abs(close - ema_20) / atr_14
rsi_7 = ta.rsi(close, 7)

vol_sma = ta.sma(volume, 20)
rel_vol = vol_sma > 0 ? (volume / vol_sma) : 1.0

mtf_bull = not use_mtf or (ema_20 >= ema_50)
mtf_bear = not use_mtf or (ema_20 <= ema_50)

squeeze_ok = bb_pctl <= bb_pctl_thresh
base_call  = squeeze_ok and mtf_bull and (dist_ema20 <= 2.5) and (close >= open) and (wick_lower_r >= 0.15) and (rsi_7 >= 25) and (rsi_7 <= 75)
base_put   = squeeze_ok and mtf_bear and (dist_ema20 <= 2.5) and (close <= open) and (wick_upper_r >= 0.15) and (rsi_7 <= 75) and (rsi_7 >= 25)

// Ensamble probabilístico de decisión ML
f_score_call = 0.50
f_score_put  = 0.50
if bb_pctl <= 0.20
    f_score_call += 0.04
    f_score_put  += 0.04
if wick_lower_r >= 0.35
    f_score_call += 0.05
if wick_upper_r >= 0.35
    f_score_put  += 0.05
if rel_vol >= 1.2
    f_score_call += 0.03
    f_score_put  += 0.03
if rsi_7 >= 35 and rsi_7 <= 55
    f_score_call += 0.04
if rsi_7 <= 65 and rsi_7 >= 45
    f_score_put  += 0.04
if dist_ema20 <= 1.0
    f_score_call += 0.03
    f_score_put  += 0.03

bool call_signal = base_call and (f_score_call >= prob_thresh) and not (base_call[1] and f_score_call[1] >= prob_thresh)
bool put_signal  = base_put  and (f_score_put  >= prob_thresh) and not (base_put[1] and f_score_put[1] >= prob_thresh)

plot(ema_20, title="EMA 20", color=color.new(#f59e0b, 0))
plot(ema_50, title="EMA 50", color=color.new(#38bdf8, 0))
plot(bb_upper, title="BB Upper", color=color.new(#c084fc, 0))
plot(bb_lower, title="BB Lower", color=color.new(#c084fc, 0))

plotshape(call_signal, title="ML Squeeze CALL", style=shape.triangleup, location=location.belowbar, color=#10b981, size=size.small, text="CALL ML")
plotshape(put_signal, title="ML Squeeze PUT", style=shape.triangledown, location=location.abovebar, color=#f43f5e, size=size.small, text="PUT ML")
'''
        footer = _build_execution_footer("volatility_squeeze_ml", export_mode)
        return header + body + footer

    # 12. CLIMAX REVERSAL (STREAK COUNT + WICK REJECTION + BODY CONTRACTION)
    if strat_key in ["climax_reversal", "climax_agotamiento"]:
        streak_len = _safe_int(params.get("streak_len", params.get("min_streak", 3)), 3)
        wick_r = _safe_float(params.get("wick_ratio", params.get("min_wick_ratio", 0.35)), 0.35)
        vol_m = _safe_float(params.get("vol_mult", params.get("volume_mult", 1.3)), 1.3)
        rsi_p = _safe_int(params.get("rsi_period", 7), 7)
        rsi_ext = _safe_float(params.get("rsi_extreme", 30.0), 30.0)
        rsi_os = _safe_float(params.get("rsi_oversold", rsi_ext), rsi_ext)
        rsi_ob = _safe_float(params.get("rsi_overbought", 100.0 - rsi_ext), 100.0 - rsi_ext)
        check_exh = params.get("check_exhaustion", True)
        bb_p = _safe_int(params.get("bb_period", 20), 20)
        bb_std = _safe_float(params.get("bb_std", 2.0), 2.0)

        header = _build_risk_mgmt_header(
            "Nexus Quant - Climax & Streak Exhaustion", export_mode, initial_capital, pos_size_usd, max_open_trades, bars_to_hold, commission_pct
        )
        body = f'''
// ============================================================================
// 2. PARÁMETROS TÉCNICOS DE LA ESTRATEGIA (OPTIMIZADOS EN BACKTEST)
// ============================================================================
streak_len       = input.int({streak_len}, "Racha de Velas Consecutivas", minval=2, maxval=10)
wick_ratio       = input.float({wick_r:.2f}, "Ratio Mínimo Mecha Clímax", minval=0.1, maxval=0.8, step=0.05)
vol_mult         = input.float({vol_m:.2f}, "Multiplicador Volumen", minval=0.0, maxval=5.0, step=0.1)
rsi_period       = input.int({rsi_p}, "Periodo RSI", minval=2, maxval=50)
rsi_oversold     = input.float({rsi_os:.1f}, "RSI Sobreventa", minval=5.0, maxval=45.0)
rsi_overbought   = input.float({rsi_ob:.1f}, "RSI Sobrecompra", minval=55.0, maxval=95.0)
check_exhaustion = input.bool({str(check_exh).lower()}, "Validar Contracción de Cuerpo (Agotamiento)")
bb_period        = input.int({bb_p}, "Periodo Bollinger", minval=5, maxval=100)
bb_std           = input.float({bb_std:.2f}, "Desviación Estándar BB", minval=1.0, maxval=4.0, step=0.1)

// ============================================================================
// 3. CÁLCULO DE INDICADORES Y CONDICIONES DE ENTRADA
// ============================================================================
[bb_mid, bb_upper, bb_lower] = ta.bb(close, bb_period, bb_std)
rsi_val = ta.rsi(close, rsi_period)

candle_range = math.max(high - low, 1e-8)
body_size    = math.abs(close - open)
lower_wick_ratio = (math.min(open, close) - low) / candle_range
upper_wick_ratio = (high - math.max(open, close)) / candle_range
body_ratio       = body_size / candle_range

bool bull_streak = true
bool bear_streak = true
for i = 1 to streak_len
    bull_streak := bull_streak and (close[i] > open[i])
    bear_streak := bear_streak and (close[i] < open[i])

bool exhaustion_bull = not check_exhaustion or (body_size <= body_size[1] * 1.15) or (body_ratio <= 0.50)
bool exhaustion_bear = not check_exhaustion or (body_size <= body_size[1] * 1.15) or (body_ratio <= 0.50)

vol_sma = ta.sma(volume, 20)
vol_spike = na(volume) or vol_sma == 0 or (volume >= vol_sma * vol_mult)

bool call_signal = bear_streak and (lower_wick_ratio >= wick_ratio) and vol_spike and (low <= bb_lower) and (rsi_val <= rsi_oversold) and exhaustion_bear
bool put_signal  = bull_streak and (upper_wick_ratio >= wick_ratio) and vol_spike and (high >= bb_upper) and (rsi_val >= rsi_overbought) and exhaustion_bull

plot(bb_upper, title="BB Upper", color=color.new(#c084fc, 0))
plot(bb_lower, title="BB Lower", color=color.new(#c084fc, 0))

plotshape(call_signal, title="Climax CALL", style=shape.triangleup, location=location.belowbar, color=#10b981, size=size.small, text="CALL")
plotshape(put_signal, title="Climax PUT", style=shape.triangledown, location=location.abovebar, color=#f43f5e, size=size.small, text="PUT")
'''
        footer = _build_execution_footer("climax_reversal", export_mode)
        return header + body + footer

    # 13. GENETIC COMPOSITE (MULTI-FILTER ORTHOGONAL 6-LAYER ARCHETYPE)
    rsi_p = _safe_int(params.get("rsi_period", 14), 14)
    rsi_os = _safe_float(params.get("rsi_oversold", 30.0), 30.0)
    rsi_ob = _safe_float(params.get("rsi_overbought", 70.0), 70.0)
    rsi_en = params.get("rsi_enabled", True)

    bb_p = _safe_int(params.get("bb_period", 20), 20)
    bb_std = _safe_float(params.get("bb_std", 2.0), 2.0)
    bb_en = params.get("bb_enabled", True)

    ema_f_p = _safe_int(params.get("ema_fast_period", 9), 9)
    ema_s_p = _safe_int(params.get("ema_slow_period", 21), 21)
    ema_en = params.get("ema_enabled", False)

    pinbar_en = params.get("rejection_filter_enabled", False)
    squeeze_en = params.get("volatility_filter_enabled", False)

    header = _build_risk_mgmt_header(
        "Nexus Quant - Compuesta Multicapa (Genetic Composite)", export_mode, initial_capital, pos_size_usd, max_open_trades, bars_to_hold, commission_pct
    )
    body = f'''
// ============================================================================
// 2. PARÁMETROS TÉCNICOS DE LA ESTRATEGIA (OPTIMIZADOS EN BACKTEST)
// ============================================================================
use_rsi        = input.bool({str(rsi_en).lower()}, "Activar Filtro RSI")
rsi_period     = input.int({rsi_p}, "Periodo RSI", minval=2, maxval=50)
rsi_oversold   = input.float({rsi_os:.1f}, "RSI Sobreventa (CALL)", minval=5.0, maxval=45.0)
rsi_overbought = input.float({rsi_ob:.1f}, "RSI Sobrecompra (PUT)", minval=55.0, maxval=95.0)

use_bb         = input.bool({str(bb_en).lower()}, "Activar Bandas Bollinger")
bb_period      = input.int({bb_p}, "Periodo Bollinger", minval=5, maxval=100)
bb_std         = input.float({bb_std:.2f}, "Desviación Estándar BB", minval=1.0, maxval=4.0, step=0.1)

use_ema        = input.bool({str(ema_en).lower()}, "Activar Filtro Tendencia EMA")
ema_fast_p     = input.int({ema_f_p}, "EMA Rápida", minval=2, maxval=50)
ema_slow_p     = input.int({ema_s_p}, "EMA Lenta", minval=5, maxval=200)

use_pinbar     = input.bool({str(pinbar_en).lower()}, "Filtro Rechazo Mecha (Pinbar)")
use_squeeze    = input.bool({str(squeeze_en).lower()}, "Filtro Squeeze Volatilidad")

// ============================================================================
// 3. CÁLCULO DE INDICADORES Y CONDICIONES DE ENTRADA
// ============================================================================
rsi_val        = ta.rsi(close, rsi_period)
[bb_mid, bb_upper, bb_lower] = ta.bb(close, bb_period, bb_std)
ema_fast       = ta.ema(close, ema_fast_p)
ema_slow       = ta.ema(close, ema_slow_p)

candle_total   = high - low
lower_wick     = math.min(open, close) - low
upper_wick     = high - math.max(open, close)
pinbar_call    = candle_total > 0 and (lower_wick / candle_total) >= 0.55
pinbar_put     = candle_total > 0 and (upper_wick / candle_total) >= 0.55

bb_width       = (bb_upper - bb_lower) / bb_mid
squeeze_active = ta.lowest(bb_width, 10) == bb_width

trend_up       = not use_ema or (ema_fast > ema_slow and close > ema_slow)
trend_down     = not use_ema or (ema_fast < ema_slow and close < ema_slow)

filter_call    = (not use_rsi or rsi_val <= rsi_oversold) and (not use_bb or close <= bb_lower) and trend_up and (not use_pinbar or pinbar_call) and (not use_squeeze or not squeeze_active)
filter_put     = (not use_rsi or rsi_val >= rsi_overbought) and (not use_bb or close >= bb_upper) and trend_down and (not use_pinbar or pinbar_put) and (not use_squeeze or not squeeze_active)

bool call_signal = filter_call and not filter_call[1]
bool put_signal  = filter_put  and not filter_put[1]

plot(bb_upper, title="BB Superior", color=color.new(#38bdf8, 50))
plot(bb_lower, title="BB Inferior", color=color.new(#38bdf8, 50))
plot(use_ema ? ema_fast : na, title="EMA Rápida", color=color.new(#f59e0b, 0))
plot(use_ema ? ema_slow : na, title="EMA Lenta", color=color.new(#c084fc, 0))

plotshape(call_signal, title="Señal CALL", style=shape.triangleup, location=location.belowbar, color=#10b981, size=size.small, text="CALL")
plotshape(put_signal, title="Señal PUT", style=shape.triangledown, location=location.abovebar, color=#f43f5e, size=size.small, text="PUT")
'''
    footer = _build_execution_footer("genetic_composite", export_mode)
    return header + body + footer
