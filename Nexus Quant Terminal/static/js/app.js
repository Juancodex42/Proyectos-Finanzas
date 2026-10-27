/**
 * app.js - Nexus Quant Terminal Main Application Hub & Orchestrator
 * Modularized ES6 coordinator connecting UI managers, streaming services, and quantitative controllers.
 * Line budget constraint: strictly < 450 lines.
 */

import { loadPairs, loadStrategies, loadCandles, onPairChanged, initEquityScaleToggles, formatPrice, renderStrategyParams, displayBacktestResults } from './ui/market_loader.js';
import { getHistory, getSaved, saveCurrentBacktest, clearHistory, loadBacktestState } from './ui/history_manager.js';
import { renderResultsLists } from './ui/history_renderer.js';
import { runBacktest, runGeneticOptimizer, initBacktestController } from './controllers/backtest_controller.js';
import { runSmartOptimization, initSmartModePresets } from './modules/smart_mode.js';
import { runStreakPlanner, updateCycleProbability } from './modules/calculators.js';
import { generatePineScriptV6, generatePineScriptV5, generateAIPrompt, detectStrategyType } from './modules/modals/export_modal.js';

const state = {
    strategies: [], selectedStrategy: null, candles: [], backtestResults: null,
    lastWinRate: null, currentBacktestData: null, loadedBacktestId: null
};
window.state = state;

let mainChart, candleSeries;
let smartChart, smartCandleSeries;

