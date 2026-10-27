/**
 * history_manager.js - Backtest & Campaign Persistence Manager
 * Manages localStorage synchronization for backtest history and saved favorites,
 * backtest state rehydration, and chart/form inputs restoration.
 * Nexus Quant Terminal
 */

import { renderResultsLists } from './history_renderer.js';

/**
 * Retrieves backtest history from localStorage.
 * @returns {Array} List of backtest objects
 */
export function getHistory() {
    try {
        return JSON.parse(localStorage.getItem('binsim_history')) || [];
    } catch (e) {
        return [];
    }
}

/**
 * Persists backtest history array to localStorage.
 * @param {Array} history 
 */
export function setHistory(history) {
    localStorage.setItem('binsim_history', JSON.stringify(history));
}

/**
 * Retrieves saved favorite backtests from localStorage.
 * @returns {Array} List of saved backtest objects
 */
export function getSaved() {
    try {
        return JSON.parse(localStorage.getItem('binsim_saved')) || [];
    } catch (e) {
        return [];
    }
}

/**
 * Persists saved favorite backtests array to localStorage.
 * @param {Array} saved 
 */
export function setSaved(saved) {
    localStorage.setItem('binsim_saved', JSON.stringify(saved));
}

/**
 * Updates a backtest entry in both history and saved storage.
 * @param {Object} backtestObj 
 */
export function updatePersistedBacktest(backtestObj) {
    let history = getHistory();
    let idx = history.findIndex(x => x.id === backtestObj.id);
    if (idx !== -1) {
        history[idx] = backtestObj;
        setHistory(history);
    }
    
    let saved = getSaved();
    idx = saved.findIndex(x => x.id === backtestObj.id);
    if (idx !== -1) {
        saved[idx] = backtestObj;
        setSaved(saved);
    }
    renderResultsLists();
}

/**
 * Saves current active backtest into saved favorites list.
 */
export function saveCurrentBacktest() {
    const s = window.state || {};
    if (!s.currentBacktestData) return;
    
    const saved = getSaved();
    if (saved.some(x => x.id === s.currentBacktestData.id)) {
        alert('Este backtest ya está en favoritos.');
        return;
    }
    
    saved.unshift(s.currentBacktestData);
    setSaved(saved);
    
    const saveBtn = document.getElementById('save-backtest-btn');
    if (saveBtn) {
        saveBtn.textContent = '¡Guardado!';
        saveBtn.disabled = true;
    }
    
    renderResultsLists();
}

/**
 * Saves a specific backtest item by ID into saved favorites list.
 * @param {string} id 
 */
export function saveBacktestById(id) {
    const history = getHistory();
    const item = history.find(x => x.id === id);
    if (!item) return;
    
    const saved = getSaved();
    if (saved.some(x => x.id === id)) {
        alert('Este backtest ya está en favoritos.');
        return;
    }
    
    saved.unshift(item);
    setSaved(saved);
    renderResultsLists();
}

/**
 * Deletes a backtest entry by ID from history or saved storage.
 * @param {string} id 
 * @param {string} type - 'history' | 'saved'
 */
export function deleteBacktestById(id, type) {
    if (type === 'history') {
        const history = getHistory().filter(x => x.id !== id);
        setHistory(history);
    } else {
        const saved = getSaved().filter(x => x.id !== id);
        setSaved(saved);
    }
    
    const s = window.state || {};
    if (s.loadedBacktestId === id) {
        s.loadedBacktestId = null;
        s.currentBacktestData = null;
    }
    
    renderResultsLists();
}

/**
 * Clears all backtest history after confirmation.
 */
export function clearHistory() {
    if (confirm('¿Seguro que deseas limpiar todo el historial de backtests?')) {
        setHistory([]);
        renderResultsLists();
    }
}

/**
 * Rehydrates backtest state into inputs, stats cards, and charts.
 * @param {Object} backtestObj 
 */
