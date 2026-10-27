/**
 * backtest_controller.js - Backtest & Genetic Optimization SSE Controller
 * Handles backtest requests, genetic optimizer streaming, and real-time SSE progress events.
 * Nexus Quant Terminal
 */

const API = '/api';

export async function runBacktest(e) {
    if (e && e.preventDefault) e.preventDefault();
    const btn = document.getElementById('run-backtest-btn');
    if (btn) {
        btn.textContent = 'Ejecutando...';
        btn.disabled = true;
    }

    const saveBtn = document.getElementById('save-backtest-btn');
    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.textContent = 'Guardar en Favoritos';
    }

    const params = {};
    document.querySelectorAll('#dynamic-params [data-param]').forEach(inp => {
        const type = inp.dataset.type;
        if (type === 'bool' || inp.tagName.toLowerCase() === 'select') {
            params[inp.dataset.param] = inp.value === 'true' || inp.value === true;
        } else {
            const val = parseFloat(inp.value);
            params[inp.dataset.param] = isNaN(val) ? inp.value : val;
        }
    });

    const strategy = (window.state && window.state.selectedStrategy) || document.getElementById('strategy-selector')?.value || 'genetic_composite';
    const pair = document.getElementById('pair-selector')?.value || 'BTCUSDT';
    const interval = document.getElementById('interval-selector')?.value || '1h';
    const expiry_candles = parseInt(document.getElementById('expiry-candles')?.value) || 20;
    const payout = parseFloat(document.getElementById('payout')?.value) || 0.92;
    const mode = 'BARBELL';
    const n_consecutive = parseInt(document.getElementById('backtest-n-consecutive')?.value) || 4;
    const bet_fraction = parseFloat(document.getElementById('backtest-bet-fraction')?.value) || 0.1;
    
    const sl_atr = parseFloat(document.getElementById('sl-atr')?.value) || 1.5;
    const tp_atr = parseFloat(document.getElementById('tp-atr')?.value) || 3.0;
    const max_holding = parseInt(document.getElementById('max-holding')?.value) || 20;
    const bullet_risk = parseFloat(document.getElementById('bullet-risk')?.value) || 33.33;
    const fee_pct = (parseFloat(document.getElementById('fee-pct')?.value) || 0.05) / 100.0;
    
    const queryParams = new URLSearchParams({
        strategy, params: JSON.stringify(params), pair, interval, expiry_candles,
        payout, mode, n_consecutive, bet_fraction, sl_atr, tp_atr, max_holding,
        bullet_risk, fee_pct, classic_mode: 'true'
    });

    const progressContainer = document.getElementById('backtest-progress-container');
    const progressBarFill = document.getElementById('backtest-progress-fill');
    const progressText = document.getElementById('backtest-progress-text');
    const progressEta = document.getElementById('backtest-progress-eta');

    if (progressContainer) progressContainer.style.display = 'block';
    if (progressBarFill) progressBarFill.style.width = '0%';
    if (progressText) progressText.textContent = 'Progreso: 0%';
    if (progressEta) progressEta.textContent = 'ETA: --s';

    if (window.activeEventSource) {
        try { window.activeEventSource.close(); } catch(err) {}
    }
    const eventSource = new EventSource(`${API}/backtest-stream?${queryParams.toString()}`);
    window.activeEventSource = eventSource;

    eventSource.onmessage = (event) => {
        const item = JSON.parse(event.data);
        if (item.type === 'log') {
            console.log(item.message);
        } else if (item.type === 'progress') {
            const pct = item.progress.toFixed(1);
            if (progressBarFill) progressBarFill.style.width = `${pct}%`;
            if (progressText) progressText.textContent = `Progreso: ${pct}%`;
            if (progressEta) progressEta.textContent = `Restante: ${item.eta.toFixed(1)}s`;
        } else if (item.type === 'error') {
            alert('Error: ' + item.message);
            eventSource.close();
            if (window.activeEventSource === eventSource) window.activeEventSource = null;
            if (btn) { btn.textContent = 'Ejecutar Backtest Barbell'; btn.disabled = false; }
            if (saveBtn) saveBtn.disabled = true;
            if (progressContainer) progressContainer.style.display = 'none';
        } else if (item.type === 'result') {
            eventSource.close();
            if (window.activeEventSource === eventSource) window.activeEventSource = null;
            if (progressContainer) progressContainer.style.display = 'none';
            
            const data = item.data;
            if (window.state) window.state.backtestResults = data;
            if (typeof window.displayBacktestResults === 'function') window.displayBacktestResults(data);
            if (typeof window.displayStatistics === 'function') window.displayStatistics(data.stats || {});
            
            if (data.signals && data.signals.length > 0 && window.candleSeries) {
                if (typeof window.buildChartMarkers === 'function') {
                    window.candleSeries.setMarkers(window.buildChartMarkers(data.signals));
                }
            }
            
            const btnEst = document.getElementById('btn-estadisticas');
            if (btnEst) btnEst.disabled = false;
            const btnOpt = document.getElementById('btn-optimizador');
            if (btnOpt) btnOpt.disabled = false;
            
            const wr = data.summary?.win_rate || data.stats?.basic?.win_rate || 0;
            const optWr = document.getElementById('opt-winrate');
            if (optWr) optWr.value = (wr * 100).toFixed(2);
            const optPay = document.getElementById('opt-payout');
            if (optPay) optPay.value = payout;
            
            const inputs = {
                strategy, strategy_display: document.getElementById('strategy-selector')?.options[document.getElementById('strategy-selector')?.selectedIndex]?.text || strategy,
                params, pair, interval, expiry_candles, payout, mode, n_consecutive, bet_fraction
            };
            
            if (window.state) {
                window.state.currentBacktestData = {
                    id: 'bt_' + Date.now(),
                    timestamp: Date.now(),
                    inputs,
                    results: data,
                    optimizer: null,
                    montecarlo: null
                };
            }
            
            const backtestSaveBtn = document.getElementById('save-backtest-btn');
            if (backtestSaveBtn) {
                backtestSaveBtn.style.display = 'block';
                backtestSaveBtn.textContent = 'Guardar en Favoritos';
                backtestSaveBtn.disabled = false;
            }
            
            if (typeof window.getHistory === 'function' && typeof window.setHistory === 'function') {
                const historyList = window.getHistory();
                historyList.unshift(window.state.currentBacktestData);
                if (historyList.length > 50) historyList.pop();
                window.setHistory(historyList);
                if (typeof window.renderResultsLists === 'function') window.renderResultsLists();
            }

            if (btn) { btn.textContent = 'Ejecutar Backtest Barbell'; btn.disabled = false; }
        }
    };

    eventSource.onerror = (err) => {
        console.error('SSE Error:', err);
        eventSource.close();
        alert('Error de conexión con el servidor.');
        if (btn) { btn.textContent = 'Ejecutar Backtest Barbell'; btn.disabled = false; }
        if (progressContainer) progressContainer.style.display = 'none';
    };
}

