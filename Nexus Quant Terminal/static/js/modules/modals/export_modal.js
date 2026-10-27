/**
 * export_modal.js - Pine Script v6 Export Modal Engine & Strategy Generators (Part 2)
 * Nexus Quant Terminal
 */

import {
    detectStrategyType,
    buildRiskHeaderV6,
    buildExecutionFooterV6,
    generateMeanReversionPine,
    generateRsiExtremesPine,
    generateBollingerBouncePine,
    generateEmaCrossPine,
    generateVolatilitySqueezePine,
    generateSupportResistancePine
} from './settings_modal.js';

export { detectStrategyType };

export function generateDailyConfluencePine(bg, mode, header) {
    const pullbackTol = (bg.pullback_tolerance || 0.015).toFixed(3);
    const rsiMinCall = (bg.rsi_min_call || 25.0).toFixed(1);
    const rsiMaxCall = (bg.rsi_max_call || 55.0).toFixed(1);
    const wickRatio = (bg.pinbar_wick_ratio || bg.wick_rejection_ratio || 0.35).toFixed(2);
    const emaWPeriod = bg.ema_weekly_period || 50;
    const emaDPeriod = bg.ema_daily_period || 20;
    const body = `
// 2. PARÁMETROS TÉCNICOS DE LA ESTRATEGIA
ema_w_period  = input.int(${emaWPeriod}, "Periodo EMA Semanal")
ema_d_period  = input.int(${emaDPeriod}, "Periodo EMA Diaria")
rsi_period    = input.int(14, "Periodo RSI")
pullback_tol  = input.float(${pullbackTol}, "Tolerancia Pullback EMA")
rsi_min_call  = input.float(${rsiMinCall}, "RSI Mínimo CALL")
rsi_max_call  = input.float(${rsiMaxCall}, "RSI Máximo CALL")
wick_ratio    = input.float(${wickRatio}, "Ratio Mínimo Mecha (Pinbar)")
exclude_wknd  = input.bool(true, "Excluir Fines de Semana")

// 3. MTF SIN LOOKAHEAD BIAS
ema_weekly    = request.security(syminfo.tickerid, "W", ta.ema(close, ema_w_period)[1], barmerge.gaps_off, barmerge.lookahead_off)
close_weekly  = request.security(syminfo.tickerid, "W", close[1], barmerge.gaps_off, barmerge.lookahead_off)
weekly_bull   = (close_weekly > ema_weekly) and (ta.change(ema_weekly) > 0)
ema_daily     = ta.ema(close, ema_d_period)
rsi_daily     = ta.rsi(close, rsi_period)
candle_range  = high - low
lower_wick    = math.min(open, close) - low
wick_call     = candle_range > 0 and (lower_wick / candle_range) >= wick_ratio
pullback_call = (low <= ema_daily * (1 + pullback_tol)) and (close >= ema_daily * (1 - pullback_tol))
rsi_call      = rsi_daily >= rsi_min_call and rsi_daily <= rsi_max_call
valid_day     = not exclude_wknd or (dayofweek != dayofweek.saturday and dayofweek != dayofweek.sunday)
bool call_signal = weekly_bull and pullback_call and rsi_call and wick_call and valid_day and not (weekly_bull[1] and pullback_call[1])
bool put_signal  = false
plot(ema_daily, title="EMA 20 Diaria", color=color.new(#f59e0b, 0), linewidth=2)
plot(ema_weekly, title="EMA 50 Semanal", color=color.new(#a855f7, 0), linewidth=3)
plotshape(call_signal, title="Señal CALL Confluencia", style=shape.triangleup, location=location.belowbar, color=#10b981, size=size.small, text="CALL")
`;
    return header + body + buildExecutionFooterV6('daily_confluence', mode);
}