export function loadBacktestState(backtestObj) {
    const s = window.state || {};
    s.loadedBacktestId = backtestObj.id;
    s.currentBacktestData = backtestObj;
    
    const btnAdvanced = document.getElementById('mode-advanced');
    if (btnAdvanced && !btnAdvanced.classList.contains('active')) {
        btnAdvanced.click();
    }
    
    // 1. Restore Backtest inputs
    const inp = backtestObj.inputs || {};
    
    const stratSel = document.getElementById('strategy-selector');
    if (stratSel && inp.strategy) {
        stratSel.value = inp.strategy;
        if (typeof window.renderStrategyParams === 'function') {
            window.renderStrategyParams(inp.strategy);
        }
        
        setTimeout(() => {
            if (inp.params) {
                Object.keys(inp.params).forEach(k => {
                    const paramInput = document.getElementById(`param-${k}`);
                    if (paramInput) paramInput.value = inp.params[k];
                });
            }
        }, 100);
    }
    
    if (inp.pair && document.getElementById('pair-selector')) document.getElementById('pair-selector').value = inp.pair;
    if (inp.interval && document.getElementById('interval-selector')) document.getElementById('interval-selector').value = inp.interval;
    if (inp.expiry_candles && document.getElementById('expiry-candles')) document.getElementById('expiry-candles').value = inp.expiry_candles;
    if (inp.payout && document.getElementById('payout')) document.getElementById('payout').value = inp.payout;
    if (inp.n_consecutive && document.getElementById('backtest-n-consecutive')) document.getElementById('backtest-n-consecutive').value = inp.n_consecutive;
    if (inp.bet_fraction && document.getElementById('backtest-bet-fraction')) document.getElementById('backtest-bet-fraction').value = inp.bet_fraction;
    
    // 2. Restore Backtest Results UI
    s.backtestResults = backtestObj.results;
    if (typeof window.displayBacktestResults === 'function') {
        window.displayBacktestResults(backtestObj.results);
    }
    if (typeof window.displayStatistics === 'function') {
        window.displayStatistics(backtestObj.results?.stats || {});
    }
    
    // Add signal markers to candles chart
    if (s.candles && s.candles.length > 0 && backtestObj.results?.signals && window.candleSeries) {
        if (typeof window.buildChartMarkers === 'function') {
            const markers = window.buildChartMarkers(backtestObj.results.signals);
            window.candleSeries.setMarkers(markers);
        }
    }
    
    const btnEst = document.getElementById('btn-estadisticas');
    if (btnEst) btnEst.disabled = false;
    const btnOpt = document.getElementById('btn-optimizador');
    if (btnOpt) btnOpt.disabled = false;
    
    // Auto-fill optimizer inputs
    const wr = backtestObj.results?.summary?.win_rate || backtestObj.results?.stats?.basic?.win_rate || 0;
    const optWrEl = document.getElementById('opt-winrate');
    if (optWrEl) optWrEl.value = (wr * 100).toFixed(2);
    const optPayoutEl = document.getElementById('opt-payout');
    if (optPayoutEl && inp.payout) optPayoutEl.value = inp.payout;
    
    // 3. Restore Optimizer UI if present
    if (backtestObj.optimizer) {
        s.optimizerResults = backtestObj.optimizer;
        const optData = backtestObj.optimizer;
        const results = optData.results_by_n || [];
        const bestN = optData.best_n_for_target || optData.optimal_n;
        const bestPlan = results.find(r => r.n === bestN);

        const ns = results.map(r => r.n);
        const gs = results.map(r => r.growth_per_trade);
        if (document.getElementById('gn-chart') && typeof window.createGrowthRateChart === 'function') {
            window.createGrowthRateChart('gn-chart', ns, gs, optData.optimal_n);
        }
        
        const kellys = results.map(r => r.kelly_f);
        if (document.getElementById('kelly-chart') && typeof window.createBarChart === 'function') {
            window.createBarChart('kelly-chart', ns, kellys, 'Kelly Fraction', '#10b981');
        }
        
        const rec = document.getElementById('opt-recommendation');
        if (rec) {
            rec.style.display = 'block';
            rec.innerHTML = `
                <div class="stat-card" style="margin-top: 15px; border-left: 3px solid var(--accent-green);">
                    <h3 style="color: var(--accent-green)">Recomendación Óptima</h3>
                    <p style="font-size: 2rem; font-weight: 700;">N = ${optData.optimal_n || bestN}</p>
                    <span style="font-size: 0.9rem; color: var(--text-secondary)">
                        Kelly: ${((optData.optimal_kelly || 0) * 100).toFixed(1)}% |
                        G(N) = ${((optData.optimal_growth || 0) * 100).toFixed(4)}% por trade
                    </span>
                </div>
            `;
        }
        
        const nTable = document.getElementById('n-table');
        if (nTable) {
            let tableHtml = `<thead><tr>
                <th>N</th><th>P(éxito)</th><th>Ganancia</th><th>Kelly</th><th>G(N)/trade</th><th>Sharpe</th>
            </tr></thead><tbody>`;
            results.forEach(r => {
                const isOpt = r.n === (optData.optimal_n || bestN);
                tableHtml += `<tr style="${isOpt ? 'background: rgba(16, 185, 129, 0.15);' : ''}">
                    <td>${isOpt ? '>> ' : ''}${r.n}</td>
                    <td>${((r.p_success || r.p_success_single || 0) * 100).toFixed(1)}%</td>
                    <td>${(r.profit_if_win || r.multiplier || 0).toFixed(2)}x</td>
                    <td>${((r.kelly_f || 0) * 100).toFixed(1)}%</td>
                    <td>${((r.growth_per_trade || 0) * 100).toFixed(4)}%</td>
                    <td>${(r.sharpe_ratio || 0).toFixed(3)}</td>
                </tr>`;
            });
            tableHtml += '</tbody>';
            nTable.innerHTML = tableHtml;
        }

        const recContent = document.getElementById('streak-recommendation-content');
        if (recContent && bestPlan) {
            recContent.innerHTML = `
                <div style="font-size: 0.9rem; line-height: 1.5; color: var(--text-primary);">
                    Campaña para <strong>$${(bestPlan.final_capital || 0).toFixed(2)} USD</strong> con racha de <strong style="color: var(--accent-green);">N = ${bestN}</strong>.
                </div>
            `;
        }
    } else {
        s.optimizerResults = null;
        if (window.gnChartInst) window.gnChartInst.destroy();
        if (window.kellyChartInst) window.kellyChartInst.destroy();
        const rec = document.getElementById('opt-recommendation');
        if (rec) rec.style.display = 'none';
        const nTable = document.getElementById('n-table');
        if (nTable) nTable.innerHTML = '';
    }
    
    // 4. Restore Monte Carlo UI if present
    if (backtestObj.montecarlo) {
        const mcData = backtestObj.montecarlo;
        const paths = mcData.paths || [];
        if (paths.length > 0 && document.getElementById('mc-chart') && typeof window.createMonteCarloChart === 'function') {
            const maxLen = Math.max(...paths.map(p => p.length));
            const labels = Array.from({ length: Math.min(maxLen, 200) }, (_, i) => i);
            
            const p95 = [], p75 = [], p50 = [], p25 = [], p5 = [];
            for (let step = 0; step < labels.length; step++) {
                const vals = paths.map(p => p[Math.min(step, p.length - 1)] || 0).sort((a, b) => a - b);
                const len = vals.length;
                p5.push(vals[Math.floor(len * 0.05)]);
                p25.push(vals[Math.floor(len * 0.25)]);
                p50.push(vals[Math.floor(len * 0.50)]);
                p75.push(vals[Math.floor(len * 0.75)]);
                p95.push(vals[Math.floor(len * 0.95)]);
            }
            window.createMonteCarloChart('mc-chart', labels, { p95, p75, p50, p25, p5 });
        }
        
        const fe = mcData.final_equity || {};
        const mcStats = document.getElementById('mc-stats');
        if (mcStats) {
            mcStats.style.display = 'block';
            mcStats.innerHTML = `
                <div class="stat-card"><h3>Mediana Final</h3><p class="text-green">${(fe.median || 0).toFixed(2)}x</p></div>
                <div class="stat-card"><h3>Riesgo de Ruina</h3><p class="${(mcData.ruin_probability || 0) > 0.05 ? 'text-red' : 'text-green'}">${((mcData.ruin_probability || 0) * 100).toFixed(2)}%</p></div>
                <div class="stat-card"><h3>Max Drawdown (P95)</h3><p>${((mcData.max_drawdowns?.p95 || 0) * 100).toFixed(1)}%</p></div>
                <div class="stat-card"><h3>P5 / P95</h3><p>${(fe.p5 || 0).toFixed(2)}x / ${(fe.p95 || 0).toFixed(2)}x</p></div>
            `;
        }
    } else {
        if (window.mcChartInst) window.mcChartInst.destroy();
        const mcStats = document.getElementById('mc-stats');
        if (mcStats) mcStats.style.display = 'none';
    }
    
    const saveBtn = document.getElementById('save-backtest-btn');
    if (saveBtn) {
        saveBtn.style.display = 'block';
        const saved = getSaved();
        if (saved.some(x => x.id === backtestObj.id)) {
            saveBtn.textContent = '¡Guardado!';
            saveBtn.disabled = true;
        } else {
            saveBtn.textContent = 'Guardar en Favoritos';
            saveBtn.disabled = false;
        }
    }
    
    if (typeof window.switchTab === 'function') {
        window.switchTab('backtest');
    }
    renderResultsLists();
}

// Global browser window bindings
if (typeof window !== 'undefined') {
    window.getHistory = getHistory;
    window.setHistory = setHistory;
    window.getSaved = getSaved;
    window.setSaved = setSaved;
    window.updatePersistedBacktest = updatePersistedBacktest;
    window.saveCurrentBacktest = saveCurrentBacktest;
    window.saveBacktestById = saveBacktestById;
    window.deleteBacktestById = deleteBacktestById;
    window.clearHistory = clearHistory;
    window.loadBacktestState = loadBacktestState;
}
