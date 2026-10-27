/**
 * stream_service.js - Binance Real-Time WebSocket & Fallback REST Polling Service
 * Provides live kline stream subscriptions, exponential backoff reconnection,
 * resilient fallback polling, and live candlestick chart updates.
 * Nexus Quant Terminal
 */

let liveWs = null;
let livePollTimer = null;
let wsReconnectAttempts = 0;
let wsReconnectTimer = null;

/**
 * Halts live streaming, clears polling timers, gracefully closes WebSocket, and resets badge.
 */
export function stopLiveStream() {
    if (liveWs) {
        try {
            liveWs.onclose = null;
            liveWs.close();
        } catch (e) {
            console.warn('Error closing live WebSocket:', e);
        }
        liveWs = null;
    }
    if (livePollTimer) {
        clearInterval(livePollTimer);
        livePollTimer = null;
    }
    updateLiveBadge(false);
}

/**
 * Updates or toggles live streaming status badge in DOM.
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
 * Updates the current active candle on charts with real-time price tick.
 * @param {Object} updatedCandle 
 */
export function updateLiveCandleInChart(updatedCandle) {
    if (!updatedCandle || !window.candleSeries) return;
    const isBearish = updatedCandle.close < updatedCandle.open;
    const barColor = isBearish ? '#e11d48' : '#10b981';
    try {
        window.candleSeries.update({
            time: updatedCandle.time,
            open: updatedCandle.open,
            high: updatedCandle.high,
            low: updatedCandle.low,
            close: updatedCandle.close,
            color: barColor
        });
        if (window.smartCandleSeries) {
            window.smartCandleSeries.update({
                time: updatedCandle.time,
                open: updatedCandle.open,
                high: updatedCandle.high,
                low: updatedCandle.low,
                close: updatedCandle.close,
                color: barColor
            });
        }
    } catch (e) {
        console.warn('Live candle update warning:', e);
    }
}

/**
 * Schedules exponential backoff reconnection for WebSocket stream.
 * @param {string} pair 
 * @param {string} interval 
 */
export function scheduleWsReconnect(pair, interval) {
    if (wsReconnectAttempts >= 5) {
        startFallbackPolling(pair, interval);
        return;
    }
    wsReconnectAttempts++;
    const delay = Math.min(1000 * Math.pow(2, wsReconnectAttempts), 30000);
    clearTimeout(wsReconnectTimer);
    wsReconnectTimer = setTimeout(() => connectLiveStream(pair, interval), delay);
}

/**
 * Connects to Binance public Kline WebSocket stream with fallback triggers.
 * @param {string} pair 
 * @param {string} interval 
 */
export function connectLiveStream(pair, interval) {
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
                    time: Math.floor(k.t / 1000),
                    open: parseFloat(k.o),
                    high: parseFloat(k.h),
                    low: parseFloat(k.l),
                    close: parseFloat(k.c)
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

/**
 * Fallback polling mechanism: polls Binance REST API for latest klines.
 * @param {string} pair 
 * @param {string} interval 
 */
export function startFallbackPolling(pair, interval) {
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
                    time: Math.floor(k[0] / 1000),
                    open: parseFloat(k[1]),
                    high: parseFloat(k[2]),
                    low: parseFloat(k[3]),
                    close: parseFloat(k[4])
                });
            }
        } catch (e) {
            console.warn('Polling error:', e);
        }
    };
    poll();
    livePollTimer = setInterval(poll, 3000);
}

// Global browser window bindings
if (typeof window !== 'undefined') {
    window.stopLiveStream = stopLiveStream;
    window.updateLiveBadge = updateLiveBadge;
    window.updateLiveCandleInChart = updateLiveCandleInChart;
    window.scheduleWsReconnect = scheduleWsReconnect;
    window.connectLiveStream = connectLiveStream;
    window.startFallbackPolling = startFallbackPolling;
}