export function generateMtfTcvePine(bg, mode, header) {
    const bbP = bg.bb_period || 20, bbStd = bg.bb_std || 2.0, wickR = bg.wick_ratio || 0.35, volM = bg.vol_mult || 1.3, rsiP = bg.rsi_period || 7, rsiOs = bg.rsi_oversold || 25.0, rsiOb = bg.rsi_overbought || 75.0;
    const body = `
// 2. PARÁMETROS TÉCNICOS
bb_period = input.int(${bbP}, "Periodo Bollinger")
bb_std = input.float(${bbStd}, "Desviación Estándar BB")
wick_ratio = input.float(${wickR}, "Min Ratio Mecha")
vol_mult = input.float(${volM}, "Multiplicador Volumen")
rsi_period = input.int(${rsiP}, "Periodo RSI")
rsi_oversold = input.float(${rsiOs}, "RSI Sobreventa")
rsi_overbought = input.float(${rsiOb}, "RSI Sobrecompra")
// 3. CÁLCULO
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
`;
    return header + body + buildExecutionFooterV6('mtf_tcve', mode);
}

export function generateDeesrPine(bg, mode, header) {
    const bbP = bg.bb_period || 20, bbStd = bg.bb_std || 2.5, kcP = bg.kc_period || 20, kcMult = bg.kc_mult || 2.0, rsiF = bg.rsi_fast_period || 3, rsiS = bg.rsi_slow_period || 14, maxBody = bg.max_body_ratio || 0.45, minWick = bg.min_wick_ratio || 0.35;
    const body = `
bb_period = input.int(${bbP}, "Periodo Bollinger")
bb_std = input.float(${bbStd}, "Desviación Estándar BB")
kc_period = input.int(${kcP}, "Periodo Keltner")
kc_mult = input.float(${kcMult}, "Multiplicador Keltner")
rsi_fast_p = input.int(${rsiF}, "RSI Rápido")
rsi_slow_p = input.int(${rsiS}, "RSI Lento")
max_body_r = input.float(${maxBody}, "Max Ratio Cuerpo")
min_wick_r = input.float(${minWick}, "Min Ratio Mecha")
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
`;
    return header + body + buildExecutionFooterV6('deesr', mode);
}

export function generateIslgRsPine(bg, mode, header) {
    const lookback = bg.lookback_period || 50, sweepR = bg.min_sweep_atr_ratio || 0.15, wickR = bg.wick_ratio || 0.35, volM = bg.vol_mult || 1.3, rsiP = bg.rsi_period || 7;
    const body = `
lookback_p  = input.int(${lookback}, "Lookback Swings")
sweep_ratio = input.float(${sweepR}, "Mínimo Barrido ATR Ratio")
wick_r      = input.float(${wickR}, "Min Ratio Mecha")
vol_mult    = input.float(${volM}, "Multiplicador Volumen")
rsi_p       = input.int(${rsiP}, "Periodo RSI")
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
`;
    return header + body + buildExecutionFooterV6('islg_rs', mode);
}

