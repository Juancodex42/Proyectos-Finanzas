/**
 * websocket.js - Binance WebSocket Real-Time Stream & Fallback Polling Module
 * Provides exponential backoff reconnection, 1500-candle FIFO retention,
 * seamless REST polling fallback, and high-DPI live candlestick rendering.
 */

import { state, appendCandle } from './state.js';

let liveWs = null;
let livePollTimer = null;
let wsReconnectAttempts = 0;
let wsReconnectTimer = null;

/**
 * Halts live streaming, clears timers, closes WebSocket gracefully, and hides live badge.
 */
export function stopLiveStream() {
    if (liveWs) {
        try {
            liveWs.onclose = null;
            liveWs.close();
        } catch (e) {}
        liveWs = null;
    }
    if (livePollTimer) {
        clearInterval(livePollTimer);
        livePollTimer = null;
    }
    updateLiveBadge(false);
}

/**
 * Toggles and updates the live status badge in DOM
 * @param {boolean} active 
 * @param {string} text 
 */
export function updateLiveBadge(active, text = 'En Vivo') {
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

/**
 * Updates the latest live candle across in-memory state and chart instances
 * Enforces 1500-candle FIFO limitation.
 * @param {Object} updatedCandle 
 */
export function updateLiveCandleInChart(updatedCandle) {
    if (!updatedCandle || isNaN(updatedCandle.time) || isNaN(updatedCandle.close)) return;

    const candleBuffer = state.candles;
    if (candleBuffer && candleBuffer.length > 0) {
        const lastCandle = candleBuffer[candleBuffer.length - 1];
        if (updatedCandle.time >= lastCandle.time) {
            const prevClose = candleBuffer.length > 1 ? candleBuffer[candleBuffer.length - 2].close : updatedCandle.open;
            let isBearish = false;
            if (updatedCandle.close < updatedCandle.open) {
                isBearish = true;
            } else if (updatedCandle.close === updatedCandle.open && updatedCandle.close < prevClose) {
                isBearish = true;
            }

            const barColor = isBearish ? '#e11d48' : (updatedCandle.close > updatedCandle.open || updatedCandle.close > prevClose ? '#10b981' : '#94a3b8');
            const candleWithColor = {
                ...updatedCandle,
                color: barColor,
                wickColor: barColor,
                borderColor: barColor
            };

            if (updatedCandle.time === lastCandle.time) {
                candleBuffer[candleBuffer.length - 1] = candleWithColor;
            } else {
                candleBuffer.push(candleWithColor);
                if (candleBuffer.length > 1500) {
                    candleBuffer.shift();
                }
            }

            try {
                if (window.candleSeries) window.candleSeries.update(candleWithColor);
                if (window.smartCandleSeries) window.smartCandleSeries.update(candleWithColor);
            } catch (err) {
                console.warn('[Chart] Error actualizando vela en vivo:', err);
            }
            const displayPrice = updatedCandle.close < 1 ? updatedCandle.close.toFixed(5) : updatedCandle.close.toFixed(2);
            updateLiveBadge(true, `En Vivo: $${displayPrice}`);
        }
    }
}

/**
 * Schedules exponential backoff reconnection for WebSocket
 * @param {string} pair 
 * @param {string} interval 
 */
export function scheduleWsReconnect(pair, interval) {
    if (wsReconnectTimer) clearTimeout(wsReconnectTimer);
    const delay = Math.min(30000, 1000 * Math.pow(2, wsReconnectAttempts));
    wsReconnectAttempts++;
    wsReconnectTimer = setTimeout(() => {
        const currentSource = document.getElementById('source-selector')?.value;
        if (currentSource === 'live') {
            console.log(`[Binance WS] Intentando reconectar WebSocket (intento ${wsReconnectAttempts}, delay ${delay}ms)...`);
            connectLiveStream(pair, interval);
        }
    }, delay);
}

/**
 * Initiates live WebSocket connection to Binance kline stream
 * Falls back to REST polling on error, close, or exception.
 * @param {string} pair 
 * @param {string} interval 
 */
export function connectLiveStream(pair, interval) {
    if (liveWs) {
        liveWs.close();
        liveWs = null;
    }
    if (livePollTimer) {
        clearInterval(livePollTimer);
        livePollTimer = null;
    }

    const streamPair = pair.toLowerCase();
    const wsUrl = `wss://stream.binance.com:9443/ws/${streamPair}@kline_${interval}`;

    try {
        liveWs = new WebSocket(wsUrl);

        liveWs.onopen = () => {
            console.log(`[Binance WS] Conectado a ${streamPair}@kline_${interval}`);
            wsReconnectAttempts = 0;
            if (wsReconnectTimer) { clearTimeout(wsReconnectTimer); wsReconnectTimer = null; }
            if (livePollTimer) { clearInterval(livePollTimer); livePollTimer = null; }
            updateLiveBadge(true, 'En Vivo (Binance WS)');
        };

        liveWs.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                if (msg.e === 'kline' && msg.k) {
                    const k = msg.k;
                    const candleTime = Math.floor(k.t / 1000);
                    const updatedCandle = {
                        time: candleTime,
                        open: parseFloat(k.o),
                        high: parseFloat(k.h),
                        low: parseFloat(k.l),
                        close: parseFloat(k.c),
                        volume: parseFloat(k.v)
                    };
                    updateLiveCandleInChart(updatedCandle);
                }
            } catch (err) {
                console.error('[Binance WS] Error procesando mensaje:', err);
            }
        };

        liveWs.onerror = (err) => {
            console.warn('[Binance WS] Error en WebSocket, usando polling y programando reconexión:', err);
            startFallbackPolling(pair, interval);
            scheduleWsReconnect(pair, interval);
        };

        liveWs.onclose = (evt) => {
            const currentSource = document.getElementById('source-selector')?.value;
            if (currentSource === 'live') {
                startFallbackPolling(pair, interval);
                scheduleWsReconnect(pair, interval);
            } else {
                updateLiveBadge(false);
            }
        };
    } catch (e) {
        console.error('[Binance WS] Error al instanciar WebSocket:', e);
        startFallbackPolling(pair, interval);
        scheduleWsReconnect(pair, interval);
    }
}

