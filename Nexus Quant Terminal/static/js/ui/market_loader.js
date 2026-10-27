/**
 * market_loader.js - Market Data & Strategy Configuration Loader
 * Manages pairs and timeframes metadata, historical and live candle fetching,
 * dynamic strategy parameters rendering, and backtest results summary display.
 * Nexus Quant Terminal
 */

const API = '/api';
let candlesAbortController = null;

/**
 * Formats price numeric value based on asset magnitude.
 * @param {number|string} price 
 * @returns {string} Formatted price string
 */
export function formatPrice(price) {
    if (price === undefined || price === null || isNaN(price)) return '--';
    const p = parseFloat(price);
    return Math.abs(p) < 10 ? p.toFixed(4) : p.toFixed(2);
}

/**
 * Fetches available trading pairs and intervals from backend and populates selectors.
 */
export function loadPairs() {
    return fetch(`${API}/data/pairs`)
        .then(res => res.json())
        .then(data => {
            const pairSel = document.getElementById('pair-selector');
            const intSel = document.getElementById('interval-selector');
            if (!pairSel || !intSel) return;
            
            const currentPair = pairSel.value;
            const currentInt = intSel.value;

            if (data.pairs && data.pairs.length > 0) {
                pairSel.innerHTML = data.pairs.map(p => `<option value="${p}">${p}</option>`).join('');
                if (data.pairs.includes(currentPair)) pairSel.value = currentPair;
            }

            const intervalOrder = { '1d': 1, '4h': 2, '2h': 3, '1h': 4, '30m': 5, '15m': 6, '5m': 7, '3m': 8, '1m': 9 };
            const rawIntervals = data.intervals || ['1d', '4h', '1h', '30m', '15m', '5m', '1m'];
            const sortedIntervals = [...new Set(rawIntervals)].sort(
                (a, b) => (intervalOrder[a] || 99) - (intervalOrder[b] || 99)
            );

            intSel.innerHTML = sortedIntervals.map(i => `<option value="${i}">${i}</option>`).join('');
            if (sortedIntervals.includes(currentInt)) {
                intSel.value = currentInt;
            }

            updatePairTimeframeRestrictions();
        })
        .catch(e => {
            console.error('Error loading pairs:', e);
        });
}

/**
 * Restricts timeframes for non-crypto pairs (Yahoo/Forex) to 1d.
 */
export function updatePairTimeframeRestrictions() {
    const pair = document.getElementById('pair-selector')?.value || 'BTCUSDT';
    const intSel = document.getElementById('interval-selector');
    const sourceSel = document.getElementById('source-selector');
    const isCrypto = pair.endsWith('USDT');

    if (!isCrypto) {
        if (intSel) {
            Array.from(intSel.options).forEach(opt => {
                opt.disabled = opt.value !== '1d';
            });
            if (intSel.value !== '1d') {
                intSel.value = '1d';
            }
        }
        if (sourceSel && sourceSel.value === 'live') {
            sourceSel.value = 'historical';
        }
    } else {
        if (intSel) {
            Array.from(intSel.options).forEach(opt => {
                opt.disabled = false;
            });
        }
    }
}

/**
 * Event handler triggered when user selects a different trading pair.
 */
export function onPairChanged() {
    updatePairTimeframeRestrictions();
    loadCandles();
}

/**
 * Loads candlestick data from either Binance live REST endpoint or backend database.
 */