function showToast(message, type = 'info', duration = 3000) {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
        toast.classList.add('toast-exit');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

window.togglePineScriptModal = () => {
    const modal = document.getElementById('pine-modal');
    if (modal) modal.classList.toggle('active');
};
window.copyPineScript = async () => {
    const code = document.getElementById('pine-code')?.innerText || '';
    if (navigator.clipboard) {
        await navigator.clipboard.writeText(code);
        showToast('✅ Código Pine Script (v6) copiado al portapapeles.', 'success');
    }
};
window.copyAIPrompt = async () => {
    const prompt = document.getElementById('ai-prompt-code')?.innerText || '';
    if (navigator.clipboard) {
        await navigator.clipboard.writeText(prompt);
        showToast('✅ Prompt estructurado para IA copiado al portapapeles.', 'success');
    }
};

let liveWs = null;
let livePollTimer = null;
let wsReconnectAttempts = 0;
let wsReconnectTimer = null;

function stopLiveStream() {
    if (liveWs) {
        liveWs.onclose = null;
        liveWs.close();
        liveWs = null;
    }
    if (livePollTimer) {
        clearInterval(livePollTimer);
        livePollTimer = null;
    }
    updateLiveBadge(false);
}

function updateLiveBadge(active, text = 'En Vivo') {
    const badge = document.getElementById('live-badge');
    const badgeText = document.getElementById('live-badge-text');
    if (!badge) return;
    if (active) {
        badge.style.display = 'inline-flex';
        if (badgeText) badgeText.textContent = text;
    } else {
        badge.style.display = 'none';
    }
}

function updateLiveCandleInChart(updatedCandle) {
    if (!updatedCandle || !candleSeries) return;
    const isBearish = updatedCandle.close < updatedCandle.open;
    try {
        candleSeries.update({
            time: updatedCandle.time, open: updatedCandle.open,
            high: updatedCandle.high, low: updatedCandle.low,
            close: updatedCandle.close, color: isBearish ? '#e11d48' : '#10b981'
        });
    } catch (e) {
        console.warn('Candle update warning:', e);
    }
}

function scheduleWsReconnect(pair, interval) {
    if (wsReconnectAttempts >= 5) {
        startFallbackPolling(pair, interval);
        return;
    }
    wsReconnectAttempts++;
    const delay = Math.min(1000 * Math.pow(2, wsReconnectAttempts), 30000);
    clearTimeout(wsReconnectTimer);
    wsReconnectTimer = setTimeout(() => connectLiveStream(pair, interval), delay);
}

function connectLiveStream(pair, interval) {
    stopLiveStream();
    const wsUrl = `wss://stream.binance.com:9443/ws/${pair.toLowerCase()}@kline_${interval}`;
    try {
        liveWs = new WebSocket(wsUrl);
        liveWs.onopen = () => {
            wsReconnectAttempts = 0;
            updateLiveBadge(true, 'En Vivo (WS)');
        };
        liveWs.onmessage = (evt) => {
            const data = JSON.parse(evt.data);
            if (data.k) {
                const k = data.k;
                const candle = {
                    time: Math.floor(k.t / 1000), open: parseFloat(k.o),
                    high: parseFloat(k.h), low: parseFloat(k.l), close: parseFloat(k.c)
                };
                updateLiveCandleInChart(candle);
            }
        };
        liveWs.onerror = (err) => {
            console.warn('Live WS error, fallback to polling:', err);
            startFallbackPolling(pair, interval);
        };
        liveWs.onclose = (evt) => {
            console.warn('Live WS closed, fallback to polling:', evt);
            startFallbackPolling(pair, interval);
        };
    } catch (e) {
        console.warn('WS instantiate error:', e);
        startFallbackPolling(pair, interval);
    }
}

function startFallbackPolling(pair, interval) {
    stopLiveStream();
    updateLiveBadge(true, 'En Vivo (Polling)');
    const poll = async () => {
        try {
            const res = await fetch(`https://api.binance.com/api/v3/klines?symbol=${pair}&interval=${interval}&limit=2`);
            if (!res.ok) return;
            const data = await res.json();
            if (data && data.length > 0) {
                const k = data[data.length - 1];
                updateLiveCandleInChart({
                    time: Math.floor(k[0] / 1000), open: parseFloat(k[1]),
                    high: parseFloat(k[2]), low: parseFloat(k[3]), close: parseFloat(k[4])
                });
            }
        } catch (e) {
            console.warn('Polling error:', e);
        }
    };
    poll();
    livePollTimer = setInterval(poll, 3000);
}

function buildChartMarkers(signals) {
    if (!signals || signals.length === 0) return [];
    const sorted = [...signals].sort((a, b) => a.time - b.time);
    const markers = [];
    const seenKeys = new Set();
    sorted.forEach(s => {
        if (!s || !s.time) return;
        const key = `${s.time}_${s.direction}_${s.result || ''}`;
        if (seenKeys.has(key)) return;
        seenKeys.add(key);
        const priceStr = s.entry_price ? ` @ ${formatPrice(s.entry_price)}` : '';
        const exitPriceStr = s.exit_price ? ` @ ${formatPrice(s.exit_price)}` : '';
        const pnlStr = (s.pnl !== undefined && s.pnl !== null) ? ` (${s.pnl >= 0 ? '+' : ''}${s.pnl.toFixed(2)}$)` : '';

        if (s.direction === 'CALL' || s.direction === 'LONG') {
            markers.push({
                time: s.time, position: 'belowBar', color: '#10b981', shape: 'arrowUp', text: `${s.direction}${priceStr}`
            });
        } else if (s.direction === 'PUT' || s.direction === 'SHORT') {
            markers.push({
                time: s.time, position: 'aboveBar', color: '#e11d48', shape: 'arrowDown', text: `${s.direction}${priceStr}`
            });
        } else if (s.direction === 'EXIT') {
            const isWin = s.result === 'WIN';
            const tradeDir = s.trade_direction || 'CALL';
            const exitPos = (tradeDir === 'CALL' || tradeDir === 'LONG') ? (isWin ? 'aboveBar' : 'belowBar') : (isWin ? 'belowBar' : 'aboveBar');
            markers.push({
                time: s.time, position: exitPos, color: isWin ? '#10b981' : '#e11d48',
                shape: 'circle', text: isWin ? `WIN${exitPriceStr}${pnlStr}` : `LOSS${exitPriceStr}${pnlStr}`
            });
        }
    });
    return markers;
}

function prepareCandles(candles) {
    if (!Array.isArray(candles) || candles.length === 0) return [];
    const sorted = [...candles].sort((a, b) => a.time - b.time);
    const clean = [];
    let lastTime = -1;
    sorted.forEach(c => {
        if (c.time > lastTime) {
            const isBearish = c.close < c.open;
            clean.push({
                time: c.time, open: c.open, high: c.high, low: c.low, close: c.close,
                color: isBearish ? '#e11d48' : '#10b981'
            });
            lastTime = c.time;
        }
    });
    return clean;
}

function switchTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabId);
    });
    document.querySelectorAll('.tab-content').forEach(c => {
        c.classList.remove('active');
        if (c.id === tabId) {
            c.classList.add('active');
        }
    });
    const targetChart = tabId === 'smart-dashboard' ? smartChart : mainChart;
    const el = document.getElementById(tabId === 'smart-dashboard' ? 'smart-tv-chart' : 'tv-chart');
    if (el && targetChart && typeof targetChart.applyOptions === 'function') {
        targetChart.applyOptions({ width: el.clientWidth, height: el.clientHeight });
    }
    if (tabId === 'smart-dashboard' && typeof createCorrelationHeatmap === 'function') {
        createCorrelationHeatmap('smart-correlation-canvas', window._corrMatrix || [], window._corrLabels || []);
    }
}

