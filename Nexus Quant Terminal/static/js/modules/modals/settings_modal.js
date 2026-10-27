/**
 * settings_modal.js - Strategy Detection, Parameter Tuning, and Pine Script v6 Generators (Part 1: Strats 1-6)
 * Nexus Quant Terminal
 */

export function detectStrategyType(strat) {
    const raw = (strat.type || strat.key || strat.strategy_key || strat.name || '').toLowerCase();
    if (raw.includes('daily_confluence') || raw.includes('confluencia')) return 'daily_confluence';
    if (raw.includes('deesr') || raw.includes('envelope')) return 'deesr';
    if (raw.includes('islg') || raw.includes('liquidity') || raw.includes('barrido')) return 'islg_rs';
    if (raw.includes('mean_reversion') || raw.includes('reversión a la media')) return 'mean_reversion';
    if (raw.includes('rsi_extreme') || raw.includes('rsi extremo')) return 'rsi_extremes';
    if (raw.includes('bollinger_bounce') || raw.includes('rebote') || raw.includes('bounce')) return 'bollinger_bounce';
    if (raw.includes('ema_cross') || raw.includes('cruce')) return 'ema_cross';
    if (raw.includes('volatility_squeeze_ml') || (raw.includes('squeeze') && raw.includes('ml')) || raw.includes('meta-filter')) return 'volatility_squeeze_ml';
    if (raw.includes('volatility_squeeze') || raw.includes('carter') || raw.includes('squeeze')) return 'volatility_squeeze';
    if (raw.includes('support_resistance') || raw.includes('soporte') || raw.includes('resistencia')) return 'support_resistance';
    if (raw.includes('mtf_tcve') || raw.includes('tcve') || raw.includes('exhaustion') || raw.includes('agotamiento')) return 'mtf_tcve';
    if (raw.includes('climax') || raw.includes('racha') || raw.includes('streak')) return 'climax_reversal';
    return 'genetic_composite';
}

export function buildRiskHeaderV6(title, mode, capital, posSize, maxTrades, holdBars, commission) {
    const isStrat = mode === 'strategy';
    const header = isStrat ? `//@version=6
strategy("${title} (Bot Ejecutable)", 
         overlay=true, 
         initial_capital=${capital.toFixed(1)}, 
         default_qty_type=strategy.cash, 
         default_qty_value=${posSize.toFixed(1)}, 
         commission_type=strategy.commission.percent, 
         commission_value=${commission.toFixed(3)},
         pyramiding=${maxTrades})` : `//@version=6
indicator("${title} (Indicador de Señales)", overlay=true)`;

    const risk = `
// ============================================================================
// 1. CONFIGURACIÓN DE GESTIÓN DE CAPITAL Y RIESGO (MODIFICA AQUÍ TUS PARÁMETROS)
// ============================================================================
pos_size_usd    = input.float(${posSize.toFixed(1)}, "Tamaño de Posición por Trade ($ USD)", tooltip="Monto en dinero que arriesgas en cada entrada")
max_open_trades = input.int(${maxTrades}, "Máximo de Operaciones Simultáneas", minval=1)
bars_to_hold    = input.int(${holdBars}, "Expiración en Velas (Time Stop)", minval=1, tooltip="Cantidad de velas que se mantiene abierta la posición")
broker_fee_pct  = input.float(${commission.toFixed(2)}, "Comisión Estimada por Trade %") / 100.0
`;
    return header + '\n' + risk;
}