export async function loadCandles() {
    if (typeof window.stopLiveStream === 'function') {
        window.stopLiveStream();
    }
    updatePairTimeframeRestrictions();

    if (candlesAbortController) {
        try { candlesAbortController.abort(); } catch (e) {}
    }
    candlesAbortController = new AbortController();
    const signal = candlesAbortController.signal;

    const pair = document.getElementById('pair-selector')?.value || 'BTCUSDT';
    const interval = document.getElementById('interval-selector')?.value || '1h';
    const source = document.getElementById('source-selector')?.value || 'historical';
    const loader = document.getElementById('chart-loader');
    if (loader) loader.classList.add('active');

    try {
        let candles = [];
        const safePair = encodeURIComponent(pair);
        const safeInterval = encodeURIComponent(interval);

        if (source === 'live') {
            try {
                const res = await fetch(`https://api.binance.com/api/v3/klines?symbol=${safePair}&interval=${safeInterval}&limit=1000`, { signal });
                if (res.ok) {
                    const data = await res.json();
                    if (Array.isArray(data)) {
                        candles = data.map(c => ({
                            time: Math.floor(c[0] / 1000),
                            open: parseFloat(c[1]),
                            high: parseFloat(c[2]),
                            low: parseFloat(c[3]),
                            close: parseFloat(c[4]),
                            volume: parseFloat(c[5])
                        }));
                    }
                } else {
                    const fallbackRes = await fetch(`${API}/data/candles?pair=${safePair}&interval=${safeInterval}&limit=1000`, { signal });
                    if (fallbackRes.ok) {
                        const fallbackData = await fallbackRes.json();
                        candles = fallbackData.candles || [];
                    }
                }
            } catch (err) {
                if (err.name === 'AbortError') return;
                const fallbackRes = await fetch(`${API}/data/candles?pair=${safePair}&interval=${safeInterval}&limit=1000`, { signal });
                if (fallbackRes.ok) {
                    const fallbackData = await fallbackRes.json();
                    candles = fallbackData.candles || [];
                }
            }
        } else {
            const res = await fetch(`${API}/data/candles?pair=${safePair}&interval=${safeInterval}&limit=1000`, { signal });
            if (res.ok) {
                const data = await res.json();
                candles = data.candles || [];
            }
        }

        const cleanCandles = typeof window.prepareCandles === 'function' ? window.prepareCandles(candles) : candles;
        if (cleanCandles.length > 0) {
            if (window.state) window.state.candles = cleanCandles;
            if (window.candleSeries) {
                window.candleSeries.setData(cleanCandles);
                window.candleSeries.setMarkers([]);
            }
            
            setTimeout(() => {
                const totalBars = cleanCandles.length;
                const visibleBars = Math.min(120, totalBars);
                if (window.mainChart) {
                    window.mainChart.timeScale().setVisibleLogicalRange({
                        from: totalBars - visibleBars,
                        to: totalBars + 5
                    });
                }
            }, 30);
        }

        const activeSource = document.getElementById('source-selector')?.value;
        if (activeSource === 'live' && cleanCandles.length > 0 && typeof window.connectLiveStream === 'function') {
            window.connectLiveStream(pair, interval);
        }
    } catch (e) {
        console.error('Error loading candles:', e);
    }
    if (loader) loader.classList.remove('active');
}

/**
 * Loads available quantitative strategies catalogue from backend.
 */
export async function loadStrategies() {
    try {
        const res = await fetch(`${API}/strategies`);
        const data = await res.json();
        const s = window.state || {};
        s.strategies = data.strategies || [];
        const sel = document.getElementById('strategy-selector');
        if (!sel) return;
        sel.innerHTML = s.strategies.map(st =>
            `<option value="${st.name}">${st.display_name || st.name}</option>`
        ).join('');
        sel.addEventListener('change', () => renderStrategyParams(sel.value));
        if (s.strategies.length > 0) renderStrategyParams(s.strategies[0].name);
    } catch (e) {
        console.error('Error loading strategies:', e);
    }
}

/**
 * Dynamically renders form inputs for strategy hyper-parameters.
 * @param {string} strategyName 
 */
export function renderStrategyParams(strategyName) {
    const s = window.state || {};
    s.selectedStrategy = strategyName;
    const strat = (s.strategies || []).find(st => st.name === strategyName);
    const container = document.getElementById('dynamic-params');
    if (!container) return;
    if (!strat || !strat.params) { container.innerHTML = ''; return; }

    container.innerHTML = strat.params.map(p => {
        if (p.type === 'bool') {
            const isTrue = String(p.default).toLowerCase() === 'true';
            return `
                <div class="control-group">
                    <label for="param-${p.name}">${p.description || p.name}
                        <span class="tooltip">?
                            <span class="tooltip-text">${p.description || p.name} (Booleano: Activo / Inactivo).</span>
                        </span>
                    </label>
                    <select id="param-${p.name}" data-param="${p.name}" data-type="bool" class="form-control">
                        <option value="true" ${isTrue ? 'selected' : ''}>Sí (Activo)</option>
                        <option value="false" ${!isTrue ? 'selected' : ''}>No (Inactivo)</option>
                    </select>
                </div>
            `;
        }

        return `
            <div class="control-group">
                <label for="param-${p.name}">${p.description || p.name}
                    <span class="tooltip">?
                        <span class="tooltip-text">${p.description || p.name} (Rango sugerido: ${p.min !== undefined ? p.min : 'min'} a ${p.max !== undefined ? p.max : 'max'}).</span>
                    </span>
                </label>
                <input type="number" id="param-${p.name}" data-param="${p.name}" data-type="${p.type || 'number'}"
                       value="${p.default}" min="${p.min !== undefined ? p.min : ''}" max="${p.max !== undefined ? p.max : ''}"
                       step="${p.step || (p.type === 'int' ? '1' : 'any')}" required>
            </div>
        `;
    }).join('');
}