let activeChartPriceLines = [];
function highlightTradeOnChart(trade, mainChart, candleSeries) {
    if (!trade || !mainChart || !candleSeries) return;
    activeChartPriceLines.forEach(pl => {
        try { candleSeries.removePriceLine(pl); } catch (e) {}
    });
    activeChartPriceLines = [];
    if (trade.entry_price) {
        const entryLine = candleSeries.createPriceLine({
            price: trade.entry_price,
            color: trade.direction === 'CALL' ? '#10b981' : '#e11d48',
            lineWidth: 2, lineStyle: 0, axisLabelVisible: true, title: `ENTRY ${trade.direction}`
        });
        activeChartPriceLines.push(entryLine);
    }
    if (trade.exit_price) {
        const exitLine = candleSeries.createPriceLine({
            price: trade.exit_price,
            color: trade.result === 'WIN' ? '#10b981' : '#e11d48',
            lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: `EXIT ${trade.result}`
        });
        activeChartPriceLines.push(exitLine);
    }
}

function displayStatistics(stats) {
    if (!stats) return;
    const ac = stats.dependency?.autocorrelation || [];
    if (ac.length > 0 && typeof createBarChart === 'function') {
        createBarChart('autocorr-chart', ac.map((_, i) => `Lag ${i + 1}`), ac, 'Autocorrelación', ac.map(v => v >= 0 ? '#a855f7' : '#e11d48'));
    }
    const sd = stats.streaks?.streak_distribution || {};
    if (Object.keys(sd).length > 0 && typeof createBarChart === 'function') {
        const sorted = Object.keys(sd).map(Number).sort((a, b) => a - b);
        createBarChart('streaks-chart', sorted.map(String), sorted.map(k => sd[k]), 'Frecuencia de Rachas', '#f59e0b');
    }
    const bh = stats.temporal?.by_hour || {};
    if (Object.keys(bh).length > 0 && typeof createBarChart === 'function') {
        const hours = Object.keys(bh).map(Number).sort((a, b) => a - b);
        const values = hours.map(h => bh[h]);
        const colors = values.map(wr => (wr > 1 ? wr : wr * 100) >= 58.8 ? '#10b981' : ((wr > 1 ? wr : wr * 100) >= 50.0 ? '#06b6d4' : '#e11d48'));
        createBarChart('hourly-chart', hours.map(h => h + 'h'), values, 'Win Rate por Hora', colors);
    }
    const dep = stats.dependency || {};
    const condEl = document.getElementById('cond-probs');
    if (condEl) {
        condEl.innerHTML = `<div><span>P(W|W)</span><strong class="text-green">${((dep.p_win_given_win || 0) * 100).toFixed(1)}%</strong></div>` +
            `<div><span>P(W|L)</span><strong>${((dep.p_win_given_loss || 0) * 100).toFixed(1)}%</strong></div>` +
            `<div><span>P(L|W)</span><strong>${((dep.p_loss_given_win || 0) * 100).toFixed(1)}%</strong></div>` +
            `<div><span>P(L|L)</span><strong class="text-red">${((dep.p_loss_given_loss || 0) * 100).toFixed(1)}%</strong></div>`;
    }
    const ms = stats.market_state || {};
    if (Object.values(ms).some(v => v > 0) && typeof createBarChart === 'function') {
        createBarChart('market-state-chart', ['Alta Vol', 'Baja Vol', 'Tendencia', 'Rango'], [ms.high_vol_wr || 0, ms.low_vol_wr || 0, ms.trending_wr || 0, ms.ranging_wr || 0], 'Win Rate por Régimen', ['#f59e0b', '#06b6d4', '#10b981', '#a855f7']);
    }
    const mt = stats.markov?.transition_matrix || [];
    const tbl = document.getElementById('markov-table');
    if (tbl && mt.length > 0) {
        let html = '<thead><tr><th>Si el anterior fue...</th><th>Siguiente: Win</th><th>Siguiente: Loss</th></tr></thead><tbody>';
        const labels = ['Win', 'Loss'];
        mt.forEach((row, i) => {
            html += `<tr><td><strong>${labels[i] || i}</strong></td>`;
            (row || []).forEach(v => { html += `<td>${(v * 100).toFixed(1)}%</td>`; });
            html += '</tr>';
        });
        tbl.innerHTML = html + '</tbody>';
    }
}