export function generateVolatilitySqueezeMlPine(bg, mode, header) {
    const bbPctlTh = bg.bb_pctl_thresh || 0.35, probTh = bg.prob_thresh || 0.53, useMtf = bg.use_mtf !== false;
    const body = `
bb_pctl_thresh = input.float(${bbPctlTh}, "Percentil Máximo Ancho BB")
prob_thresh    = input.float(${probTh}, "Umbral Probabilidad ML P(WIN)", minval=0.50, maxval=0.90, step=0.01)
use_mtf        = input.bool(${useMtf}, "Activar Filtro MTF EMA")
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
dist_ema20 = math.abs(close - ema_20) / math.max(ta.atr(14), 1e-8)
rsi_7 = ta.rsi(close, 7)
rel_vol = ta.sma(volume, 20) > 0 ? (volume / ta.sma(volume, 20)) : 1.0
mtf_bull = not use_mtf or (ema_20 >= ema_50)
mtf_bear = not use_mtf or (ema_20 <= ema_50)
squeeze_ok = bb_pctl <= bb_pctl_thresh
base_call  = squeeze_ok and mtf_bull and (dist_ema20 <= 2.5) and (close >= open) and (wick_lower_r >= 0.15) and (rsi_7 >= 25) and (rsi_7 <= 75)
base_put   = squeeze_ok and mtf_bear and (dist_ema20 <= 2.5) and (close <= open) and (wick_upper_r >= 0.15) and (rsi_7 <= 75) and (rsi_7 >= 25)
f_score_call = 0.50 + (bb_pctl <= 0.20 ? 0.04 : 0) + (wick_lower_r >= 0.35 ? 0.05 : 0) + (rel_vol >= 1.2 ? 0.03 : 0) + (rsi_7 >= 35 and rsi_7 <= 55 ? 0.04 : 0) + (dist_ema20 <= 1.0 ? 0.03 : 0)
f_score_put  = 0.50 + (bb_pctl <= 0.20 ? 0.04 : 0) + (wick_upper_r >= 0.35 ? 0.05 : 0) + (rel_vol >= 1.2 ? 0.03 : 0) + (rsi_7 <= 65 and rsi_7 >= 45 ? 0.04 : 0) + (dist_ema20 <= 1.0 ? 0.03 : 0)
bool call_signal = base_call and (f_score_call >= prob_thresh) and not (base_call[1] and f_score_call[1] >= prob_thresh)
bool put_signal  = base_put  and (f_score_put  >= prob_thresh) and not (base_put[1] and f_score_put[1] >= prob_thresh)
plot(ema_20, title="EMA 20", color=color.new(#f59e0b, 0))
plot(ema_50, title="EMA 50", color=color.new(#38bdf8, 0))
plot(bb_upper, title="BB Upper", color=color.new(#c084fc, 0))
plot(bb_lower, title="BB Lower", color=color.new(#c084fc, 0))
plotshape(call_signal, title="ML Squeeze CALL", style=shape.triangleup, location=location.belowbar, color=#10b981, size=size.small, text="CALL ML")
plotshape(put_signal, title="ML Squeeze PUT", style=shape.triangledown, location=location.abovebar, color=#f43f5e, size=size.small, text="PUT ML")
`;
    return header + body + buildExecutionFooterV6('volatility_squeeze_ml', mode);
}

export function generateClimaxReversalPine(bg, mode, header) {
    const streakLen = bg.streak_len || bg.min_streak || 3, wickR = bg.wick_ratio || bg.min_wick_ratio || 0.35, volM = bg.vol_mult || bg.volume_mult || 1.3, rsiP = bg.rsi_period || 7, rsiExtreme = bg.rsi_extreme || 30.0, rsiOs = bg.rsi_oversold || rsiExtreme, rsiOb = bg.rsi_overbought || (100.0 - rsiExtreme), checkExh = bg.check_exhaustion !== false, bbP = bg.bb_period || 20, bbStd = bg.bb_std || 2.0;
    const body = `
streak_len = input.int(${streakLen}, "Racha de Velas")
wick_ratio = input.float(${wickR}, "Min Mecha Clímax")
vol_mult = input.float(${volM}, "Multiplicador Volumen")
rsi_period = input.int(${rsiP}, "Periodo RSI")
rsi_oversold = input.float(${rsiOs}, "RSI Sobreventa")
rsi_overbought = input.float(${rsiOb}, "RSI Sobrecompra")
check_exhaustion = input.bool(${checkExh}, "Validar Contracción Cuerpo")
bb_period = input.int(${bbP}, "Periodo Bollinger")
bb_std = input.float(${bbStd}, "Desviación Estándar BB")
[bb_mid, bb_upper, bb_lower] = ta.bb(close, bb_period, bb_std)
rsi_val = ta.rsi(close, rsi_period)
candle_range = math.max(high - low, 1e-8)
body_size = math.abs(close - open)
lower_wick_ratio = (math.min(open, close) - low) / candle_range
upper_wick_ratio = (high - math.max(open, close)) / candle_range
body_ratio = body_size / candle_range
bool bull_streak = true, bool bear_streak = true
for i = 1 to streak_len
    bull_streak := bull_streak and (close[i] > open[i])
    bear_streak := bear_streak and (close[i] < open[i])
bool exhaustion_bull = not check_exhaustion or (body_size <= body_size[1] * 1.15) or (body_ratio <= 0.50)
bool exhaustion_bear = not check_exhaustion or (body_size <= body_size[1] * 1.15) or (body_ratio <= 0.50)
vol_spike = na(volume) or ta.sma(volume, 20) == 0 or (volume >= ta.sma(volume, 20) * vol_mult)
bool call_signal = bear_streak and (lower_wick_ratio >= wick_ratio) and vol_spike and (low <= bb_lower) and (rsi_val <= rsi_oversold) and exhaustion_bear
bool put_signal  = bull_streak and (upper_wick_ratio >= wick_ratio) and vol_spike and (high >= bb_upper) and (rsi_val >= rsi_overbought) and exhaustion_bull
plot(bb_upper, title="BB Upper", color=color.new(#c084fc, 0))
plot(bb_lower, title="BB Lower", color=color.new(#c084fc, 0))
plotshape(call_signal, title="Climax CALL", style=shape.triangleup, location=location.belowbar, color=#10b981, size=size.small, text="CALL")
plotshape(put_signal, title="Climax PUT", style=shape.triangledown, location=location.abovebar, color=#f43f5e, size=size.small, text="PUT")
`;
    return header + body + buildExecutionFooterV6('climax_reversal', mode);
}

