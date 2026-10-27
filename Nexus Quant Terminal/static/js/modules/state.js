/**
 * state.js - BinSim Central Reactive State Management Module
 * Manages active tabs, candle buffer (1500 limit FIFO), backtest/optimizer state,
 * and SSE streams across the application.
 */

export const state = {
    currentTab: 'dashboard',
    candles: [],
    strategies: [],
    backtestResults: null,
    optimizerResults: null,
    selectedStrategy: null,
    lastWinRate: 0.5,
    currentBacktestData: null,
    loadedBacktestId: null,
    activeEventSource: null
};

// Listeners for reactive updates
const listeners = new Set();

/**
 * Returns current state snapshot
 */
export function getState() {
    return state;
}

/**
 * Updates partial state and notifies registered listeners
 * @param {Object} partialState 
 */
export function setState(partialState) {
    if (!partialState || typeof partialState !== 'object') return;
    Object.assign(state, partialState);
    notifyListeners();
}

/**
 * Resets state back to initial default configuration
 */
export function resetState() {
    state.currentTab = 'dashboard';
    state.candles = [];
    state.strategies = [];
    state.backtestResults = null;
    state.optimizerResults = null;
    state.selectedStrategy = null;
    state.lastWinRate = 0.5;
    state.currentBacktestData = null;
    state.loadedBacktestId = null;
    if (state.activeEventSource) {
        try { state.activeEventSource.close(); } catch (e) {}
        state.activeEventSource = null;
    }
    notifyListeners();
}

/**
 * Subscribes a callback to state mutation events
 * @param {Function} listener 
 * @returns {Function} unsubscribe function
 */
export function subscribe(listener) {
    if (typeof listener === 'function') {
        listeners.add(listener);
        return () => listeners.delete(listener);
    }
    return () => {};
}

function notifyListeners() {
    listeners.forEach(fn => {
        try {
            fn(state);
        } catch (e) {
            console.error('[State] Error executing listener:', e);
        }
    });
}

/**
 * Safely replaces candle buffer with max 1500 limit
 * @param {Array} newCandles 
 * @param {number} maxLimit 
 */
export function setCandles(newCandles, maxLimit = 1500) {
    if (!Array.isArray(newCandles)) {
        state.candles = [];
    } else if (newCandles.length > maxLimit) {
        state.candles = newCandles.slice(newCandles.length - maxLimit);
    } else {
        state.candles = [...newCandles];
    }
    notifyListeners();
}

/**
 * Appends a new candle enforcing FIFO eviction at 1500 candles
 * @param {Object} candle 
 * @param {number} maxLimit 
 */
export function appendCandle(candle, maxLimit = 1500) {
    if (!candle) return;
    state.candles.push(candle);
    while (state.candles.length > maxLimit) {
        state.candles.shift();
    }
    notifyListeners();
}

/**
 * Updates the last candle in buffer or appends if time is greater
 * @param {Object} candle 
 * @param {number} maxLimit 
 */
export function updateLastCandle(candle, maxLimit = 1500) {
    if (!candle || isNaN(candle.time)) return;
    if (state.candles.length === 0) {
        state.candles.push(candle);
    } else {
        const lastCandle = state.candles[state.candles.length - 1];
        if (candle.time === lastCandle.time) {
            state.candles[state.candles.length - 1] = candle;
        } else if (candle.time > lastCandle.time) {
            appendCandle(candle, maxLimit);
        }
    }
}

/**
 * Gets active tab
 */
export function getActiveTab() {
    return state.currentTab;
}

/**
 * Sets active tab
 * @param {string} tabId 
 */
export function setActiveTab(tabId) {
    state.currentTab = tabId;
    notifyListeners();
}

/**
 * Sets and tracks active SSE EventSource
 * @param {EventSource|null} es 
 */
export function setActiveEventSource(es) {
    if (state.activeEventSource && state.activeEventSource !== es) {
        try { state.activeEventSource.close(); } catch (e) {}
    }
    state.activeEventSource = es;
    window.activeEventSource = es;
}

/**
 * Closes and clears active SSE EventSource
 */
export function closeActiveEventSource() {
    if (state.activeEventSource) {
        try { state.activeEventSource.close(); } catch (e) {}
        state.activeEventSource = null;
    }
    if (window.activeEventSource) {
        try { window.activeEventSource.close(); } catch (e) {}
        window.activeEventSource = null;
    }
}

// Global browser bridge compatibility
if (typeof window !== 'undefined') {
    window.BinSimModules = window.BinSimModules || {};
    window.BinSimModules.state = {
        state,
        getState,
        setState,
        resetState,
        subscribe,
        setCandles,
        appendCandle,
        updateLastCandle,
        getActiveTab,
        setActiveTab,
        setActiveEventSource,
        closeActiveEventSource
    };
    if (!window.state) {
        window.state = state;
    }
}

export default state;