const INTERACTIVE_DOM_IDS = [
    "mode-smart", "mode-advanced", "live-badge", "live-badge-text", "btn-smart-run", "smart-preset-select", "smart-streak-length", "smart-base-capital",
    "smart-profit-pct", "smart-risk-capital", "smart-attempts", "smart-payout", "smart-generations", "smart-population", "smart-console-box",
    "smart-progress-bar-fill", "smart-console-logs", "smart-top-5-box", "smart-top-5-list", "smart-rec-content", "smart-ladder-content",
    "smart-correlation-canvas", "smart-selected-assets-body", "smart-equity-chart-canvas", "smart-mc-chart-canvas", "smart-asset-selector",
    "smart-tv-chart", "smart-tv-chart-empty", "smart-markov-table", "smart-markov-explanation", "pair-selector", "interval-selector",
    "source-selector", "tv-chart", "chart-loader", "backtest-form", "strategy-selector", "dynamic-params", "expiry-candles", "payout",
    "backtest-n-consecutive", "backtest-cycle-prob", "backtest-bet-fraction", "gen-generations", "gen-population", "gen-min-trades",
    "optimize-genetic-btn", "genetic-progress-fill", "genetic-progress-text", "genetic-progress-eta", "genetic-feedback", "run-backtest-btn",
    "save-backtest-btn", "backtest-progress-fill", "backtest-progress-text", "backtest-progress-eta", "stat-winrate", "stat-trades",
    "stat-pnl", "stat-mw", "stat-ml", "equity-chart", "trades-table", "btn-clear-history", "history-list", "saved-list", "autocorr-chart",
    "streaks-chart", "hourly-chart", "cond-probs", "market-state-chart", "markov-table", "opt-winrate", "opt-payout", "opt-base-capital",
    "opt-profit-pct", "opt-risk-capital", "opt-target-capital", "opt-attempts", "btn-calc-streak", "streak-progress-fill", "streak-progress-text",
    "streak-progress-eta", "streak-recommendation-content", "bet-ladder-container", "streak-alternatives-table", "mc-chart"
];

async function initApp() {
    INTERACTIVE_DOM_IDS.forEach(id => {
        const el = document.getElementById(id);
        if (!el) {
            const queryEl = document.querySelector(`#${id}`);
            if (queryEl) return;
        }
    });

    if (typeof createCandlestickChart === 'function') {
        const lw = createCandlestickChart('tv-chart');
        if (lw) {
            mainChart = lw.chart;
            candleSeries = lw.series;
            window.mainChart = mainChart;
            window.candleSeries = candleSeries;
        }
        const slw = createCandlestickChart('smart-tv-chart');
        if (slw) {
            smartChart = slw.chart;
            smartCandleSeries = slw.series;
            window.smartChart = smartChart;
            window.smartCandleSeries = smartCandleSeries;
        }
    }

    const btnSmart = document.getElementById('mode-smart');
    const btnAdv = document.getElementById('mode-advanced');
    if (btnSmart) {
        btnSmart.addEventListener('click', () => {
            btnSmart.classList.add('active');
            if (btnAdv) btnAdv.classList.remove('active');
            switchTab('smart-dashboard');
        });
    }
    if (btnAdv) {
        btnAdv.addEventListener('click', () => {
            btnAdv.classList.add('active');
            if (btnSmart) btnSmart.classList.remove('active');
            switchTab('dashboard');
        });
    }

    document.getElementById('btn-smart-run')?.addEventListener('click', runSmartOptimization);
    document.getElementById('run-backtest-btn')?.addEventListener('click', runBacktest);
    document.getElementById('save-backtest-btn')?.addEventListener('click', saveCurrentBacktest);
    document.getElementById('optimize-genetic-btn')?.addEventListener('click', runGeneticOptimizer);
    document.getElementById('btn-clear-history')?.addEventListener('click', clearHistory);
    document.getElementById('btn-calc-streak')?.addEventListener('click', runStreakPlanner);

    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const tabId = e.currentTarget.dataset.tab;
            if (tabId) switchTab(tabId);
        });
    });

    document.getElementById('pair-selector')?.addEventListener('change', onPairChanged);
    document.getElementById('interval-selector')?.addEventListener('change', onPairChanged);
    document.getElementById('source-selector')?.addEventListener('change', onPairChanged);
    document.getElementById('backtest-form')?.addEventListener('submit', runBacktest);

    initEquityScaleToggles();
    initSmartModePresets();
    initBacktestController();
    await loadPairs();
    await loadStrategies();
    await loadCandles();
    renderResultsLists();
}

window.buildChartMarkers = buildChartMarkers;
window.prepareCandles = prepareCandles;
window.switchTab = switchTab;
window.highlightTradeOnChart = highlightTradeOnChart;
window.displayStatistics = displayStatistics;
window.showToast = showToast;
window.connectLiveStream = connectLiveStream;
window.stopLiveStream = stopLiveStream;
window.startFallbackPolling = startFallbackPolling;
window.updateLiveBadge = updateLiveBadge;
window.updateLiveCandleInChart = updateLiveCandleInChart;
window.scheduleWsReconnect = scheduleWsReconnect;
window.initApp = initApp;

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}