export function generateGeneticCompositePine(bg, mode, header) {
    const rsiP = bg.rsi_period || 14, rsiOversold = bg.rsi_oversold || 30.0, rsiOverbought = bg.rsi_overbought || 70.0, rsiEnabled = bg.rsi_enabled !== false;
    const bbP = bg.bb_period || 20, bbStd = bg.bb_std || 2.0, bbEnabled = bg.bb_enabled !== false;
    const emaFastP = bg.ema_fast_period || 9, emaSlowP = bg.ema_slow_period || 21, emaEnabled = bg.ema_enabled === true;
    const rejectionEnabled = bg.rejection_filter_enabled === true, volatilityEnabled = bg.volatility_filter_enabled === true;
    const body = `
use_rsi = input.bool(${rsiEnabled}, "Activar Filtro RSI")
rsi_period = input.int(${rsiP}, "Periodo RSI")
rsi_oversold = input.float(${rsiOversold.toFixed(1)}, "RSI Sobreventa (CALL)")
rsi_overbought = input.float(${rsiOverbought.toFixed(1)}, "RSI Sobrecompra (PUT)")
use_bb = input.bool(${bbEnabled}, "Activar Bandas Bollinger")
bb_period = input.int(${bbP}, "Periodo Bollinger")
bb_std = input.float(${bbStd.toFixed(1)}, "Desviación Estándar BB")
use_ema = input.bool(${emaEnabled}, "Activar Filtro Tendencia EMA")
ema_fast_p = input.int(${emaFastP}, "EMA Rápida")
ema_slow_p = input.int(${emaSlowP}, "EMA Lenta")
use_pinbar = input.bool(${rejectionEnabled}, "Filtro Rechazo Mecha (Pinbar)")
use_squeeze = input.bool(${volatilityEnabled}, "Filtro Squeeze Volatilidad")
rsi_val = ta.rsi(close, rsi_period)
[bb_mid, bb_upper, bb_lower] = ta.bb(close, bb_period, bb_std)
ema_fast = ta.ema(close, ema_fast_p)
ema_slow = ta.ema(close, ema_slow_p)
candle_total = high - low
pinbar_call = candle_total > 0 and ((math.min(open, close) - low) / candle_total) >= 0.55
pinbar_put  = candle_total > 0 and ((high - math.max(open, close)) / candle_total) >= 0.55
bb_width = (bb_upper - bb_lower) / bb_mid
squeeze_active = ta.lowest(bb_width, 10) == bb_width
trend_up   = not use_ema or (ema_fast > ema_slow and close > ema_slow)
trend_down = not use_ema or (ema_fast < ema_slow and close < ema_slow)
filter_call = (not use_rsi or rsi_val <= rsi_oversold) and (not use_bb or close <= bb_lower) and trend_up and (not use_pinbar or pinbar_call) and (not use_squeeze or not squeeze_active)
filter_put  = (not use_rsi or rsi_val >= rsi_overbought) and (not use_bb or close >= bb_upper) and trend_down and (not use_pinbar or pinbar_put) and (not use_squeeze or not squeeze_active)
bool call_signal = filter_call and not filter_call[1]
bool put_signal  = filter_put  and not filter_put[1]
plot(bb_upper, title="BB Superior", color=color.new(#38bdf8, 50))
plot(bb_lower, title="BB Inferior", color=color.new(#38bdf8, 50))
plot(use_ema ? ema_fast : na, title="EMA Rápida", color=color.new(#f59e0b, 0))
plot(use_ema ? ema_slow : na, title="EMA Lenta", color=color.new(#c084fc, 0))
plotshape(call_signal, title="Señal CALL", style=shape.triangleup, location=location.belowbar, color=#10b981, size=size.small, text="CALL")
plotshape(put_signal, title="Señal PUT", style=shape.triangledown, location=location.abovebar, color=#f43f5e, size=size.small, text="PUT")
`;
    return header + body + buildExecutionFooterV6('genetic_composite', mode);
}