export function buildExecutionFooterV6(stratKey, mode) {
    let footer = `
// ============================================================================
// 4. ALERTAS NATIVAS Y WEBHOOKS DE AUTOMATIZACIÓN
// ============================================================================
alertcondition(call_signal, title="${stratKey.toUpperCase()} CALL Signal", message='{"action": "BUY_CALL", "strategy": "${stratKey}", "ticker": "' + syminfo.ticker + '", "close": ' + str.tostring(close) + '}')
alertcondition(put_signal, title="${stratKey.toUpperCase()} PUT Signal", message='{"action": "SELL_PUT", "strategy": "${stratKey}", "ticker": "' + syminfo.ticker + '", "close": ' + str.tostring(close) + '}')
`;
    if (mode === 'strategy') {
        footer += `
// ============================================================================
// 5. MOTOR DE EJECUCIÓN VIRTUAL DE ÓRDENES (TRADINGVIEW STRATEGY TESTER)
// ============================================================================
if call_signal and strategy.opentrades < max_open_trades
    strategy.entry("BUY_CALL", strategy.long, qty=pos_size_usd / close,
                   alert_message='{"action": "BUY_CALL", "strategy": "${stratKey}", "ticker": "' + syminfo.ticker + '", "amount": ' + str.tostring(pos_size_usd) + '}')

if put_signal and strategy.opentrades < max_open_trades
    strategy.entry("SELL_PUT", strategy.short, qty=pos_size_usd / close,
                   alert_message='{"action": "SELL_PUT", "strategy": "${stratKey}", "ticker": "' + syminfo.ticker + '", "amount": ' + str.tostring(pos_size_usd) + '}')

if strategy.opentrades > 0 and ta.barssince(strategy.opentrades.entry_time(0)) >= bars_to_hold
    strategy.close_all(comment="Expiración por tiempo alcanzada")
`;
    }
    return footer;
}

export function generateMeanReversionPine(bg, mode, header) {
    const smaP = bg.sma_period || 20;
    const thresh = bg.threshold !== undefined ? (bg.threshold * 100).toFixed(2) : '1.50';
    const atrP = bg.atr_period || 14;
    const atrPct = bg.atr_threshold_percentile || 50;
    const body = `
// 2. PARÁMETROS TÉCNICOS DE LA ESTRATEGIA
sma_period    = input.int(${smaP}, "Periodo SMA", minval=2, maxval=200)
threshold_pct = input.float(${thresh}, "Umbral Desviación %", step=0.1) / 100.0
atr_period    = input.int(${atrP}, "Periodo ATR Volatilidad", minval=2, maxval=100)
atr_pct_max   = input.float(${atrPct}, "Percentil Máximo ATR (%)", minval=10.0, maxval=100.0)

// 3. CÁLCULO DE INDICADORES Y ENTRADAS
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
plotshape(call_signal, title="CALL Signal", style=shape.triangleup, location=location.belowbar, color=#10b981, size=size.small, text="CALL")
plotshape(put_signal, title="PUT Signal", style=shape.triangledown, location=location.abovebar, color=#f43f5e, size=size.small, text="PUT")
`;
    return header + body + buildExecutionFooterV6('mean_reversion', mode);
}

export function generateRsiExtremesPine(bg, mode, header) {
    const rsiP = bg.rsi_period || 14;
    const oversold = bg.oversold || 25;
    const overbought = bg.overbought || 75;
    const wickR = bg.wick_ratio || 0.35;
    const volM = bg.vol_mult || 1.3;
    const body = `
// 2. PARÁMETROS TÉCNICOS DE LA ESTRATEGIA
rsi_period     = input.int(${rsiP}, "Periodo RSI", minval=2, maxval=50)
rsi_oversold   = input.float(${oversold}, "RSI Sobreventa (CALL)", minval=5.0, maxval=45.0)
rsi_overbought = input.float(${overbought}, "RSI Sobrecompra (PUT)", minval=55.0, maxval=95.0)
wick_ratio     = input.float(${wickR}, "Min Ratio Mecha Rechazo", minval=0.0, maxval=0.8, step=0.05)
vol_mult       = input.float(${volM}, "Multiplicador de Volumen", minval=0.0, maxval=5.0, step=0.1)

// 3. CÁLCULO DE INDICADORES Y ENTRADAS
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
`;
    return header + body + buildExecutionFooterV6('rsi_extremes', mode);
}