/**
 * Initializes linear vs logarithmic scale mode toggles for equity curves.
 */
export function initEquityScaleToggles() {
    const pairs = [
        { canvasId: 'equity-chart', linearId: 'btn-scale-linear', logId: 'btn-scale-log' },
        { canvasId: 'smart-equity-chart-canvas', linearId: 'btn-smart-scale-linear', logId: 'btn-smart-scale-log' }
    ];

    pairs.forEach(({ canvasId, linearId, logId }) => {
        window[canvasId + '_scaleMode'] = 'linear';
        const linearBtn = document.getElementById(linearId);
        const logBtn = document.getElementById(logId);

        if (linearBtn) {
            linearBtn.addEventListener('click', () => {
                linearBtn.classList.add('active');
                if (logBtn) logBtn.classList.remove('active');
                window[canvasId + '_scaleMode'] = 'linear';
                const cached = window[canvasId + '_data'];
                if (cached && cached.equityPoints && typeof window.createEquityCurve === 'function') {
                    window.createEquityCurve(canvasId, cached.equityPoints, cached.rawLabels);
                }
            });
        }

        if (logBtn) {
            logBtn.addEventListener('click', () => {
                logBtn.classList.add('active');
                if (linearBtn) linearBtn.classList.remove('active');
                window[canvasId + '_scaleMode'] = 'log';
                const cached = window[canvasId + '_data'];
                if (cached && cached.equityPoints && typeof window.createEquityCurve === 'function') {
                    window.createEquityCurve(canvasId, cached.equityPoints, cached.rawLabels);
                }
            });
        }
    });
}

/**
 * Displays backtest results summary metrics and trade list.
 * @param {Object} data 
 */