export function generatePineScriptV6(strat, options = {}) {
    const bg = strat.best_genome || strat.params || {};
    const name = strat.name ? strat.name.replace(/[^a-zA-Z0-9\s]/g, '').trim() : 'Estrategia Nexus';
    const sType = detectStrategyType(strat);
    const mode = options.export_mode || options.mode || 'strategy';
    const initialCapital = parseFloat(options.initial_capital) || 1000.0;
    const posSizeUsd = parseFloat(options.pos_size_usd) || 50.0;
    const maxOpenTrades = parseInt(options.max_open_trades) || 1;
    const barsToHold = parseInt(options.bars_to_hold) || parseInt(bg.expiry_candles) || 1;
    const commissionPct = parseFloat(options.commission_pct) || 0.0005;

    const header = buildRiskHeaderV6(`Nexus Quant - ${name}`, mode, initialCapital, posSizeUsd, maxOpenTrades, barsToHold, commissionPct);

    if (sType === 'mean_reversion') return generateMeanReversionPine(bg, mode, header);
    if (sType === 'rsi_extremes') return generateRsiExtremesPine(bg, mode, header);
    if (sType === 'bollinger_bounce') return generateBollingerBouncePine(bg, mode, header);
    if (sType === 'ema_cross') return generateEmaCrossPine(bg, mode, header);
    if (sType === 'volatility_squeeze') return generateVolatilitySqueezePine(bg, mode, header);
    if (sType === 'support_resistance') return generateSupportResistancePine(bg, mode, header);
    if (sType === 'daily_confluence') return generateDailyConfluencePine(bg, mode, header);
    if (sType === 'mtf_tcve') return generateMtfTcvePine(bg, mode, header);
    if (sType === 'deesr') return generateDeesrPine(bg, mode, header);
    if (sType === 'islg_rs') return generateIslgRsPine(bg, mode, header);
    if (sType === 'volatility_squeeze_ml') return generateVolatilitySqueezeMlPine(bg, mode, header);
    if (sType === 'climax_reversal') return generateClimaxReversalPine(bg, mode, header);
    return generateGeneticCompositePine(bg, mode, header);
}

export const generatePineScriptV5 = generatePineScriptV6;