export async function runGeneticOptimizer() {
    const btn = document.getElementById('optimize-genetic-btn');
    const feedback = document.getElementById('genetic-feedback');
    if (btn) { btn.textContent = 'Buscando con Rust...'; btn.disabled = true; }
    if (feedback) { feedback.style.display = 'none'; feedback.innerHTML = ''; }

    const pair = document.getElementById('pair-selector')?.value || 'BTCUSDT';
    const interval = document.getElementById('interval-selector')?.value || '1h';
    const expiry = parseInt(document.getElementById('expiry-candles')?.value) || 1;
    const min_trades = parseFloat(document.getElementById('gen-min-trades')?.value) || 5.0;
    const generations = parseInt(document.getElementById('gen-generations')?.value) || 50;
    const population = parseInt(document.getElementById('gen-population')?.value) || 150;

    const queryParams = new URLSearchParams({ pair, interval, expiry, min_trades, generations, population });

    const progressContainer = document.getElementById('genetic-progress-container');
    const progressBarFill = document.getElementById('genetic-progress-fill');
    const progressText = document.getElementById('genetic-progress-text');
    const progressEta = document.getElementById('genetic-progress-eta');

    if (progressContainer) progressContainer.style.display = 'block';
    if (progressBarFill) progressBarFill.style.width = '0%';
    if (progressText) progressText.textContent = 'Progreso: 0%';
    if (progressEta) progressEta.textContent = 'ETA: --s';

    const eventSource = new EventSource(`${API}/genetic/run-stream?${queryParams.toString()}`);

    eventSource.onmessage = (event) => {
        const item = JSON.parse(event.data);
        if (item.type === 'log') {
            console.log(item.message);
        } else if (item.type === 'progress') {
            const pct = item.progress.toFixed(1);
            if (progressBarFill) progressBarFill.style.width = `${pct}%`;
            if (progressText) progressText.textContent = `Progreso: ${pct}%`;
            if (progressEta) progressEta.textContent = `Restante: ${item.eta.toFixed(1)}s`;
        } else if (item.type === 'error') {
            alert('Error: ' + item.message);
            eventSource.close();
            if (btn) { btn.textContent = 'Ejecutar Búsqueda Genética'; btn.disabled = false; }
            if (progressContainer) progressContainer.style.display = 'none';
        } else if (item.type === 'result') {
            eventSource.close();
            if (progressContainer) progressContainer.style.display = 'none';

            const data = item.data;
            const stratSel = document.getElementById('strategy-selector');
            if (stratSel) {
                stratSel.value = 'genetic_composite';
                if (typeof window.renderStrategyParams === 'function') window.renderStrategyParams('genetic_composite');
                
                setTimeout(() => {
                    const p = data.parameters || {};
                    Object.keys(p).forEach(k => {
                        const paramInput = document.getElementById(`param-${k}`);
                        if (paramInput) {
                            paramInput.value = (typeof p[k] === 'boolean') ? (p[k] ? 1 : 0) : p[k];
                        }
                    });
                    
                    if (feedback) {
                        feedback.style.display = 'block';
                        feedback.style.borderColor = 'var(--accent-green)';
                        feedback.style.color = 'var(--text-primary)';
                        const oosWr = (data.out_of_sample_win_rate * 100).toFixed(1);
                        const isWr = (data.in_sample_win_rate * 100).toFixed(1);
                        const stab = (data.neighbour_stability_is * 100).toFixed(1);
                        feedback.innerHTML = `
                            <div style="color: var(--accent-green); font-weight: 600; margin-bottom: 4px;">✅ ¡Búsqueda en Rust Completada!</div>
                            <div>Win Rate Real (No Visto): <strong>${oosWr}%</strong></div>
                            <div>Estabilidad Vecindad: <strong>${stab}%</strong></div>
                            <div style="font-size: 0.75rem; color: var(--text-secondary);">
                                Win Rate Histórico: ${isWr}% | Trades IS: ${data.in_sample_trades}
                            </div>
                        `;
                    }
                    setTimeout(() => {
                        document.getElementById('backtest-form')?.dispatchEvent(new Event('submit'));
                    }, 100);
                }, 100);
            }

            if (btn) { btn.textContent = 'Ejecutar Búsqueda Genética'; btn.disabled = false; }
        }
    };

    eventSource.onerror = (err) => {
        console.error('SSE Error:', err);
        eventSource.close();
        alert('Error de conexión con el servidor.');
        if (btn) { btn.textContent = 'Ejecutar Búsqueda Genética'; btn.disabled = false; }
        if (progressContainer) progressContainer.style.display = 'none';
    };
}

export function initBacktestController() {
    const backtestForm = document.getElementById('backtest-form');
    if (backtestForm) {
        backtestForm.addEventListener('submit', runBacktest);
    }
    const genBtn = document.getElementById('optimize-genetic-btn');
    if (genBtn) {
        genBtn.addEventListener('click', runGeneticOptimizer);
    }
}