/**
 * Fallback polling mechanism: queries Binance REST API every 3s
 * @param {string} pair 
 * @param {string} interval 
 */
export function startFallbackPolling(pair, interval) {
    if (livePollTimer) clearInterval(livePollTimer);
    updateLiveBadge(true, 'En Vivo (Polling)');

    livePollTimer = setInterval(async () => {
        const source = document.getElementById('source-selector')?.value;
        if (source !== 'live') {
            clearInterval(livePollTimer);
            livePollTimer = null;
            updateLiveBadge(false);
            return;
        }

        try {
            const res = await fetch(`https://api.binance.com/api/v3/klines?symbol=${pair}&interval=${interval}&limit=2`);
            if (!res.ok) return;
            const data = await res.json();
            if (Array.isArray(data) && data.length > 0) {
                const latest = data[data.length - 1];
                const updatedCandle = {
                    time: Math.floor(latest[0] / 1000),
                    open: parseFloat(latest[1]),
                    high: parseFloat(latest[2]),
                    low: parseFloat(latest[3]),
                    close: parseFloat(latest[4]),
                    volume: parseFloat(latest[5])
                };
                updateLiveCandleInChart(updatedCandle);
            }
        } catch (e) {
            console.error('Error polling Binance live klines:', e);
        }
    }, 3000);
}

// Global browser bridge compatibility
if (typeof window !== 'undefined') {
    window.BinSimModules = window.BinSimModules || {};
    window.BinSimModules.websocket = {
        stopLiveStream,
        updateLiveBadge,
        updateLiveCandleInChart,
        scheduleWsReconnect,
        connectLiveStream,
        startFallbackPolling
    };
    window.connectLiveStream = connectLiveStream;
    window.stopLiveStream = stopLiveStream;
    window.startFallbackPolling = startFallbackPolling;
    window.updateLiveBadge = updateLiveBadge;
    window.updateLiveCandleInChart = updateLiveCandleInChart;
    window.scheduleWsReconnect = scheduleWsReconnect;
}