export function generateAIPrompt(strat, options = {}) {
    const bg = strat.best_genome || strat.params || {};
    const name = strat.name ? strat.name.trim() : 'Estrategia Nexus';
    const sType = detectStrategyType(strat);
    const mode = options.export_mode || 'strategy';
    return `Actúa como un Desarrollador Cuantitativo Senior Experto en Pine Script (TradingView v6) y Trading Algorítmico Automatizado.
Genera el bot ejecutable o indicador verificado para la siguiente estrategia:
NOMBRE ESTRATEGIA: ${name} (Tipo: ${sType})
MODO SOLICITADO: ${mode === 'strategy' ? 'Bot Ejecutable (strategy v6 con Probador de Estrategias y gestión de órdenes)' : 'Indicador Visual (indicator v6 con alertas Webhook)'}
DESCRIPCIÓN OPERATIVA EXACTA:
${strat.natural_description || 'Estrategia cuantitativa optimizada con filtrado ortogonal de alta fidelidad.'}
PARÁMETROS OPTIMIZADOS EN BACKTEST:
${JSON.stringify(bg, null, 2)}
CONFIGURACIÓN DE GESTIÓN DE CAPITAL REQUERIDA:
- Capital Inicial: $${options.initial_capital || 1000} USD
- Tamaño de Posición: $${options.pos_size_usd || 50} USD por trade
- Máximo de Operaciones Simultáneas: ${options.max_open_trades || 1}
- Expiración en Velas: ${options.bars_to_hold || 1} velas
REQUISITOS TÉCNICOS DE PINE SCRIPT v6:
1. Declarar //@version=6 al inicio.
2. Usar ${mode === 'strategy' ? 'strategy("...", overlay=true, ...)' : 'indicator("...", overlay=true)'}.
3. Incluir sección comentada en español para gestión de riesgo.
4. Implementar las reglas matemáticas sin lookahead bias.
5. Crear plotshape para señales visuales y alertcondition/alert_message en formato JSON para webhooks.`;
}

export function showToast(message, type = 'info', duration = 3000) {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.style.cssText = 'position: fixed; bottom: 20px; right: 20px; z-index: 9999; display: flex; flex-direction: column; gap: 8px; pointer-events: none;';
        document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = `toast-message toast-${type}`;
    let borderColor = type === 'success' ? 'rgba(16, 185, 129, 0.45)' : (type === 'error' ? 'rgba(244, 63, 94, 0.45)' : 'rgba(56, 189, 248, 0.35)');
    toast.style.cssText = `background: rgba(15, 23, 42, 0.95); color: #ffffff; border: 1.5px solid ${borderColor}; border-radius: 8px; padding: 10px 16px; font-size: 0.82rem; font-family: 'Inter', sans-serif; box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5); display: flex; align-items: center; gap: 8px; opacity: 0; transform: translateY(10px); transition: opacity 180ms ease, transform 180ms ease; pointer-events: auto;`;
    toast.innerHTML = `<span>${message}</span>`;
    container.appendChild(toast);
    requestAnimationFrame(() => { toast.style.opacity = '1'; toast.style.transform = 'translateY(0)'; });
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        setTimeout(() => { if (toast.parentElement) toast.parentElement.removeChild(toast); }, 200);
    }, duration);
}

export function togglePineScriptModal(id) {
    const el = document.getElementById(`pinescript-box-${id}`);
    if (el) el.style.display = el.style.display === 'none' ? 'block' : 'none';
}

export function copyPineScript(id) {
    const txt = document.getElementById(`pinescript-code-${id}`);
    if (txt) {
        navigator.clipboard.writeText(txt.value);
        showToast('✅ Código Pine Script (v6) copiado al portapapeles.', 'success');
    }
}

export function copyAIPrompt(id) {
    const txt = document.getElementById(`ai-prompt-${id}`);
    if (txt) {
        navigator.clipboard.writeText(txt.value);
        showToast('✅ Prompt estructurado para IA copiado al portapapeles.', 'success');
    }
}

export function downloadPineScriptFile(id, stratKey = 'strategy', asset = null, interval = null) {
    const txt = document.getElementById(`pinescript-code-${id}`);
    if (txt) {
        const pair = asset || document.getElementById('pair-selector')?.value || 'BTCUSDT';
        const tf = interval || document.getElementById('interval-selector')?.value || '4h';
        const fileName = `Nexus_${String(stratKey).replace(/[^a-zA-Z0-9_-]/g, '_')}_${String(pair).replace(/[^a-zA-Z0-9_-]/g, '_')}_${String(tf).replace(/[^a-zA-Z0-9_-]/g, '_')}_v6.pine`;
        const blob = new Blob([txt.value], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = fileName;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast('💾 Archivo ' + fileName + ' descargado.', 'success');
    }
}