export function displayBacktestResults(data) {
    const s = data.summary || data.stats?.basic || data.stats || {};
    const wr = s.win_rate !== undefined ? s.win_rate : (data.stats?.win_rate !== undefined ? data.stats.win_rate : (data.stats?.basic?.win_rate || 0));
    const st = window.state || {};
    st.lastWinRate = wr;
    if (typeof window.updateCycleProbability === 'function') {
        window.updateCycleProbability();
    }
    
    const winrateEl = document.getElementById('stat-winrate');
    if (winrateEl) winrateEl.textContent = (wr * 100).toFixed(2) + '%';
    
    const tradesEl = document.getElementById('stat-trades');
    if (tradesEl) tradesEl.textContent = s.total_trades || s.total || data.stats?.total_trades || data.stats?.basic?.total_trades || 0;

    const pnl = s.net_pnl !== undefined ? s.net_pnl : (data.stats?.net_pnl !== undefined ? data.stats.net_pnl : (data.stats?.basic?.net_pnl || 0));
    const pnlEl = document.getElementById('stat-pnl');
    if (pnlEl) {
        pnlEl.textContent = (pnl > 0 ? '+' : '') + pnl.toFixed(2);
        pnlEl.className = pnl > 0 ? 'text-green' : 'text-red';
    }

    const maxWin = s.max_win_streak !== undefined ? s.max_win_streak : (data.stats?.max_win_streak !== undefined ? data.stats.max_win_streak : (data.stats?.streaks?.max_win_streak));
    const maxLoss = s.max_loss_streak !== undefined ? s.max_loss_streak : (data.stats?.max_loss_streak !== undefined ? data.stats.max_loss_streak : (data.stats?.streaks?.max_loss_streak));
    const mwEl = document.getElementById('stat-mw');
    if (mwEl) mwEl.textContent = maxWin !== undefined ? maxWin : '--';
    const mlEl = document.getElementById('stat-ml');
    if (mlEl) mlEl.textContent = maxLoss !== undefined ? maxLoss : '--';

    // Equity curve
    if (data.equity_curve && data.equity_curve.length > 0 && typeof window.createEquityCurve === 'function') {
        window.createEquityCurve('equity-chart', data.equity_curve);
    }

    // Trades table (last 100)
    const tbody = document.querySelector('#trades-table tbody');
    if (!tbody) return;
    const trades = (data.trades || []).slice(-100);
    tbody.innerHTML = trades.map((t, idx) => {
        const date = t.time ? new Date(t.time * 1000).toISOString().slice(0, 16).replace('T', ' ') : '--';
        const slStr = t.sl_price ? formatPrice(t.sl_price) : '--';
        const tpStr = t.tp_price ? formatPrice(t.tp_price) : '--';
        const durStr = t.duration !== undefined ? `${t.duration} v` : (t.holding_candles !== undefined ? `${t.holding_candles} v` : '1 v');
        const rStr = t.r_multiple !== undefined ? `${t.r_multiple >= 0 ? '+' : ''}${t.r_multiple.toFixed(2)}R` : '--';
        const exitReason = t.exit_reason || (t.result === 'WIN' ? 'TP' : 'SL');
        const isLong = (t.direction === 'LONG' || t.direction === 'CALL');

        return `<tr data-trade-idx="${idx}" style="cursor: pointer;" title="Haz clic para ver líneas exactas en el gráfico">
            <td>#${trades.length - idx}</td>
            <td>${date}</td>
            <td><span class="badge ${isLong ? 'badge-call' : 'badge-put'}">${isLong ? '▲ LONG' : '▼ SHORT'}</span></td>
            <td style="text-align: right;">${formatPrice(t.entry_price)}</td>
            <td style="text-align: right; color: var(--accent-red);">${slStr}</td>
            <td style="text-align: right; color: var(--accent-green);">${tpStr}</td>
            <td style="text-align: right;">${formatPrice(t.exit_price)}</td>
            <td style="text-align: center;">${durStr}</td>
            <td style="text-align: right; font-weight: 700;" class="${(t.pnl || 0) > 0 ? 'text-green' : ((t.pnl || 0) < 0 ? 'text-red' : '')}">${rStr}</td>
            <td style="text-align: right; font-weight: 700;" class="${(t.pnl || 0) > 0 ? 'text-green' : ((t.pnl || 0) < 0 ? 'text-red' : '')}">${(t.pnl || 0) > 0 ? '+' : ''}${(t.pnl || 0).toFixed(2)}</td>
            <td style="text-align: center;"><span class="badge ${t.result === 'WIN' ? 'badge-win' : (t.result === 'TIE' ? 'badge-tie' : 'badge-loss')}">${exitReason}</span></td>
        </tr>`;
    }).join('');

    tbody.querySelectorAll('tr').forEach(row => {
        row.addEventListener('click', (e) => {
            const idx = parseInt(e.currentTarget.dataset.tradeIdx);
            const trade = trades[idx];
            if (!trade) return;
            tbody.querySelectorAll('tr').forEach(r => r.style.background = 'transparent');
            row.style.background = 'rgba(168, 85, 247, 0.15)';
            if (typeof window.highlightTradeOnChart === 'function') {
                window.highlightTradeOnChart(trade, window.mainChart, window.candleSeries);
            }
        });
    });
}

// Global browser window bindings
if (typeof window !== 'undefined') {
    window.formatPrice = formatPrice;
    window.loadPairs = loadPairs;
    window.updatePairTimeframeRestrictions = updatePairTimeframeRestrictions;
    window.onPairChanged = onPairChanged;
    window.loadCandles = loadCandles;
    window.loadStrategies = loadStrategies;
    window.renderStrategyParams = renderStrategyParams;
    window.initEquityScaleToggles = initEquityScaleToggles;
    window.displayBacktestResults = displayBacktestResults;
}