export function generateBollingerBouncePine(bg, mode, header) {
    const bbP = bg.bb_period || 20;
    const bbStd = bg.bb_std || 2.2;
    const wickR = bg.wick_ratio || 0.35;
    const volM = bg.vol_mult || 1.3;
    const body = `
// 2. PARÁMETROS TÉCNICOS DE LA ESTRATEGIA
bb_period  = input.int(${bbP}, "Periodo Bollinger", minval=5, maxval=100)
bb_std     = input.float(${bbStd}, "Desviación Estándar BB", minval=1.0, maxval=4.0, step=0.1)
wick_ratio = input.float(${wickR}, "Min Ratio Mecha", minval=0.0, maxval=0.8, step=0.05)
vol_mult   = input.float(${volM}, "Multiplicador Volumen", minval=0.0, maxval=5.0, step=0.1)

// 3. CÁLCULO DE INDICADORES Y ENTRADAS
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
plot(bb_upper, title="BB Upper", color=color.new(#f43f5e, 20))
plot(bb_mid, title="BB Mid", color=color.new(#94a3b8, 40))
plot(bb_lower, title="BB Lower", color=color.new(#10b981, 20))
plotshape(call_signal, title="BB Bounce CALL", style=shape.triangleup, location=location.belowbar, color=#10b981, size=size.small, text="CALL")
plotshape(put_signal, title="BB Bounce PUT", style=shape.triangledown, location=location.abovebar, color=#f43f5e, size=size.small, text="PUT")
`;
    return header + body + buildExecutionFooterV6('bollinger_bounce', mode);
}

export function generateEmaCrossPine(bg, mode, header) {
    const fastP = bg.fast_period || 9;
    const slowP = bg.slow_period || 21;
    const body = `
// 2. PARÁMETROS TÉCNICOS DE LA ESTRATEGIA
fast_p = input.int(${fastP}, "EMA Rápida", minval=2, maxval=50)
slow_p = input.int(${slowP}, "EMA Lenta", minval=5, maxval=200)

// 3. CÁLCULO DE INDICADORES Y ENTRADAS
ema_fast = ta.ema(close, fast_p)
ema_slow = ta.ema(close, slow_p)
bool call_signal = ta.crossover(ema_fast, ema_slow)
bool put_signal  = ta.crossunder(ema_fast, ema_slow)
plot(ema_fast, title="EMA Fast", color=color.new(#10b981, 0), linewidth=2)
plot(ema_slow, title="EMA Slow", color=color.new(#f43f5e, 0), linewidth=2)
plotshape(call_signal, title="EMA Cross CALL", style=shape.triangleup, location=location.belowbar, color=#10b981, size=size.small, text="CALL")
plotshape(put_signal, title="EMA Cross PUT", style=shape.triangledown, location=location.abovebar, color=#f43f5e, size=size.small, text="PUT")
`;
    return header + body + buildExecutionFooterV6('ema_cross', mode);
}

export function generateVolatilitySqueezePine(bg, mode, header) {
    const bbP = bg.bb_period || 20;
    const bbMult = bg.bb_mult || 1.5;
    const kcP = bg.kc_period || 20;
    const kcMult = bg.kc_mult || 2.0;
    const body = `
// 2. PARÁMETROS TÉCNICOS DE LA ESTRATEGIA
bb_period = input.int(${bbP}, "Periodo Bollinger", minval=5, maxval=100)
bb_mult   = input.float(${bbMult}, "Mult Bollinger", minval=0.5, maxval=3.0, step=0.1)
kc_period = input.int(${kcP}, "Periodo Keltner", minval=5, maxval=100)
kc_mult   = input.float(${kcMult}, "Mult Keltner", minval=0.5, maxval=3.0, step=0.1)

// 3. CÁLCULO DE INDICADORES Y ENTRADAS
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
`;
    return header + body + buildExecutionFooterV6('volatility_squeeze', mode);
}

export function generateSupportResistancePine(bg, mode, header) {
    const lookback = bg.lookback || bg.sr_lookback || 50;
    const prox = bg.proximity !== undefined ? (bg.proximity * 100).toFixed(2) : '0.30';
    const wickR = bg.bounce_wick_ratio || bg.wick_ratio || 0.0;
    const body = `
// 2. PARÁMETROS TÉCNICOS DE LA ESTRATEGIA
lookback   = input.int(${lookback}, "Lookback S/R", minval=10, maxval=200)
proximity  = input.float(${prox}, "Zona Proximidad %", step=0.05) / 100.0
wick_ratio = input.float(${wickR}, "Min Mecha Rebote", minval=0.0, maxval=0.8, step=0.05)

// 3. CÁLCULO DE INDICADORES Y ENTRADAS
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
`;
    return header + body + buildExecutionFooterV6('support_resistance', mode);
}
